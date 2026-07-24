"""Candidate builder for CORQ.

CORQ must choose a side. It must not blindly use player1 as the pick.
This module expands one normalized match into one or two pick candidates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def build_pick_candidates(match: Dict[str, Any]) -> List[Dict[str, Any]]:
    player1 = match.get("player1")
    player2 = match.get("player2")
    p1_odds = to_float(match.get("odds_player1") or match.get("p1_odds") or match.get("home_odds"))
    p2_odds = to_float(match.get("odds_player2") or match.get("p2_odds") or match.get("away_odds"))

    candidates: List[Dict[str, Any]] = []

    if player1 and player2 and (p1_odds is not None or p2_odds is not None):
        c1 = dict(match)
        c1.update({
            "pick": player1,
            "opponent": player2,
            "pick_side": "player1",
            "pick_odds": p1_odds,
            "opponent_odds": p2_odds,
            "odds": p1_odds,
        })
        candidates.append(c1)

        c2 = dict(match)
        c2.update({
            "pick": player2,
            "opponent": player1,
            "pick_side": "player2",
            "pick_odds": p2_odds,
            "opponent_odds": p1_odds,
            "odds": p2_odds,
        })
        candidates.append(c2)
        return candidates

    # Fallback if odds are still missing: keep current orientation, but this will be rejected from CORQ ranking.
    fallback = dict(match)
    fallback.setdefault("pick", player1)
    fallback.setdefault("opponent", player2)
    fallback.setdefault("pick_side", "player1")
    candidates.append(fallback)
    return candidates
