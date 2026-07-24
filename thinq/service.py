"""THINQ service.

Broad runtime version focused on ELO + H2H.
THINQ remains an intelligence layer. It returns edges, confidence and flags.
CORQ remains responsible for final ranking and TOP outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from thinq.loaders.elo_loader import build_elo_context
from thinq.loaders.h2h_loader import build_h2h_context


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
        player1_id: Optional[Any] = None,
        player2_id: Optional[Any] = None,
        tournament_id: Optional[Any] = None,
        best_of: int = 3,
        save_snapshot: bool = False,
        pick: Optional[str] = None,
        opponent: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        analysis_pick = pick or player1
        analysis_opponent = opponent or (player2 if analysis_pick == player1 else player1)
        surface_ctx = normalize_surface(surface)
        elo = build_elo_context(analysis_pick, analysis_opponent, surface_ctx.get("surface") or surface)
        h2h = build_h2h_context(
            event_id=event_id,
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_ctx.get("surface") or surface,
            player1_id=player1_id,
            player2_id=player2_id,
        )
        edges = {
            "elo_edge": float(elo.get("elo_edge") or 0.0),
            "h2h_edge": float(h2h.get("edge") or 0.0),
        }
        flags: List[str] = []
        flags.extend(surface_ctx.get("flags") or [])
        flags.extend(elo.get("flags") or [])
        if h2h.get("status") != "OK":
            flags.append("NO_H2H_DATA")
        data_score = 0.25
        if elo.get("status") == "OK":
            data_score += 0.45
        if h2h.get("status") == "OK":
            data_score += 0.15
        if surface_ctx.get("surface") != "Unknown":
            data_score += 0.05
        confidence = round(max(min(data_score, 0.85), 0.0), 4)
        return {
            "available": True,
            "error": None,
            "confidence": confidence,
            "surface": surface_ctx,
            "elo": elo,
            "h2h": {
                "status": h2h.get("status"),
                "source": h2h.get("source"),
                "total_matches": h2h.get("total_matches", 0),
                "pick_wins": h2h.get("pick_wins", 0),
                "opponent_wins": h2h.get("opponent_wins", 0),
                "edge": h2h.get("edge", 0.0),
                "confidence": h2h.get("confidence", 0.0),
                "reason": h2h.get("reason"),
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
            "thinq_elo_edge": edges["elo_edge"],
            "thinq_h2h_status": h2h.get("status"),
            "thinq_h2h_source": h2h.get("source"),
            "thinq_h2h_total_matches": h2h.get("total_matches", 0),
            "thinq_h2h_edge": edges["h2h_edge"],
            "thinq_h2h_confidence": h2h.get("confidence", 0.0),
            "thinq_flags": sorted(set(flags)),
        }


# Compatibility alias for old imports.
def build_match_features(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return ThinqService().build_match_features(*args, **kwargs)
