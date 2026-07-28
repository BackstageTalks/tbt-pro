"""THINQ service with side-orientation audit.

THINQ is always calculated for pick/opponent.
player1 and player2 are kept as canonical HOME/AWAY input fields only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from corq.sides import build_side_audit

try:
    from thinq.loaders.elo_loader import build_elo_context
except Exception:
    def build_elo_context(pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
        return {"status": "NO_DATA", "selected_elo_type": None, "elo_edge": 0.0, "flags": ["MISSING_ELO"]}

try:
    from thinq.loaders.h2h_loader import build_h2h_context
except Exception:
    def build_h2h_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "NO_DATA", "source": "none", "total_matches": 0, "pick_wins": 0, "opponent_wins": 0, "edge": 0.0, "confidence": 0.0, "reason": "H2H loader unavailable"}

try:
    from thinq.features.recent_form import build_recent_form_context
except Exception:
    def build_recent_form_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "NO_DATA", "flags": ["RECENT_FORM_NO_DATA"], "recent_form_edge": 0.0, "short_form_edge": 0.0, "surface_recent_form_edge": 0.0, "opponent_quality_edge": 0.0, "form_confidence": 0.0}

try:
    from thinq.features.match_dynamics import build_match_dynamics_context
except Exception:
    def build_match_dynamics_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {
            "status": "NO_DATA",
            "source": None,
            "projected_sets": None,
            "projected_games": None,
            "tiebreak_probability": None,
            "decider_probability": None,
            "straight_sets_probability": None,
            "sets_edge": 0.0,
            "games_edge": 0.0,
            "confidence": 0.0,
            "flags": ["MATCH_DYNAMICS_UNAVAILABLE"],
        }


try:
    from thinq.loaders.ta_profile_loader import build_match_ta_context
except Exception:
    def build_match_ta_context(pick: str, opponent: str, surface: str = "") -> Dict[str, Any]:
        return {
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
            "ta_sets_decision": "N/A",
            "ta_games_decision": "N/A",
            "ta_tb_decision": "N/A",
            "ta_serve_return_pattern": "N/A",
            "ta_match_shape": "N/A",
            "ta_depth_label": "N/A",
            "ta_decision_confidence": 0.0,
            "ta_decision_notes": [],
        }

try:
    from thinq.features.probability_layer import build_thinq_probability_layer
except Exception:
    def build_thinq_probability_layer(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        pick = kwargs.get("pick") or ""
        opponent = kwargs.get("opponent") or ""
        return {
            "status": "NO_DATA",
            "model_version": "THINQ_PROBABILITY_UNAVAILABLE",
            "pick": pick,
            "opponent": opponent,
            "pick_probability": 0.50,
            "pick_probability_pct": 50.0,
            "opponent_probability": 0.50,
            "opponent_probability_pct": 50.0,
            "winner": pick,
            "winner_probability": 0.50,
            "winner_probability_pct": 50.0,
            "edge": 0.0,
            "confidence": 0.0,
            "components": {},
            "flags": ["THINQ_PROBABILITY_UNAVAILABLE"],
        }


def _flags_from_context(ctx: Dict[str, Any]) -> List[str]:
    value = ctx.get("flags") if isinstance(ctx, dict) else []
    return [str(x) for x in value if x] if isinstance(value, list) else ([str(value)] if value else [])


def _safe_elo_context(pick: str, opponent: str, surface: Optional[str]) -> Dict[str, Any]:
    try:
        ctx = build_elo_context(pick, opponent, surface)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["ELO_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "selected_elo_type": None,
            "overall_elo_edge": 0.0,
            "surface_elo_edge": 0.0,
            "elo_edge": 0.0,
            "flags": ["ELO_CONTEXT_FAILED", "MISSING_ELO"],
            "error": str(exc),
        }


def _safe_h2h_context(**kwargs: Any) -> Dict[str, Any]:
    try:
        ctx = build_h2h_context(**kwargs)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["H2H_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": "none",
            "total_matches": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "edge": 0.0,
            "confidence": 0.0,
            "reason": "H2H context failed",
            "flags": ["H2H_CONTEXT_FAILED"],
            "error": str(exc),
        }


def _safe_recent_form_context(pick: str, opponent: str, surface: Optional[str], level: Optional[str]) -> Dict[str, Any]:
    try:
        ctx = build_recent_form_context(pick, opponent, surface, level)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["RECENT_FORM_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": None,
            "reason": "Recent form context failed",
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
            "form_data_depth": 0.0,
            "flags": ["RECENT_FORM_CONTEXT_FAILED", "RECENT_FORM_NO_DATA"],
            "history_status": {"status": "ERROR", "match_count": 0, "file_count": 0},
            "error": str(exc),
        }


def _safe_match_dynamics_context(**kwargs: Any) -> Dict[str, Any]:
    try:
        ctx = build_match_dynamics_context(**kwargs)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["MATCH_DYNAMICS_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": None,
            "projected_sets": None,
            "projected_games": None,
            "sets_edge": 0.0,
            "games_edge": 0.0,
            "confidence": 0.0,
            "flags": ["MATCH_DYNAMICS_CONTEXT_FAILED"],
            "error": str(exc),
        }


def _safe_ta_context(pick: str, opponent: str, surface: str = "") -> Dict[str, Any]:
    try:
        ctx = build_match_ta_context(pick, opponent, surface)
        if isinstance(ctx, dict):
            return ctx
    except Exception as exc:
        return {"ta_status": "N/A", "aces_status": "N/A", "ta_decision_confidence": 0.0, "ta_decision_notes": [f"TA_CONTEXT_FAILED: {exc}"]}
    return {"ta_status": "N/A", "aces_status": "N/A", "ta_decision_confidence": 0.0, "ta_decision_notes": ["TA_CONTEXT_NON_DICT"]}


def normalize_surface(surface: Optional[str]) -> Dict[str, Any]:
    raw = str(surface or "").strip()
    text = raw.lower()
    flags: List[str] = []
    if "clay" in text:
        bucket = "Clay"
        elo_type = "clay_elo"
    elif "grass" in text:
        bucket = "Grass"
        elo_type = "grass_elo"
    elif "carpet" in text:
        bucket = "Hard"
        elo_type = "hard_elo"
        flags.append("CARPET_AS_HARD_FALLBACK")
    elif "hard" in text or "indoor" in text:
        bucket = "Hard"
        elo_type = "hard_elo"
    else:
        bucket = "Unknown"
        elo_type = "elo"
        flags.append("SURFACE_UNKNOWN")
    return {
        "surface": bucket,
        "surface_raw": raw or None,
        "surface_environment": None,
        "surface_model_bucket": bucket,
        "surface_source": "match_payload" if raw else "unknown",
        "surface_confidence": "MEDIUM" if raw else "LOW",
        "selected_elo_type": elo_type,
        "flags": flags,
    }


class ThinqService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def build_match_features(
        self,
        player1: str,
        player2: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        tournament_url: Optional[str] = None,
        tour_type: Optional[str] = None,
        as_of_date: Optional[str] = None,
        event_id: Optional[Any] = None,
        event_custom_id: Optional[Any] = None,
        player1_id: Optional[Any] = None,
        player2_id: Optional[Any] = None,
        tournament_id: Optional[Any] = None,
        best_of: int = 3,
        save_snapshot: bool = False,
        pick: Optional[str] = None,
        opponent: Optional[str] = None,
        pick_side: Optional[str] = None,
        opponent_side: Optional[str] = None,
        side_audit: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        analysis_pick = pick or player1
        analysis_opponent = opponent or (player2 if analysis_pick == player1 else player1)
        thinq_side = side_audit or build_side_audit(
            {
                "player1": player1,
                "player2": player2,
                "pick": analysis_pick,
                "opponent": analysis_opponent,
                "pick_side": pick_side,
                "opponent_side": opponent_side,
            }
        )

        raw_payload = kwargs.get("raw") or kwargs.get("match_raw") or kwargs.get("raw_event") or {}
        if not event_custom_id:
            event_custom_id = kwargs.get("event_custom_id") or kwargs.get("custom_id") or kwargs.get("customId")
        if not event_custom_id and isinstance(raw_payload, dict):
            event_custom_id = raw_payload.get("customId") or raw_payload.get("custom_id")

        surface_ctx = normalize_surface(surface)
        surface_bucket = surface_ctx.get("surface") or surface
        elo = _safe_elo_context(analysis_pick, analysis_opponent, surface_bucket)
        h2h = _safe_h2h_context(
            event_id=event_id,
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            player1_id=player1_id,
            player2_id=player2_id,
            event_custom_id=event_custom_id,
        )
        recent_form = _safe_recent_form_context(analysis_pick, analysis_opponent, surface_bucket, level)
        match_dynamics = _safe_match_dynamics_context(
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            best_of=best_of,
            elo=elo,
            h2h=h2h,
            recent_form=recent_form,
            odds_player1=kwargs.get("odds_player1") or kwargs.get("p1_odds") or kwargs.get("odds1") or kwargs.get("home_odds"),
            odds_player2=kwargs.get("odds_player2") or kwargs.get("p2_odds") or kwargs.get("odds2") or kwargs.get("away_odds"),
            pick_odds=kwargs.get("pick_odds") or kwargs.get("odds"),
            opponent_odds=kwargs.get("opponent_odds"),
        )
        ta_context = _safe_ta_context(analysis_pick, analysis_opponent, str(surface_bucket or ""))

        edges = {
            "overall_elo_edge": float(elo.get("overall_elo_edge") or 0.0),
            "surface_elo_edge": float(elo.get("surface_elo_edge") or 0.0),
            "elo_edge": float(elo.get("elo_edge") or 0.0),
            "h2h_edge": float(h2h.get("edge") or 0.0),
            "recent_form_edge": float(recent_form.get("recent_form_edge") or 0.0),
            "short_form_edge": float(recent_form.get("short_form_edge") or 0.0),
            "surface_recent_form_edge": float(recent_form.get("surface_recent_form_edge") or 0.0),
            "opponent_quality_edge": float(recent_form.get("opponent_quality_edge") or 0.0),
            "sets_edge": float(match_dynamics.get("sets_edge") or 0.0),
            "games_edge": float(match_dynamics.get("games_edge") or 0.0),
        }

        flags: List[str] = []
        flags.extend(surface_ctx.get("flags") or [])
        flags.extend(elo.get("flags") or [])
        flags.extend(recent_form.get("flags") or [])
        flags.extend(match_dynamics.get("flags") or [])
        if h2h.get("status") != "OK":
            flags.append("NO_H2H_DATA")
        if recent_form.get("status") != "OK":
            flags.append("RECENT_FORM_NO_DATA")
        if not thinq_side.get("side_valid"):
            flags.append("THINQ_SIDE_ORIENTATION_INVALID")

        confidence = 0.20
        if elo.get("status") == "OK":
            confidence += 0.35
        if h2h.get("status") == "OK":
            confidence += 0.10
        if recent_form.get("status") == "OK":
            confidence += min(float(recent_form.get("form_confidence") or 0.0) * 0.25, 0.18)
        if match_dynamics.get("status") == "OK":
            confidence += min(float(match_dynamics.get("confidence") or 0.0) * 0.08, 0.06)
        if surface_ctx.get("surface") != "Unknown":
            confidence += 0.05
        confidence = round(max(min(confidence, 0.88), 0.0), 4)

        thinq_probability_layer = build_thinq_probability_layer(
            pick=analysis_pick,
            opponent=analysis_opponent,
            pick_side=pick_side,
            opponent_side=opponent_side,
            edges=edges,
            confidence=confidence,
            elo=elo,
            h2h=h2h,
            recent_form=recent_form,
            match_dynamics=match_dynamics,
            flags=flags,
        )

        return {
            "available": True,
            "error": None,
            "confidence": confidence,
            "thinq_side": thinq_side,
            "surface": surface_ctx,
            "elo": elo,
            "h2h": {
                "status": h2h.get("status"),
                "source": h2h.get("source"),
                "total_matches": h2h.get("total_matches", 0),
                "pick_wins": h2h.get("pick_wins", 0),
                "opponent_wins": h2h.get("opponent_wins", 0),
                "pick_win_pct": h2h.get("pick_win_pct"),
                "same_surface_matches": h2h.get("same_surface_matches"),
                "same_surface_pick_wins": h2h.get("same_surface_pick_wins"),
                "edge": h2h.get("edge", 0.0),
                "confidence": h2h.get("confidence", 0.0),
                "reason": h2h.get("reason"),
                "endpoint": h2h.get("endpoint"),
                "params": h2h.get("params"),
                "endpoint_attempts": h2h.get("endpoint_attempts") or [],
                "api_status_code": h2h.get("api_status_code"),
                "api_error": h2h.get("api_error"),
                "cache_path": h2h.get("cache_path"),
                "requested_event_id": h2h.get("requested_event_id"),
                "requested_event_custom_id": h2h.get("requested_event_custom_id"),
                "requested_player1_id": h2h.get("requested_player1_id"),
                "requested_player2_id": h2h.get("requested_player2_id"),
            },
            "recent_form": recent_form,
            "match_dynamics": match_dynamics,
            "thinq_probability_layer": thinq_probability_layer,
            "probability_layer": thinq_probability_layer,
            "contexts": {
                "match_dynamics": match_dynamics,
                "h2h": h2h,
                "recent_form": recent_form,
                "elo": elo,
                "thinq_probability_layer": thinq_probability_layer,
                "ta_context": ta_context,
            },
            "edges": edges,
            "flags": sorted(set(flags)),
            "thinq_available": True,
            "thinq_probability_status": thinq_probability_layer.get("status"),
            "thinq_model_version": thinq_probability_layer.get("model_version"),
            "thinq_probability": thinq_probability_layer.get("pick_probability"),
            "thinq_probability_pct": thinq_probability_layer.get("pick_probability_pct"),
            "thinq_winner": thinq_probability_layer.get("winner"),
            "thinq_winner_side": thinq_probability_layer.get("winner_side"),
            "thinq_winner_probability": thinq_probability_layer.get("winner_probability"),
            "thinq_winner_probability_pct": thinq_probability_layer.get("winner_probability_pct"),
            "thinq_edge": thinq_probability_layer.get("edge"),
            "thinq_probability_confidence": thinq_probability_layer.get("confidence"),
            "thinq_probability_components": thinq_probability_layer.get("components"),
            "thinq_confidence": confidence,
            "thinq_selected_elo_type": elo.get("selected_elo_type"),
            "thinq_elo_pick": elo.get("pick_elo"),
            "thinq_elo_opponent": elo.get("opponent_elo"),
            "thinq_yelo_pick": elo.get("pick_yelo"),
            "thinq_yelo_opponent": elo.get("opponent_yelo"),
            "thinq_overall_elo_edge": edges["overall_elo_edge"],
            "thinq_surface_elo_edge": edges["surface_elo_edge"],
            "thinq_elo_edge": edges["elo_edge"],
            "thinq_h2h_status": h2h.get("status"),
            "thinq_h2h_source": h2h.get("source"),
            "thinq_h2h_total_matches": h2h.get("total_matches", 0),
            "thinq_h2h_pick_wins": h2h.get("pick_wins", 0),
            "thinq_h2h_opponent_wins": h2h.get("opponent_wins", 0),
            "thinq_h2h_same_surface_matches": h2h.get("same_surface_matches", 0),
            "thinq_surface_h2h_pick_wins": h2h.get("same_surface_pick_wins", 0),
            "thinq_surface_h2h_opponent_wins": h2h.get("same_surface_opponent_wins", None),
            "thinq_h2h_edge": edges["h2h_edge"],
            "thinq_h2h_confidence": h2h.get("confidence", 0.0),
            "thinq_h2h_endpoint": h2h.get("endpoint"),
            "thinq_h2h_params": h2h.get("params"),
            "thinq_h2h_endpoint_attempts": h2h.get("endpoint_attempts") or [],
            "thinq_h2h_api_status_code": h2h.get("api_status_code"),
            "thinq_h2h_api_error": h2h.get("api_error"),
            "thinq_h2h_cache_path": h2h.get("cache_path"),
            "thinq_h2h_requested_event_id": h2h.get("requested_event_id"),
            "thinq_h2h_requested_event_custom_id": h2h.get("requested_event_custom_id"),
            "thinq_recent_form_edge": edges["recent_form_edge"],
            "thinq_short_form_edge": edges["short_form_edge"],
            "thinq_surface_recent_form_edge": edges["surface_recent_form_edge"],
            "thinq_opponent_quality_edge": edges["opponent_quality_edge"],
            "thinq_sets_edge": edges["sets_edge"],
            "thinq_games_edge": edges["games_edge"],
            "thinq_projected_sets": match_dynamics.get("projected_sets"),
            "thinq_projected_games": match_dynamics.get("projected_games"),
            "thinq_tiebreak_probability": match_dynamics.get("tiebreak_probability"),
            "thinq_decider_probability": match_dynamics.get("decider_probability"),
            "thinq_straight_sets_probability": match_dynamics.get("straight_sets_probability"),
            "thinq_match_shape": match_dynamics.get("match_shape"),
            "thinq_match_dynamics_confidence": match_dynamics.get("confidence", 0.0),
            "thinq_form_confidence": recent_form.get("form_confidence", 0.0),
            "ta_context": ta_context,
            "thinq_ta_context": ta_context,
            "ta_status": ta_context.get("ta_status"),
            "ta_pick_status": ta_context.get("ta_pick_status"),
            "ta_opp_status": ta_context.get("ta_opp_status"),
            "ta_pick_set_pct": ta_context.get("ta_pick_set_pct"),
            "ta_opp_set_pct": ta_context.get("ta_opp_set_pct"),
            "ta_pick_game_pct": ta_context.get("ta_pick_game_pct"),
            "ta_opp_game_pct": ta_context.get("ta_opp_game_pct"),
            "ta_pick_tb_split": ta_context.get("ta_pick_tb_split"),
            "ta_opp_tb_split": ta_context.get("ta_opp_tb_split"),
            "ta_pick_ace_pct": ta_context.get("ta_pick_ace_pct"),
            "ta_opp_ace_pct": ta_context.get("ta_opp_ace_pct"),
            "ta_pick_surface_dr": ta_context.get("ta_pick_surface_dr"),
            "ta_opp_surface_dr": ta_context.get("ta_opp_surface_dr"),
            "ta_pick_rpw_pct": ta_context.get("ta_pick_rpw_pct"),
            "ta_opp_rpw_pct": ta_context.get("ta_opp_rpw_pct"),
            "ta_pick_depth": ta_context.get("ta_pick_depth"),
            "ta_opp_depth": ta_context.get("ta_opp_depth"),
            "pick_aces_line": ta_context.get("pick_aces_line"),
            "opponent_aces_line": ta_context.get("opponent_aces_line"),
            "total_aces_line": ta_context.get("total_aces_line"),
            "aces_status": ta_context.get("aces_status"),
            "ta_scope": ta_context.get("ta_scope"),
            "ta_surface": ta_context.get("ta_surface"),
            "ta_pick_hold_pct": ta_context.get("ta_pick_hold_pct"),
            "ta_opp_hold_pct": ta_context.get("ta_opp_hold_pct"),
            "ta_pick_break_pct": ta_context.get("ta_pick_break_pct"),
            "ta_opp_break_pct": ta_context.get("ta_opp_break_pct"),
            "ta_pick_spw_pct": ta_context.get("ta_pick_spw_pct"),
            "ta_opp_spw_pct": ta_context.get("ta_opp_spw_pct"),
            "ta_pick_tpw_pct": ta_context.get("ta_pick_tpw_pct"),
            "ta_opp_tpw_pct": ta_context.get("ta_opp_tpw_pct"),
            "ta_pick_matches": ta_context.get("ta_pick_matches"),
            "ta_opp_matches": ta_context.get("ta_opp_matches"),
            "ta_winner_decision": ta_context.get("ta_winner_decision"),
            "ta_winner_read": ta_context.get("ta_winner_decision"),
            "ta_sets_decision": ta_context.get("ta_sets_decision"),
            "ta_games_decision": ta_context.get("ta_games_decision"),
            "ta_tb_decision": ta_context.get("ta_tb_decision"),
            "ta_projected_sets": ta_context.get("ta_projected_sets"),
            "ta_projected_games": ta_context.get("ta_projected_games"),
            "ta_straight_sets_probability": ta_context.get("ta_straight_sets_probability"),
            "ta_decider_probability": ta_context.get("ta_decider_probability"),
            "ta_tiebreak_probability": ta_context.get("ta_tiebreak_probability"),
            "ta_score_projection": ta_context.get("ta_score_projection"),
            "ta_sets_model_status": ta_context.get("ta_sets_model_status"),
            "ta_serve_return_pattern": ta_context.get("ta_serve_return_pattern"),
            "ta_match_shape": ta_context.get("ta_match_shape"),
            "ta_depth_label": ta_context.get("ta_depth_label"),
            "ta_decision_confidence": ta_context.get("ta_decision_confidence"),
            "ta_decision_notes": ta_context.get("ta_decision_notes") or [],
            "thinq_flags": sorted(set(flags)),
            "thinq_source_status": {
                "elo": elo.get("status"),
                "h2h": h2h.get("status"),
                "recent_form": recent_form.get("status"),
                "match_dynamics": match_dynamics.get("status"),
                "ta": ta_context.get("ta_status"),
                "history_match_count": (recent_form.get("history_status") or {}).get("match_count") if isinstance(recent_form.get("history_status"), dict) else None,
                "history_file_count": (recent_form.get("history_status") or {}).get("file_count") if isinstance(recent_form.get("history_status"), dict) else None,
            },
        }


def build_match_features(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return ThinqService().build_match_features(*args, **kwargs)
