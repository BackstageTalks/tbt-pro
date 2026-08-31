"""BlinQ orchestration over the canonical ThinQ model.

BlinQ does not implement a second prediction formula. It runs ThinQ in both
orientations and accepts a prediction only when the real A/B model runs are
complementary. Exact 50:50 always means NO_PREDICTION.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from thinq.service import ThinqService
from blinq.features.recent_form import build_recent_form_context
from blinq.loaders.h2h_loader import build_h2h_context
from blinq.model import build_elo_context

REGISTRY_PATH = Path("thinq/data/players/player_registry.json")
TOLERANCE = 0.0001


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(row: Dict[str, Any]) -> str:
    return str(
        row.get("display_name")
        or row.get("canonical_name")
        or row.get("name")
        or row.get("player")
        or ""
    ).strip()


def _registry_mtime() -> int:
    try:
        return REGISTRY_PATH.stat().st_mtime_ns
    except OSError:
        return 0


@lru_cache(maxsize=2)
def _registry_cached(_mtime_ns: int) -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("players") if isinstance(payload, dict) else []
    if isinstance(rows, dict):
        rows = list(rows.values())
    index: Dict[str, Dict[str, Any]] = {}
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        name = _name(raw)
        if not name:
            continue
        row = dict(raw)
        row["player"] = name
        keys = [name, row.get("normalized_name"), row.get("compact_key")]
        keys.extend(row.get("aliases") if isinstance(row.get("aliases"), list) else [])
        for value in keys:
            key = _compact(value)
            if key:
                index.setdefault(key, row)
    return index


def _registry() -> Dict[str, Dict[str, Any]]:
    return _registry_cached(_registry_mtime())


def _tour(row: Dict[str, Any]) -> Optional[str]:
    for value in (
        row.get("tour"), row.get("circuit"), row.get("category"),
        row.get("competition_type"), row.get("gender"), row.get("sex"),
        row.get("league"), row.get("source_tour"),
    ):
        text = str(value or "").strip().upper()
        if "WTA" in text or text in {"F", "W", "WOMEN", "FEMALE"}:
            return "WTA"
        if "ATP" in text or text in {"M", "MEN", "MALE"}:
            return "ATP"
    return None


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    country = row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2")
    return {
        "player": row.get("player") or _name(row),
        "player_id": _int(row.get("api_team_id") or row.get("rapidapi_id") or row.get("player_id")),
        "country_code": str(country).upper() if country else None,
        "country_name": row.get("country_name") or row.get("country"),
        "tour": _tour(row),
        "rank": _int(row.get("rank") or row.get("api_rank")),
        "rank_points": _int(row.get("rank_points") or row.get("api_points")),
        "elo": _float(row.get("elo")),
        "hard_elo": _float(row.get("hard_elo")),
        "clay_elo": _float(row.get("clay_elo")),
        "grass_elo": _float(row.get("grass_elo")),
    }


def _layer(result: Dict[str, Any]) -> Dict[str, Any]:
    value = result.get("thinq_probability_layer") or result.get("probability_layer")
    return value if isinstance(value, dict) else {}



def _pair_index(value1: Any, value2: Any, *, samples1: int = 1, samples2: int = 1) -> Dict[str, Any]:
    """Return a real-data pair index. Missing samples stay unavailable, never 50:50."""
    first = _float(value1)
    second = _float(value2)
    if first is None or second is None or samples1 <= 0 or samples2 <= 0:
        return {"available": False, "p1": None, "p2": None}
    total = first + second
    if total <= 0:
        return {"available": False, "p1": None, "p2": None}
    p1 = round(first / total * 100.0, 1)
    return {"available": True, "p1": p1, "p2": round(100.0 - p1, 1)}


def _elo_indices(player1: Dict[str, Any], player2: Dict[str, Any], surface: str) -> Dict[str, Any]:
    """Return anonymized ELO indices. Raw ratings never enter the public index contract."""
    context = build_elo_context(player1, player2, surface)
    indices = context.get("indices") if isinstance(context, dict) else {}
    return indices if isinstance(indices, dict) else {}

def _surface_h2h_index(h2h: Dict[str, Any]) -> Dict[str, Any]:
    total = _int(h2h.get("same_surface_matches")) or 0
    first = _int(h2h.get("same_surface_pick_wins"))
    second = _int(h2h.get("same_surface_opponent_wins"))
    index = _pair_index(first, second, samples1=total, samples2=total)
    index.update({"label": "SH-INDEX", "sample": total})
    return index


def _window(form: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    player = form.get(side) if isinstance(form.get(side), dict) else {}
    value = player.get(key) if isinstance(player.get(key), dict) else {}
    return value


def _form_record(form: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    window = _window(form, side, key)
    wins = _int(window.get("wins") if window.get("wins") is not None else window.get("w"))
    losses = _int(window.get("losses") if window.get("losses") is not None else window.get("l"))
    count = _int(window.get("count"))
    if count is None and wins is not None and losses is not None:
        count = wins + losses
    if wins is None or losses is None or not count or count <= 0:
        return {"available": False, "wins": None, "losses": None, "count": 0}
    return {"available": True, "wins": wins, "losses": losses, "count": count}


def _form_records(form: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player1": {
            "last10": _form_record(form, "pick", "last10"),
            "surface": _form_record(form, "pick", "surface_last10"),
        },
        "player2": {
            "last10": _form_record(form, "opponent", "last10"),
            "surface": _form_record(form, "opponent", "surface_last10"),
        },
    }


def _form_index(form: Dict[str, Any], key: str, prefix: str) -> Dict[str, Any]:
    first = _window(form, "pick", key)
    second = _window(form, "opponent", key)
    count1 = _int(first.get("count")) or 0
    count2 = _int(second.get("count")) or 0
    sample = min(count1, count2)
    index = _pair_index(first.get("win_pct"), second.get("win_pct"), samples1=count1, samples2=count2)
    index.update({"label": f"{prefix}{sample}-index" if sample > 0 else f"{prefix}-index", "sample": sample})
    return index


def _h2h_index(h2h: Dict[str, Any]) -> Dict[str, Any]:
    total = _int(h2h.get("total_matches")) or 0
    first = _int(h2h.get("pick_wins"))
    second = _int(h2h.get("opponent_wins"))
    index = _pair_index(first, second, samples1=total, samples2=total)
    index.update({"label": f"H{total}-index" if total > 0 else "H-index", "sample": total})
    return index


def _data_index(public: Dict[str, Any], elo: Dict[str, Any], form_window: Dict[str, Any], surface_window: Dict[str, Any], h2h_total: int) -> float:
    checks = [
        public.get("player_id") is not None,
        public.get("elo") is not None,
        elo.get("pick_elo") is not None,
        (_int(form_window.get("count")) or 0) >= 5,
        (_int(surface_window.get("count")) or 0) >= 3,
        h2h_total > 0,
        public.get("rank") is not None,
        bool(public.get("country_code")),
    ]
    return round(sum(1 for item in checks if item) / len(checks) * 100.0, 1)


def _build_indices(forward: Dict[str, Any], player1: Dict[str, Any], player2: Dict[str, Any], surface: str, coverage: Dict[str, Any]) -> Dict[str, Any]:
    elo = forward.get("elo") if isinstance(forward.get("elo"), dict) else {}
    form = forward.get("recent_form") if isinstance(forward.get("recent_form"), dict) else {}
    h2h = forward.get("h2h") if isinstance(forward.get("h2h"), dict) else {}
    p1_last10 = _window(form, "pick", "last10")
    p2_last10 = _window(form, "opponent", "last10")
    p1_surface = _window(form, "pick", "surface_last10")
    p2_surface = _window(form, "opponent", "surface_last10")
    h2h_total = _int(h2h.get("total_matches")) or 0
    elo_indices = _elo_indices(player1, player2, surface)
    return {
        "strength": elo_indices.get("strength") or {"available": False, "p1": None, "p2": None, "label": "E-INDEX"},
        "surface_strength": elo_indices.get("surface_strength") or {"available": False, "p1": None, "p2": None, "label": "SE-INDEX"},
        "form": _form_index(form, "last10", "F"),
        "court_form": _form_index(form, "surface_last10", "CF"),
        "h2h": _h2h_index(h2h),
        "surface_h2h": _surface_h2h_index(h2h),
        "data": {
            "available": _float(coverage.get("score")) is not None,
            "value": round(float(coverage.get("score")) / 10.0, 1) if _float(coverage.get("score")) is not None else None,
            "scale": 10,
            "label": "Data depth",
        },
    }



def _surface_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def _direct_data_bundle(player1: Dict[str, Any], player2: Dict[str, Any], surface: str, forward: Dict[str, Any]) -> Dict[str, Any]:
    """Build BlinQ context only from verified BlinQ match data.

    Missing data remains NO_DATA. ThinQ context, rankings, market data and
    cross-signal fallbacks are not accepted as substitutes.
    """
    cutoff = datetime.now(timezone.utc).isoformat()
    form = build_recent_form_context(
        player1.get("player") or "",
        player2.get("player") or "",
        surface,
        pick_player_id=player1.get("player_id"),
        opponent_player_id=player2.get("player_id"),
        match_start=cutoff,
    )
    h2h = build_h2h_context(
        player1.get("player") or "",
        player2.get("player") or "",
        player1.get("player_id"),
        player2.get("player_id"),
        surface=surface,
        match_start=cutoff,
    )
    return {
        "form": form if isinstance(form, dict) else {"status": "NO_DATA"},
        "h2h": h2h if isinstance(h2h, dict) else {"status": "NO_DATA"},
        "source": "BLINQ_VERIFIED_MATCH_DATA",
        "cutoff": cutoff,
    }

def _coverage(player1: Dict[str, Any], player2: Dict[str, Any], elo: Dict[str, Any], form: Dict[str, Any], h2h: Dict[str, Any], surface: str) -> Dict[str, Any]:
    p1_last = _form_record(form, "pick", "last10")
    p2_last = _form_record(form, "opponent", "last10")
    p1_surface = _form_record(form, "pick", "surface_last10")
    p2_surface = _form_record(form, "opponent", "surface_last10")
    surface_key = {"Hard": "hard_elo", "Clay": "clay_elo", "Grass": "grass_elo"}.get(_surface_bucket(surface))
    families = {
        "elo": bool(player1.get("elo") is not None and player2.get("elo") is not None),
        "surface_elo": bool(surface_key and player1.get(surface_key) is not None and player2.get(surface_key) is not None),
        "form": bool(p1_last.get("available") and p2_last.get("available") and min(p1_last["count"], p2_last["count"]) >= 5),
        "surface_form": bool(p1_surface.get("available") and p2_surface.get("available") and min(p1_surface["count"], p2_surface["count"]) >= 3),
        "h2h": bool((_int(h2h.get("total_matches")) or 0) > 0),
    }
    concrete_surface = _surface_bucket(surface) in {"Hard", "Clay", "Grass"}
    if not concrete_surface:
        families["surface_elo"] = False
        families["surface_form"] = False
    weighted = ({"elo": 40, "form": 40, "h2h": 20} if not concrete_surface
                else {"elo": 30, "surface_elo": 15, "form": 30, "surface_form": 15, "h2h": 10})
    score = sum(weighted[key] for key, available in families.items() if key in weighted and available)
    independent = families["form"] or families["h2h"]
    return {
        "score": float(score),
        "families": families,
        "independent_signal_available": independent,
        "prediction_allowed": bool(families["elo"] and independent and score >= 60),
        "required_rule": "ELO plus usable Form or real H2H, with coverage >= 60",
    }

def _no_prediction(reason: str, flags: List[str], **extra: Any) -> Dict[str, Any]:
    return {
        "model": "BlinQ",
        "model_version": "BLINQ_AUDIT_CONTRACT_V6",
        "status": "NO_PREDICTION",
        "prediction_status": "NO_PREDICTION",
        "winner": None,
        "winner_side": None,
        "winner_probability": None,
        "player1_probability": None,
        "player2_probability": None,
        "public_status": "NO_CLEAR_EDGE",
        "public_label": "NO CLEAR EDGE",
        "reason": reason,
        "flags": sorted(set(flags)),
        **extra,
    }


class BlinqService:
    def __init__(self) -> None:
        self.thinq = ThinqService()

    def players(self) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for row in _registry().values():
            public = _public(row)
            if public["player"] and public["elo"] is not None:
                unique.setdefault(_compact(public["player"]), public)
        return sorted(unique.values(), key=lambda row: str(row["player"]).casefold())

    def _resolve(self, value: str) -> Optional[Dict[str, Any]]:
        return _registry().get(_compact(value))

    def _run(self, pick: Dict[str, Any], opponent: Dict[str, Any], surface: str) -> Dict[str, Any]:
        pick_public, opponent_public = _public(pick), _public(opponent)
        return self.thinq.build_match_features(
            player1=pick_public["player"],
            player2=opponent_public["player"],
            pick=pick_public["player"],
            opponent=opponent_public["player"],
            pick_side="HOME",
            opponent_side="AWAY",
            player1_id=pick_public["player_id"],
            player2_id=opponent_public["player_id"],
            surface=surface,
            level=None,
            best_of=3,
            save_snapshot=False,
        )

    def predict(self, player1: str, player2: str, surface: Optional[str] = None) -> Dict[str, Any]:
        if not str(player1 or "").strip() or not str(player2 or "").strip():
            return _no_prediction("Both players are required.", ["INVALID_INPUT"])
        if _compact(player1) == _compact(player2):
            return _no_prediction("Select two different players.", ["SAME_PLAYER"])

        row1, row2 = self._resolve(player1), self._resolve(player2)
        if row1 is None or row2 is None:
            missing = ([player1] if row1 is None else []) + ([player2] if row2 is None else [])
            return _no_prediction("Player not found in central registry.", ["PLAYER_NOT_FOUND"], missing_players=missing)

        tour1, tour2 = _tour(row1), _tour(row2)
        if not tour1 or not tour2:
            return _no_prediction(
                "Player tour is unavailable. Comparison suppressed.",
                ["PLAYER_TOUR_UNKNOWN"], player1=_public(row1), player2=_public(row2),
            )
        if tour1 != tour2:
            return _no_prediction(
                "ATP and WTA players cannot be compared.",
                ["CROSS_TOUR_COMPARISON"], player1=_public(row1), player2=_public(row2),
            )

        surface_name = str(surface or "Overall")
        forward = self._run(row1, row2, surface_name)
        reverse = self._run(row2, row1, surface_name)
        player1_public, player2_public = _public(row1), _public(row2)
        data_bundle = _direct_data_bundle(player1_public, player2_public, surface_name, forward)
        enriched_forward = dict(forward)
        enriched_forward["recent_form"] = data_bundle.get("form") or {}
        enriched_forward["h2h"] = data_bundle.get("h2h") or {}
        coverage = _coverage(player1_public, player2_public, enriched_forward.get("elo") or {}, enriched_forward["recent_form"], enriched_forward["h2h"], surface_name)
        layer_ab, layer_ba = _layer(forward), _layer(reverse)
        p_ab = _float(layer_ab.get("pick_probability"))
        p_ba = _float(layer_ba.get("pick_probability"))
        edge_ab = _float(layer_ab.get("edge"))
        edge_ba = _float(layer_ba.get("edge"))

        probability_ok = p_ab is not None and p_ba is not None and abs((p_ab + p_ba) - 1.0) <= TOLERANCE
        edge_ok = edge_ab is not None and edge_ba is not None and abs(edge_ab + edge_ba) <= TOLERANCE
        tie_ok = not (
            p_ab == 0.5
            and (layer_ab.get("prediction_status") != "NO_PREDICTION" or layer_ab.get("winner") is not None)
        )
        symmetry_ok = bool(probability_ok and edge_ok and tie_ok)

        audit = {
            "status": "PASS" if symmetry_ok else "FAIL",
            "probability_complement_ok": probability_ok,
            "edge_antisymmetry_ok": edge_ok,
            "tie_guard_ok": tie_ok,
            "probability_sum": round((p_ab or 0.0) + (p_ba or 0.0), 8),
            "edge_sum": round((edge_ab or 0.0) + (edge_ba or 0.0), 8),
            "tolerance": TOLERANCE,
        }

        indices = _build_indices(enriched_forward, player1_public, player2_public, surface_name, coverage)
        validation_failed = not symmetry_ok or p_ab is None or p_ba is None or edge_ab is None or edge_ba is None
        blocked = (
            not symmetry_ok
            or p_ab is None
            or p_ba is None
            or layer_ab.get("prediction_status") == "NO_PREDICTION"
            or p_ab == 0.5
            or not coverage.get("prediction_allowed")
        )
        if blocked:
            flags = list(layer_ab.get("flags") or [])
            if not symmetry_ok:
                flags.append("BLINQ_REAL_AB_SYMMETRY_FAILED")
            if not coverage.get("prediction_allowed"):
                flags.append("INSUFFICIENT_SIGNAL_COVERAGE")
            return _no_prediction(
                "The comparison could not produce a sufficiently supported edge.",
                flags,
                outcome_type="VALIDATION_FAILED" if validation_failed else "NO_CLEAR_EDGE",
                public_status="RESULT_UNAVAILABLE" if validation_failed else "NO_CLEAR_EDGE",
                public_label="RESULT UNAVAILABLE" if validation_failed else "NO CLEAR EDGE",
                confidence=None,
                confidence_label="NOT_CALCULATED",
                low_confidence=bool(coverage.get("score", 0) < 75),
                player1=_public(row1),
                player2=_public(row2),
                surface=surface_name,
                symmetry_audit=audit,
                indices=indices,
                data_coverage=coverage,
                data_depth=indices.get("data", {}).get("value"),
                data_depth_scale=10,
                data_bundle_source=data_bundle.get("source"),
                h2h=enriched_forward.get("h2h") or {},
                recent_form=enriched_forward.get("recent_form") or {},
                elo=enriched_forward.get("elo") or {},
                form_records=_form_records(enriched_forward.get("recent_form") if isinstance(enriched_forward.get("recent_form"), dict) else {}),
            )

        winner_is_p1 = p_ab > 0.5
        return {
            "model": "BlinQ",
            "model_version": "BLINQ_AUDIT_CONTRACT_V6",
            "status": "PREDICTION",
            "prediction_status": "PREDICTION",
            "public_status": "PREDICTION",
            "public_label": "PREDICTION",
            "outcome_type": "PREDICTION",
            "surface": surface_name,
            "player1": _public(row1),
            "player2": _public(row2),
            "player1_probability": round(p_ab, 4),
            "player2_probability": round(1.0 - p_ab, 4),
            "winner": _public(row1)["player"] if winner_is_p1 else _public(row2)["player"],
            "winner_side": "PLAYER1" if winner_is_p1 else "PLAYER2",
            "winner_probability": round(max(p_ab, 1.0 - p_ab), 4),
            "confidence": layer_ab.get("confidence"),
            "confidence_label": ("LOW" if (_float(layer_ab.get("confidence")) or 0.0) < 0.60 else "MEDIUM" if (_float(layer_ab.get("confidence")) or 0.0) < 0.75 else "HIGH"),
            "low_confidence": (_float(layer_ab.get("confidence")) or 0.0) < 0.60 or float(coverage.get("score") or 0.0) < 75.0,
            "edge": edge_ab,
            "h2h": enriched_forward.get("h2h") or {},
            "recent_form": enriched_forward.get("recent_form") or {},
            "elo": enriched_forward.get("elo") or {},
            "data_coverage": coverage,
            "data_depth": indices.get("data", {}).get("value"),
            "data_depth_scale": 10,
            "data_bundle_source": data_bundle.get("source"),
            "flags": sorted(set(layer_ab.get("flags") or [])),
            "symmetry_audit": audit,
            "indices": indices,
            "form_records": _form_records(enriched_forward.get("recent_form") if isinstance(enriched_forward.get("recent_form"), dict) else {}),
        }
