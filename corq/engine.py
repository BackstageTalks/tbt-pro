"""CORQ daily runtime with side safety.

Hard rule:
- player1 = home/API first side
- player2 = away/API second side
- pick/opponent are derived from pick_side by corq.sides
- THINQ receives pick/opponent and side audit for candidate-side calculations
"""
from __future__ import annotations

import argparse
import inspect
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from corq.candidates import load_candidates
from corq.model import build_corq_prediction
from corq.outputs import save_all, save_run_manifest, save_top7
from corq.ranking import make_all_match_view, rank_corq, top7_from_ranking
from corq.sides import build_side_audit, repair_candidate_side


def _load_thinq_service():
    try:
        from thinq.service import ThinqService  # type: ignore
        return ThinqService()
    except Exception:
        try:
            from thinq.thinq_service import ThinqService  # type: ignore
            return ThinqService()
        except Exception:
            return None


def _load_ta_rankings() -> Dict[str, Any]:
    try:
        from thinq.loaders.ranking_loader import load_rankings  # type: ignore
        data = load_rankings()
        return data if isinstance(data, dict) else {"players": {}}
    except Exception:
        return {"players": {}}


def _enrich_with_ta_rankings(record: Dict[str, Any], rankings: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from thinq.loaders.ranking_loader import enrich_row_with_ta_ranks  # type: ignore
        return enrich_row_with_ta_ranks(record, rankings=rankings)
    except Exception:
        record.setdefault("pick_ta_rank_display", "(X)")
        record.setdefault("opponent_ta_rank_display", "(X)")
        return record



def _enrich_with_ta_profile_context(record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        try:
            from thinq.loaders.ta_profile_loader import build_match_ta_context  # type: ignore
        except Exception:
            # Some repo snapshots keep the TA profile loader as a top-level helper.
            # Keep this fallback so Aces/DF projections are not silently lost due to
            # import-path drift between workflows.
            from ta_profile_loader import build_match_ta_context  # type: ignore
        ctx = build_match_ta_context(
            str(record.get("pick") or record.get("player") or record.get("player1") or ""),
            str(record.get("opponent") or record.get("opp") or record.get("player2") or ""),
            str(record.get("surface") or record.get("surface_raw") or ""),
        )
        if isinstance(ctx, dict):
            record.update(ctx)
            record["ta_context"] = ctx
            return record
    except Exception as exc:
        record.setdefault("ta_context_error", str(exc))
    defaults = {
        "ta_status": "N/A",
        "ta_pick_status": "N/A",
        "ta_opp_status": "N/A",
        "ta_pick_set_pct": None,
        "ta_opp_set_pct": None,
        "ta_pick_game_pct": None,
        "ta_opp_game_pct": None,
        "ta_pick_tb_split": None,
        "ta_opp_tb_split": None,
        "ta_pick_ace_pct": None,
        "ta_opp_ace_pct": None,
        "ta_pick_df_pct": None,
        "ta_opp_df_pct": None,
        "ta_pick_surface_dr": None,
        "ta_opp_surface_dr": None,
        "ta_pick_rpw_pct": None,
        "ta_opp_rpw_pct": None,
        "ta_pick_depth": None,
        "ta_opp_depth": None,
        "pick_aces_line": None,
        "opponent_aces_line": None,
        "total_aces_line": None,
        "aces_status": "N/A",
        "ta_winner_decision": "N/A",
        "ta_winner_read": "N/A",
        "ta_sets_decision": "N/A",
        "ta_games_decision": "N/A",
        "ta_tb_decision": "N/A",
        "ta_serve_return_pattern": "N/A",
        "ta_match_shape": "N/A",
        "ta_depth_label": "N/A",
        "ta_decision_confidence": 0.0,
        "ta_decision_notes": [],
    }
    for key, value in defaults.items():
        record.setdefault(key, value)
    return record


def _call_build_match_features(thinq_service: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    method = thinq_service.build_match_features
    try:
        signature = inspect.signature(method)
        accepted = set(signature.parameters.keys())
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        filtered = dict(payload) if accepts_kwargs else {key: value for key, value in payload.items() if key in accepted}
        return method(**filtered)
    except Exception:
        return method(
            player1=payload.get("player1"),
            player2=payload.get("player2"),
            surface=payload.get("surface"),
            level=payload.get("level"),
            event_id=payload.get("event_id"),
            best_of=payload.get("best_of") or 3,
        )


def _nested_get(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _raw_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = record.get("raw")
    return raw if isinstance(raw, dict) else {}


def _event_custom_id(record: Dict[str, Any]) -> Optional[str]:
    raw = _raw_dict(record)
    candidates = [
        record.get("event_custom_id"),
        record.get("custom_id"),
        record.get("customId"),
        raw.get("customId"),
        raw.get("custom_id"),
        _nested_get(record, "event", "customId"),
        _nested_get(record, "match", "customId"),
    ]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def _raw_team_id(record: Dict[str, Any], side: str) -> Any:
    raw = _raw_dict(record)
    key = "homeTeam" if side == "HOME" else "awayTeam"
    team = raw.get(key) if isinstance(raw.get(key), dict) else {}
    if team.get("id") not in (None, ""):
        return team.get("id")
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return info.get("id")


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _enrich_with_thinq(record: Dict[str, Any], thinq_service: Any) -> Dict[str, Any]:
    safe_record = repair_candidate_side(record)
    safe_record["side_audit"] = build_side_audit(safe_record)

    if thinq_service is None:
        safe_record["thinq"] = {"available": False, "error": "THINQ_SERVICE_UNAVAILABLE"}
        safe_record["thinq_available"] = False
        safe_record["thinq_error"] = "THINQ_SERVICE_UNAVAILABLE"
        safe_record["thinq_flags"] = ["THINQ_SERVICE_UNAVAILABLE"]
        return safe_record

    raw = _raw_dict(safe_record)
    event_custom_id = _event_custom_id(safe_record)
    event_id = _first_present(
        safe_record.get("event_id"),
        safe_record.get("match_id"),
        safe_record.get("id"),
        raw.get("id"),
    )

    payload = {
        "player1": safe_record.get("player1"),
        "player2": safe_record.get("player2"),
        "surface": safe_record.get("surface") or safe_record.get("surface_raw") or raw.get("groundType"),
        "level": safe_record.get("level") or safe_record.get("category") or _nested_get(raw, "tournament", "category", "name"),
        "tournament_url": safe_record.get("tournament_url"),
        "tour_type": safe_record.get("tour_type") or safe_record.get("gender") or _nested_get(raw, "homeTeam", "gender") or _nested_get(raw, "awayTeam", "gender"),
        "as_of_date": safe_record.get("date") or safe_record.get("match_date") or safe_record.get("match_start") or safe_record.get("start_time"),
        "event_id": event_id,
        "event_custom_id": event_custom_id,
        "custom_id": event_custom_id,
        "customId": event_custom_id,
        "player1_id": _first_present(safe_record.get("player1_id"), safe_record.get("player1Id"), _raw_team_id(safe_record, "HOME")),
        "player2_id": _first_present(safe_record.get("player2_id"), safe_record.get("player2Id"), _raw_team_id(safe_record, "AWAY")),
        "tournament_id": _first_present(safe_record.get("tournament_id"), safe_record.get("tournamentId"), _nested_get(raw, "tournament", "id")),
        "best_of": safe_record.get("best_of") or 3,
        "pick": safe_record.get("pick"),
        "opponent": safe_record.get("opponent"),
        "pick_side": safe_record.get("pick_side"),
        "opponent_side": safe_record.get("opponent_side"),
        "side_audit": safe_record.get("side_audit"),
        # Odds are part of the ThinQ match context. Do not force ThinQ to
        # rediscover them from raw payloads because side-safe candidates already
        # carry correctly oriented pick/opponent odds.
        "odds_player1": safe_record.get("odds_player1") or safe_record.get("p1_odds") or safe_record.get("odds1") or safe_record.get("home_odds"),
        "odds_player2": safe_record.get("odds_player2") or safe_record.get("p2_odds") or safe_record.get("odds2") or safe_record.get("away_odds"),
        "p1_odds": safe_record.get("p1_odds") or safe_record.get("odds_player1") or safe_record.get("home_odds"),
        "p2_odds": safe_record.get("p2_odds") or safe_record.get("odds_player2") or safe_record.get("away_odds"),
        "odds1": safe_record.get("odds1") or safe_record.get("odds_player1") or safe_record.get("home_odds"),
        "odds2": safe_record.get("odds2") or safe_record.get("odds_player2") or safe_record.get("away_odds"),
        "home_odds": safe_record.get("home_odds") or safe_record.get("odds_player1") or safe_record.get("p1_odds"),
        "away_odds": safe_record.get("away_odds") or safe_record.get("odds_player2") or safe_record.get("p2_odds"),
        "pick_odds": safe_record.get("pick_odds") or safe_record.get("odds"),
        "opponent_odds": safe_record.get("opponent_odds"),
        "odds": safe_record.get("odds") or safe_record.get("pick_odds"),
        "odds_pair_available": safe_record.get("odds_pair_available"),
        "odds_matching_direction": safe_record.get("odds_matching_direction"),
        "odds_labels_confirmed": safe_record.get("odds_labels_confirmed"),
        "status_type": safe_record.get("status_type"),
        "status_code": safe_record.get("status_code"),
        "match_start": safe_record.get("match_start") or safe_record.get("start_time"),
        "start_time": safe_record.get("start_time") or safe_record.get("match_start"),
        "raw": raw,
        "match_raw": raw,
        "raw_event": raw,
    }

    try:
        thinq = _call_build_match_features(thinq_service, payload)
        if not isinstance(thinq, dict):
            thinq = {"available": False, "error": "THINQ_RETURNED_NON_DICT"}
    except Exception as exc:
        thinq = {"available": False, "error": str(exc), "flags": ["THINQ_ATTACH_FAILED"]}

    safe_record["thinq"] = thinq
    safe_record["thinq_available"] = bool(thinq.get("available", thinq.get("thinq_available", False)))
    safe_record["thinq_error"] = thinq.get("error")
    safe_record["thinq_confidence"] = thinq.get("confidence") or thinq.get("thinq_confidence")
    safe_record["thinq_edges"] = thinq.get("edges") if isinstance(thinq.get("edges"), dict) else {}
    safe_record["thinq_flags"] = thinq.get("flags") or thinq.get("thinq_flags") or []
    # Flatten data-source status for easier web/debug inspection.
    safe_record["thinq_elo_status"] = _nested_get(thinq, "elo", "status") or thinq.get("thinq_elo_status")
    safe_record["thinq_recent_form_status"] = _nested_get(thinq, "recent_form", "status") or thinq.get("thinq_recent_form_status")
    safe_record["thinq_recent_form_reason"] = _nested_get(thinq, "recent_form", "reason") or thinq.get("thinq_recent_form_reason")
    safe_record["thinq_history_match_count"] = _nested_get(thinq, "recent_form", "history_status", "match_count")
    safe_record["thinq_history_file_count"] = _nested_get(thinq, "recent_form", "history_status", "file_count")
    safe_record["thinq_match_dynamics_status"] = _nested_get(thinq, "match_dynamics", "status") or thinq.get("thinq_match_dynamics_status")
    safe_record["thinq_probability_layer_status"] = _nested_get(thinq, "thinq_probability_layer", "status") or thinq.get("thinq_probability_status")

    for key, value in thinq.items():
        if key.startswith("thinq_"):
            safe_record[key] = value

    safe_record["thinq_h2h_requested_event_custom_id"] = (
        _nested_get(thinq, "h2h", "requested_event_custom_id")
        or thinq.get("thinq_h2h_requested_event_custom_id")
    )
    return safe_record






def _date_only_for_marq(record: Dict[str, Any]) -> str:
    for key in ("match_date", "date", "start_time_utc", "match_time_utc", "commence_time", "start_time", "match_time"):
        value = record.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if len(text) >= 10:
            return text[:10]
    return date.today().isoformat()


def _decimal_odds(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return None
        number = float(str(value).replace(",", "."))
        if 1.01 <= number <= 100.0:
            return number
    except Exception:
        return None
    return None


def _pct_points(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return None
        number = float(str(value).replace("%", "").replace(",", "."))
        if abs(number) <= 1.0:
            number *= 100.0
        return number
    except Exception:
        return None


def _first_pct_points(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _nested_get(row, *key.split(".")) if "." in key else row.get(key)
        number = _pct_points(value)
        if number is not None:
            return number
    return None


def _first_float(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _nested_get(row, *key.split(".")) if "." in key else row.get(key)
        try:
            if value not in (None, "", "—", "-"):
                return float(str(value).replace(",", "."))
        except Exception:
            continue
    return None


def _append_unique_flag(row: Dict[str, Any], key: str, flag: str) -> None:
    values = row.get(key)
    if not isinstance(values, list):
        values = [] if values in (None, "") else [str(values)]
    if flag not in values:
        values.append(flag)
    row[key] = values


def _has_positive_ta_support(row: Dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "ta_winner_decision",
            "ta_winner_read",
            "ta_signal",
            "ta_signal_label",
            "ta_signal_type",
        )
    ).lower()
    return any(token in text for token in ("supports pick", "slight pick", "winner_support", "ta supports pick"))


def _has_positive_form_support(row: Dict[str, Any]) -> bool:
    for key in (
        "recent_form_edge",
        "short_form_edge",
        "surface_recent_form_edge",
        "opponent_quality_edge",
        "thinq.recent_form.edge",
        "thinq.recent_form.recent_form_edge",
    ):
        value = _first_float(row, key)
        if value is not None and value > 0:
            return True
    return False


def _apply_high_edge_reality_guard(row: Dict[str, Any]) -> Dict[str, Any]:
    """Block TOP7 promotion for overconfident high-edge market disagreements."""
    out = dict(row)
    corq_pct = _first_pct_points(out, "corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability", "cloq_probability")
    odds = _decimal_odds(out.get("pick_odds") or out.get("cloq_pick_odds") or out.get("selected_odds") or out.get("odds_decimal") or out.get("decimal_odds") or out.get("odds"))
    raw_edge = _first_pct_points(out, "pick_thinq_edge", "thinq_edge", "thinq_total_edge", "top7_pick_thinq_edge", "edge", "model_edge", "value_edge")
    if raw_edge is None and corq_pct is not None and odds is not None:
        raw_edge = corq_pct - (100.0 / odds)
    elif raw_edge is None and corq_pct is not None:
        raw_edge = corq_pct - 50.0

    stat_depth = _first_pct_points(out, "stat_data_depth", "pick_data_depth", "data_depth", "top7_pick_data_depth", "thinq_probability_confidence")
    form_depth = _first_pct_points(out, "form_data_depth", "form_confidence", "recent_form_confidence", "thinq_form_confidence")
    ta_support = _has_positive_ta_support(out)
    form_support = _has_positive_form_support(out)
    strong_depth = (stat_depth is not None and stat_depth >= 80.0) and (form_depth is not None and form_depth >= 70.0)

    edge_multiplier = 1.0
    if raw_edge is not None:
        if form_depth is not None and form_depth < 50.0:
            edge_multiplier = 0.45
            _append_unique_flag(out, "corq_warning_flags", "LOW_FORM_DEPTH_EDGE_CAPPED")
        elif form_depth is not None and form_depth < 60.0:
            edge_multiplier = 0.55
            _append_unique_flag(out, "corq_warning_flags", "LOW_FORM_DEPTH_EDGE_CAPPED")
        elif form_depth is not None and form_depth < 70.0:
            edge_multiplier = 0.75
    adjusted_edge = round(raw_edge * edge_multiplier, 4) if raw_edge is not None else None

    confirmations = int(ta_support) + int(form_support) + int(strong_depth)
    blocked_reasons: List[str] = []
    if raw_edge is not None and odds is not None and raw_edge >= 15.0 and odds >= 1.80:
        _append_unique_flag(out, "risk_flags", "MARKET_DISAGREEMENT_RISK")
        if not (ta_support and strong_depth):
            blocked_reasons.append("HIGH_EDGE_NEEDS_TA_AND_DEPTH_CONFIRMATION")
    if corq_pct is not None and odds is not None and odds >= 2.00 and corq_pct >= 65.0:
        _append_unique_flag(out, "risk_flags", "MARKET_DISAGREEMENT_RISK")
        if confirmations < 2:
            blocked_reasons.append("UNDERDOG_PRICE_NEEDS_TWO_CONFIRMATIONS")
    if raw_edge is not None and raw_edge >= 12.0 and form_depth is not None and form_depth < 60.0:
        blocked_reasons.append("LOW_FORM_DEPTH_WITH_HIGH_EDGE")

    out["raw_pick_edge_pp"] = round(raw_edge, 4) if raw_edge is not None else None
    out["confidence_adjusted_edge_pp"] = adjusted_edge
    out["edge_guard_multiplier"] = edge_multiplier
    out["edge_guard_confirmations"] = confirmations
    out["edge_guard_ta_support"] = ta_support
    out["edge_guard_form_support"] = form_support
    out["edge_guard_strong_depth"] = strong_depth

    if blocked_reasons:
        for flag in ("HIGH_EDGE_QUARANTINE", "TOP7_EDGE_GUARD_BLOCKED"):
            _append_unique_flag(out, "risk_flags", flag)
            _append_unique_flag(out, "corq_warning_flags", flag)
            _append_unique_flag(out, "top7_quality_reject_reasons", flag)
        for reason in blocked_reasons:
            _append_unique_flag(out, "top7_quality_reject_reasons", reason)
        out["top7_edge_guard_blocked"] = True
        out["top7_publishable"] = False
        out["eligible_for_top7"] = False
        out["edge_guard_status"] = "BLOCKED_FROM_TOP7"
        out["edge_guard_reasons"] = blocked_reasons
    else:
        out["top7_edge_guard_blocked"] = False
        out["edge_guard_status"] = "OK"
        out["edge_guard_reasons"] = []
    return out


def _no_vig_pair_from_odds(pick_odds: Any, opponent_odds: Any) -> tuple[Optional[float], Optional[float]]:
    pick = _decimal_odds(pick_odds)
    opp = _decimal_odds(opponent_odds)
    if pick is None or opp is None:
        return None, None
    p_raw = 1.0 / pick
    o_raw = 1.0 / opp
    total = p_raw + o_raw
    if total <= 0:
        return None, None
    return round((p_raw / total) * 100.0, 1), round((o_raw / total) * 100.0, 1)


def _fallback_marq_from_row(record: Dict[str, Any]) -> Dict[str, Any]:
    """Build a minimal MARQ view from already available match odds.

    This prevents empty MarQ boxes when bookmaker event lookup fails. It does
    not create movement or CLV because historical/current quote snapshots are
    required for those fields.
    """
    pick_odds = _first_present(record.get("pick_odds"), record.get("odds"))
    opponent_odds = _first_present(record.get("opponent_odds"), record.get("opp_odds"))
    if pick_odds is None or opponent_odds is None:
        pick_side = str(record.get("pick_side") or "").upper()
        if pick_side == "HOME":
            pick_odds = _first_present(record.get("odds_player1"), record.get("p1_odds"), record.get("odds1"), record.get("home_odds"))
            opponent_odds = _first_present(record.get("odds_player2"), record.get("p2_odds"), record.get("odds2"), record.get("away_odds"))
        elif pick_side == "AWAY":
            pick_odds = _first_present(record.get("odds_player2"), record.get("p2_odds"), record.get("odds2"), record.get("away_odds"))
            opponent_odds = _first_present(record.get("odds_player1"), record.get("p1_odds"), record.get("odds1"), record.get("home_odds"))
        else:
            pick_odds = _first_present(record.get("odds_player1"), record.get("p1_odds"), record.get("odds1"), record.get("home_odds"), pick_odds)
            opponent_odds = _first_present(record.get("odds_player2"), record.get("p2_odds"), record.get("odds2"), record.get("away_odds"), opponent_odds)
    pick_pct, opp_pct = _no_vig_pair_from_odds(pick_odds, opponent_odds)
    if pick_pct is None or opp_pct is None:
        return {}
    edge = round(pick_pct - 50.0, 1)
    final = "Market With Pick" if edge >= 2.0 else "Market Against Pick" if edge <= -2.0 else "Neutral"
    return {
        "marq_market_view": True,
        "marq_source": "RuntimeOddsFallback",
        "marq_market_name": "Match winner",
        "marq_provider_count": 1,
        "marq_crowd_pick_pct": pick_pct,
        "marq_crowd_opponent_pct": opp_pct,
        "marq_edge_pct": edge,
        "marq_move_signal": "PENDING",
        "marq_display_move_signal": "PENDING",
        "marq_movement_available": False,
        "marq_initial_pick_odds": None,
        "marq_current_pick_odds": _decimal_odds(pick_odds),
        "marq_initial_opponent_odds": None,
        "marq_current_opponent_odds": _decimal_odds(opponent_odds),
        "marq_move_range": None,
        "marq_market_move_pct": None,
        "marq_quality_signal": "ODDS ONLY",
        "marq_final": final,
        "marq_final_display": final,
        "marq_clv_status": "PENDING",
    }


def _enrich_with_marq(record: Dict[str, Any]) -> Dict[str, Any]:
    """Attach MARQ market-view fields to a scored match row.

    Primary source is marq.pipeline/provider. If provider data is unavailable,
    use the current routed odds as a minimal no-vig market view so the MarQ box
    still has Pick/Opp/Edge data instead of all blanks.
    """
    output = dict(record)
    try:
        from marq.pipeline import build_marq_from_match  # type: ignore
        marq = build_marq_from_match(
            player1=str(output.get("player1") or ""),
            player2=str(output.get("player2") or ""),
            date_only=_date_only_for_marq(output),
            pick=str(output.get("pick") or output.get("player") or "") or None,
            odds_player1=_decimal_odds(_first_present(output.get("odds_player1"), output.get("p1_odds"), output.get("odds1"), output.get("home_odds"))),
            odds_player2=_decimal_odds(_first_present(output.get("odds_player2"), output.get("p2_odds"), output.get("odds2"), output.get("away_odds"))),
        )
        if isinstance(marq, dict):
            output.update({k: v for k, v in marq.items() if v not in (None, "")})
    except Exception as exc:
        output.setdefault("marq_error", str(exc))

    if output.get("marq_crowd_pick_pct") in (None, "") or output.get("marq_crowd_opponent_pct") in (None, ""):
        fallback = _fallback_marq_from_row(output)
        if fallback:
            for key, value in fallback.items():
                output.setdefault(key, value)

    if output.get("marq_edge_pct") in (None, ""):
        try:
            pick_pct = float(output.get("marq_crowd_pick_pct"))
            output["marq_edge_pct"] = round(pick_pct - 50.0, 1)
        except Exception:
            pass
    if output.get("marq_final") in (None, ""):
        try:
            edge = float(output.get("marq_edge_pct"))
            output["marq_final"] = "Market With Pick" if edge >= 2.0 else "Market Against Pick" if edge <= -2.0 else "Neutral"
            output["marq_final_display"] = output["marq_final"]
        except Exception:
            output.setdefault("marq_final", "Pending")

    try:
        from marq.odds_snapshots import enrich_row_with_internal_marq  # type: ignore
        output = enrich_row_with_internal_marq(output)
    except Exception as exc:
        output.setdefault("marq_internal_error", str(exc))
    return output

def _enrich_with_sets_games(record: Dict[str, Any]) -> Dict[str, Any]:
    """Attach Sets/Games market-aware fields from marq.market_lines.

    This is intentionally soft-fail: if market helpers or upstream APIs are not
    available, the CORQ runtime continues and the renderer shows N/A/Pending.
    """
    try:
        from marq.market_lines import build_sets_games_from_match, build_sets_games_value_candidates  # type: ignore
    except Exception as exc:
        record.setdefault("sets_games_status", "UNAVAILABLE")
        record.setdefault("sets_games_error", str(exc))
        record.setdefault("sets_games_best_value", "Pending lines")
        return record

    try:
        model_prediction = {
            "probability_player1": record.get("probability_player1") or record.get("p1_probability") or record.get("player1_probability"),
            "probability_player2": record.get("probability_player2") or record.get("p2_probability") or record.get("player2_probability"),
        }
        enriched = build_sets_games_from_match(record, model_prediction=model_prediction)
        if isinstance(enriched, dict):
            record.update(enriched)
        value_candidates = build_sets_games_value_candidates(record)
        record["sets_games_value_candidates"] = value_candidates
        if value_candidates and value_candidates[0].get("selection"):
            record["sets_games_best_value"] = value_candidates[0].get("selection")
            record["sets_games_best_value_edge"] = value_candidates[0].get("edge")
        else:
            record.setdefault("sets_games_best_value", "Pending lines")
        record.setdefault("sets_games_status", "OK")
    except Exception as exc:
        record.setdefault("sets_games_status", "ERROR")
        record.setdefault("sets_games_error", str(exc))
        record.setdefault("sets_games_best_value", "Pending lines")
    return record

def _write_results_foundation_snapshots(
    all_rows: List[Dict[str, Any]],
    top7_rows: List[Dict[str, Any]],
    run_date: Optional[str],
    output_root: str,
) -> Dict[str, str]:
    """Store immutable daily snapshots for future Results evaluation."""
    day = (run_date or date.today().isoformat())[:10]
    year = day[:4]
    root = Path(output_root) / "snapshots" / year
    root.mkdir(parents=True, exist_ok=True)
    top7_path = root / f"{day}_corq_top7_snapshot.json"
    all_path = root / f"{day}_all_audit_snapshot.json"
    top7_path.write_text(json.dumps(top7_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    all_path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_root = Path(output_root) / "snapshots"
    latest_root.mkdir(parents=True, exist_ok=True)
    (latest_root / "latest_corq_top7_snapshot.json").write_text(json.dumps(top7_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (latest_root / "latest_all_audit_snapshot.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "corq_top7_snapshot": str(top7_path),
        "all_audit_snapshot": str(all_path),
        "latest_corq_top7_snapshot": str(latest_root / "latest_corq_top7_snapshot.json"),
        "latest_all_audit_snapshot": str(latest_root / "latest_all_audit_snapshot.json"),
    }


def run_daily(input_path: Optional[str] = None, output_root: str = "outputs", run_date: Optional[str] = None) -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    raw_candidates = load_candidates(input_path)
    candidates = [repair_candidate_side(candidate) for candidate in raw_candidates]
    thinq_service = _load_thinq_service()
    ta_rankings = _load_ta_rankings()

    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        enriched = _enrich_with_thinq(candidate, thinq_service)
        prediction = build_corq_prediction(enriched)
        prediction = _enrich_with_ta_rankings(prediction, ta_rankings)
        prediction = _enrich_with_ta_profile_context(prediction)
        prediction = _enrich_with_sets_games(prediction)
        prediction = _enrich_with_marq(prediction)
        prediction = _apply_high_edge_reality_guard(prediction)
        scored.append(prediction)

    all_view = make_all_match_view(scored)
    ranking = rank_corq(scored)
    ranking_for_top7 = [row for row in ranking if not row.get("top7_edge_guard_blocked")]
    top7 = top7_from_ranking(ranking_for_top7, top_n=7)

    all_paths = save_all(all_view, run_date=run_date, output_root=output_root)
    top7_paths = save_top7(top7, run_date=run_date, output_root=output_root)
    snapshot_paths = _write_results_foundation_snapshots(all_view, top7, run_date=run_date, output_root=output_root)
    manifest = {
        "runtime": "corq_daily_side_safe",
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date or date.today().isoformat(),
        "input_path": input_path,
        "candidate_count": len(candidates),
        "scored_count": len(scored),
        "all_count": len(all_view),
        "ranked_count": len(ranking),
        "top7_count": len(top7),
        "edge_guard": {
            "blocked_count": sum(1 for row in scored if row.get("top7_edge_guard_blocked")),
            "ranking_before_guard": len(ranking),
            "ranking_after_guard": len(ranking_for_top7),
        },
        "thinq_service_available": thinq_service is not None,
        "side_safety": {
            "player1_definition": "HOME_API_FIRST_SIDE",
            "player2_definition": "AWAY_API_SECOND_SIDE",
            "pick_definition": "DERIVED_FROM_PICK_SIDE",
        },
        "outputs": {"all": all_paths, "top7": top7_paths, "snapshots": snapshot_paths},
    }
    manifest_paths = save_run_manifest(manifest, run_date=run_date, output_root=output_root)
    manifest["outputs"]["manifest"] = manifest_paths
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CORQ daily runtime")
    parser.add_argument("--input", dest="input_path", default=None, help="Optional path to candidates/matches JSON")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    parser.add_argument("--date", dest="run_date", default=None, help="Run date YYYY-MM-DD")
    args = parser.parse_args()

    manifest = run_daily(input_path=args.input_path, output_root=args.output_root, run_date=args.run_date)
    print("CORQ runtime finished")
    print(f"Candidates: {manifest['candidate_count']}")
    print(f"ALL: {manifest['all_count']}")
    print(f"TOP7: {manifest['top7_count']}")


if __name__ == "__main__":
    main()
