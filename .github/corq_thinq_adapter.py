"""
CORQ -> THINQ Adapter v2

Role:
- CORQ remains the final CORE output model.
- THINQ is the intelligence layer / brain.
- This adapter is only the bridge between the existing CORQ prediction dict and THINQ.

Safety:
- If THINQ fails, existing CORQ/web/RSS/Telegram flow continues.
- New THINQ fields are added without requiring renderer changes.
- Probability adjustment can be disabled by env.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

THINQ_ENABLED = os.getenv("CORQ_THINQ_ENABLED", "1") != "0"
THINQ_APPLY_ADJUSTMENT = os.getenv("CORQ_THINQ_APPLY_ADJUSTMENT", "1") == "1"
THINQ_MAX_ADJUSTMENT = float(os.getenv("CORQ_THINQ_MAX_ADJUSTMENT", "0.06"))
THINQ_MIN_PROBABILITY = float(os.getenv("CORQ_THINQ_MIN_PROBABILITY", "0.10"))
THINQ_MAX_PROBABILITY = float(os.getenv("CORQ_THINQ_MAX_PROBABILITY", "0.90"))

_THINQ_SERVICE = None


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_name(value: Any) -> str:
    try:
        import re
        import unicodedata
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())
    except Exception:
        return ""


def same_player(a: Any, b: Any) -> bool:
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm or a_norm in b_norm or b_norm in a_norm:
        return True
    a_parts = a_norm.split()
    b_parts = b_norm.split()
    return bool(a_parts and b_parts and a_parts[-1] == b_parts[-1])


def infer_tour_type(match: Dict[str, Any]) -> Optional[str]:
    text = " ".join(str(match.get(k) or "") for k in ["gender", "category", "tournament", "tour_type"]).lower()
    if "wta" in text or "women" in text or "female" in text:
        return "wta"
    if "atp" in text or "challenger" in text or "men" in text or "male" in text:
        return "atp"
    return None




def nested_get(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def event_custom_id_from_match(match: Dict[str, Any]) -> Optional[str]:
    raw = match.get("raw") if isinstance(match.get("raw"), dict) else {}
    candidates = [
        match.get("event_custom_id"),
        match.get("custom_id"),
        match.get("customId"),
        raw.get("customId"),
        raw.get("custom_id"),
        nested_get(match, "event", "customId"),
        nested_get(match, "match", "customId"),
    ]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def player_id_from_match(match: Dict[str, Any], side: str) -> Any:
    raw = match.get("raw") if isinstance(match.get("raw"), dict) else {}
    if side == "player1":
        return (
            match.get("player1_id")
            or match.get("player1Id")
            or nested_get(raw, "homeTeam", "id")
            or nested_get(raw, "homeTeam", "playerTeamInfo", "id")
        )
    return (
        match.get("player2_id")
        or match.get("player2Id")
        or nested_get(raw, "awayTeam", "id")
        or nested_get(raw, "awayTeam", "playerTeamInfo", "id")
    )

def get_thinq_service():
    global _THINQ_SERVICE
    if _THINQ_SERVICE is not None:
        return _THINQ_SERVICE
    from thinq.thinq_service import ThinqService
    _THINQ_SERVICE = ThinqService()
    return _THINQ_SERVICE


def build_thinq_features(match: Dict[str, Any], surface: Optional[str]) -> Dict[str, Any]:
    service = get_thinq_service()
    raw = match.get("raw") if isinstance(match.get("raw"), dict) else {}
    return service.build_match_features(
        player1=match.get("player1"),
        player2=match.get("player2"),
        surface=surface or match.get("surface"),
        level=match.get("level") or match.get("category"),
        tournament_url=match.get("tournament_url"),
        tour_type=infer_tour_type(match),
        as_of_date=match.get("date") or match.get("match_date"),
        event_id=match.get("event_id") or match.get("match_id") or match.get("id") or raw.get("id"),
        event_custom_id=event_custom_id_from_match(match),
        player1_id=player_id_from_match(match, "player1"),
        player2_id=player_id_from_match(match, "player2"),
        tournament_id=match.get("tournament_id") or match.get("tournamentId") or nested_get(raw, "tournament", "id"),
        best_of=int(match.get("best_of") or 3),
        raw=raw,
        match_raw=raw,
    )


def edge_for_pick(edge_value: Any, pick: Any, player1: Any, player2: Any) -> Optional[float]:
    edge = safe_float(edge_value)
    if edge is None:
        return None
    if same_player(pick, player1):
        return edge
    if same_player(pick, player2):
        return -edge
    return edge


def calculate_pick_adjustment(thinq_result: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    edges = thinq_result.get("edges") if isinstance(thinq_result.get("edges"), dict) else {}
    confidence = safe_float(thinq_result.get("confidence"))
    if confidence is None:
        confidence = 0.0

    weights = {
        "elo_edge": 0.45,
        "surface_form_edge": 0.25,
        "recent_form_edge": 0.15,
        "level_form_edge": 0.10,
        "h2h_edge": 0.08,
        "fatigue_edge": 0.06,
        "surface_transition_edge": 0.05,
        "status_risk_edge": 0.10,
    }

    pick = prediction.get("pick")
    player1 = prediction.get("player1")
    player2 = prediction.get("player2")
    contributions: Dict[str, Optional[float]] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for key, weight in weights.items():
        pick_edge = edge_for_pick(edges.get(key), pick, player1, player2)
        contributions[key] = pick_edge
        if pick_edge is None:
            continue
        weighted_sum += pick_edge * weight
        total_weight += weight

    raw_adjustment = weighted_sum / total_weight if total_weight > 0 else 0.0
    confidence_multiplier = 0.50 + 0.50 * clamp(confidence, 0.0, 1.0)
    adjustment = clamp(raw_adjustment * confidence_multiplier, -THINQ_MAX_ADJUSTMENT, THINQ_MAX_ADJUSTMENT)

    return {
        "adjustment": round(adjustment, 4),
        "raw_adjustment": round(raw_adjustment, 4),
        "confidence_multiplier": round(confidence_multiplier, 4),
        "contributions": contributions,
    }


def flatten_thinq_fields(thinq_result: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    edges = thinq_result.get("edges") if isinstance(thinq_result.get("edges"), dict) else {}
    contexts = thinq_result.get("contexts") if isinstance(thinq_result.get("contexts"), dict) else {}
    dynamics = contexts.get("match_dynamics") if isinstance(contexts.get("match_dynamics"), dict) else {}
    h2h_ctx = contexts.get("h2h") if isinstance(contexts.get("h2h"), dict) else {}
    if not h2h_ctx:
        raw = thinq_result.get("raw") if isinstance(thinq_result.get("raw"), dict) else {}
        h2h_ctx = raw.get("h2h") if isinstance(raw.get("h2h"), dict) else {}
    quality = thinq_result.get("data_quality") if isinstance(thinq_result.get("data_quality"), dict) else {}
    flags = thinq_result.get("flags") if isinstance(thinq_result.get("flags"), list) else []

    output = {
        "thinq_available": True,
        "thinq_error": None,
        "thinq_version": thinq_result.get("thinq_version"),
        "thinq_role": thinq_result.get("thinq_role"),
        "thinq_confidence": thinq_result.get("confidence"),
        "thinq_flags": flags,
        "thinq_edges": edges,
        "thinq_contexts": contexts,
        "thinq_data_quality": quality,
        "thinq_elo_edge": edges.get("elo_edge"),
        "thinq_surface_form_edge": edges.get("surface_form_edge"),
        "thinq_recent_form_edge": edges.get("recent_form_edge"),
        "thinq_level_form_edge": edges.get("level_form_edge"),
        "thinq_h2h_edge": edges.get("h2h_edge"),
        "thinq_h2h_context": h2h_ctx,
        "thinq_h2h_status": h2h_ctx.get("h2h_status") or h2h_ctx.get("status") or ("AVAILABLE" if h2h_ctx.get("h2h_total_matches") else "NO_DATA"),
        "thinq_h2h_source": h2h_ctx.get("h2h_source") or h2h_ctx.get("source"),
        "thinq_h2h_confidence": h2h_ctx.get("h2h_confidence"),
        "thinq_h2h_total_matches": h2h_ctx.get("h2h_total_matches") or h2h_ctx.get("total_matches"),
        "thinq_h2h_player1_wins": h2h_ctx.get("h2h_player1_wins"),
        "thinq_h2h_player2_wins": h2h_ctx.get("h2h_player2_wins"),
        "thinq_h2h_reason": h2h_ctx.get("h2h_reason") or h2h_ctx.get("reason"),
        "thinq_fatigue_edge": edges.get("fatigue_edge"),
        "thinq_surface_transition_edge": edges.get("surface_transition_edge"),
        "thinq_status_risk_edge": edges.get("status_risk_edge"),
        "thinq_sets_edge": edges.get("sets_edge"),
        "thinq_games_edge": edges.get("games_edge"),
        "thinq_tiebreak_edge": edges.get("tiebreak_edge"),
        "thinq_decider_edge": edges.get("decider_edge"),
        "thinq_projected_sets": dynamics.get("projected_sets"),
        "thinq_projected_games": dynamics.get("projected_games"),
        "thinq_tiebreak_probability": dynamics.get("tiebreak_probability"),
        "thinq_decider_probability": dynamics.get("decider_probability"),
        "thinq_straight_sets_probability": dynamics.get("straight_sets_probability"),
        "thinq_match_dynamics_confidence": dynamics.get("confidence"),
        "thinq_close_match_index": dynamics.get("close_match_index"),
        "thinq_favorite_strength_index": dynamics.get("favorite_strength_index"),
    }

    if prediction.get("expected_games") is None and dynamics.get("projected_games") is not None:
        output["expected_games"] = dynamics.get("projected_games")
    if prediction.get("tie_break_probability") is None and dynamics.get("tiebreak_probability") is not None:
        output["tie_break_probability"] = dynamics.get("tiebreak_probability")
    if prediction.get("expected_sets") is None and dynamics.get("projected_sets") is not None:
        output["expected_sets"] = dynamics.get("projected_sets")

    return output


def attach_thinq_to_prediction(
    prediction: Dict[str, Any],
    match: Dict[str, Any],
    surface: Optional[str],
    pick: Any,
    base_probability: Optional[float],
    final_probability: Optional[float],
) -> Dict[str, Any]:
    item = dict(prediction)

    if not THINQ_ENABLED:
        item["thinq_available"] = False
        item["thinq_error"] = "CORQ_THINQ_ENABLED=0"
        item.setdefault("thinq_flags", [])
        return item

    try:
        thinq_result = build_thinq_features(match=match, surface=surface)
        item.update(flatten_thinq_fields(thinq_result, item))
        adj = calculate_pick_adjustment(thinq_result, item)
        item["corq_thinq_adjustment"] = adj["adjustment"]
        item["corq_thinq_raw_adjustment"] = adj["raw_adjustment"]
        item["corq_thinq_confidence_multiplier"] = adj["confidence_multiplier"]
        item["corq_thinq_contributions"] = adj["contributions"]
        item["corq_thinq_adjustment_applied"] = False
        item["corq_thinq_adjustment_mode"] = "THINQ_ENABLED_NOT_APPLIED"

        current_probability = safe_float(item.get("probability"))
        if current_probability is None:
            current_probability = safe_float(final_probability)
        item["corq_raw_probability"] = round(current_probability, 4) if current_probability is not None else None

        if THINQ_APPLY_ADJUSTMENT and current_probability is not None:
            adjusted = clamp(current_probability + adj["adjustment"], THINQ_MIN_PROBABILITY, THINQ_MAX_PROBABILITY)
            item["corq_thinq_adjusted_probability"] = round(adjusted, 4)
            item["probability"] = round(adjusted, 4)
            item["corq_ai_probability_before_thinq"] = item.get("corq_ai_probability")
            item["corq_ai_probability"] = round(adjusted, 4)
            item["corq_thinq_adjustment_applied"] = True
            item["corq_thinq_adjustment_mode"] = "APPLIED_TO_CORQ_PROBABILITY"
        else:
            item["corq_thinq_adjusted_probability"] = None
            if current_probability is None:
                item["corq_thinq_adjustment_mode"] = "NO_CORQ_PROBABILITY"
            elif not THINQ_APPLY_ADJUSTMENT:
                item["corq_thinq_adjustment_mode"] = "DISABLED_BY_ENV"

        return item
    except Exception as exc:
        item["thinq_available"] = False
        item["thinq_error"] = str(exc)
        flags = item.get("thinq_flags") if isinstance(item.get("thinq_flags"), list) else []
        item["thinq_flags"] = flags + ["THINQ_ATTACH_FAILED"]
        return item
