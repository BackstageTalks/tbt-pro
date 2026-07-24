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
        elo = build_elo_context(analysis_pick, analysis_opponent, surface_bucket)
        h2h = build_h2h_context(
            event_id=event_id,
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            player1_id=player1_id,
            player2_id=player2_id,
            event_custom_id=event_custom_id,
        )
        recent_form = build_recent_form_context(analysis_pick, analysis_opponent, surface_bucket)
        match_dynamics = build_match_dynamics_context(
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            best_of=best_of,
            elo=elo,
            h2h=h2h,
            recent_form=recent_form,
            odds_player1=kwargs.get("odds_player1") or kwargs.get("p1_odds") or kwargs.get("odds1"),
            odds_player2=kwargs.get("odds_player2") or kwargs.get("p2_odds") or kwargs.get("odds2"),
            pick_odds=kwargs.get("pick_odds") or kwargs.get("odds"),
            opponent_odds=kwargs.get("opponent_odds"),
        )

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
            "contexts": {
                "match_dynamics": match_dynamics,
                "h2h": h2h,
                "recent_form": recent_form,
                "elo": elo,
            },
            "edges": edges,
            "flags": sorted(set(flags)),
            "thinq_available": True,
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
            "thinq_flags": sorted(set(flags)),
        }


def build_match_features(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return ThinqService().build_match_features(*args, **kwargs)
