"""Canonical side helpers for CORQ/THINQ.

Hard rule:
- player1 is always HOME/API first side
- player2 is always AWAY/API second side
- pick is never treated as a stable identity by itself
- pick is derived from pick_side: HOME or AWAY

This prevents old bugs where ELO, H2H, odds or recent form were calculated for
player1/player2 while the selected pick was actually player2.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

HOME = "HOME"
AWAY = "AWAY"


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def side_from_pick(player1: Any, player2: Any, pick: Any) -> Optional[str]:
    pick_key = normalize_name(pick)
    if not pick_key:
        return None
    if pick_key == normalize_name(player1):
        return HOME
    if pick_key == normalize_name(player2):
        return AWAY
    return None


def derive_side_record(match: Dict[str, Any], pick_side: str) -> Dict[str, Any]:
    """Return a candidate record derived from canonical HOME/AWAY side.

    The input match may contain legacy pick/opponent fields, but this function
    ignores them and derives pick/opponent from player1/player2 + pick_side.
    """
    side = str(pick_side or "").upper().strip()
    if side not in {HOME, AWAY}:
        raise ValueError(f"Invalid pick_side: {pick_side}")

    player1 = match.get("player1") or match.get("home_player") or match.get("home") or match.get("homeTeam")
    player2 = match.get("player2") or match.get("away_player") or match.get("away") or match.get("awayTeam")
    if not player1 or not player2:
        raise ValueError("Missing player1/player2 for side derivation")

    home_odds = match.get("odds_player1") or match.get("p1_odds") or match.get("home_odds") or match.get("odds1") or match.get("price1")
    away_odds = match.get("odds_player2") or match.get("p2_odds") or match.get("away_odds") or match.get("odds2") or match.get("price2")

    if side == HOME:
        pick = str(player1)
        opponent = str(player2)
        pick_odds = home_odds
        opponent_odds = away_odds
        opponent_side = AWAY
        orientation = "PICK_IS_PLAYER1_HOME"
        pick_is_player1 = True
        pick_is_player2 = False
    else:
        pick = str(player2)
        opponent = str(player1)
        pick_odds = away_odds
        opponent_odds = home_odds
        opponent_side = HOME
        orientation = "PICK_IS_PLAYER2_AWAY"
        pick_is_player1 = False
        pick_is_player2 = True

    out = dict(match)
    out.update(
        {
            "player1": str(player1),
            "player2": str(player2),
            "home_player": str(player1),
            "away_player": str(player2),
            "pick_side": side,
            "opponent_side": opponent_side,
            "pick": pick,
            "opponent": opponent,
            "odds": pick_odds,
            "pick_odds": pick_odds,
            "opponent_odds": opponent_odds,
            "pick_is_player1": pick_is_player1,
            "pick_is_player2": pick_is_player2,
            "pick_is_home": side == HOME,
            "pick_is_away": side == AWAY,
            "side_orientation": orientation,
            "side_locked": True,
        }
    )
    out["side_audit"] = build_side_audit(out)
    return out


def build_side_audit(record: Dict[str, Any]) -> Dict[str, Any]:
    player1 = record.get("player1")
    player2 = record.get("player2")
    pick = record.get("pick")
    opponent = record.get("opponent")
    pick_side = str(record.get("pick_side") or "").upper().strip() or side_from_pick(player1, player2, pick)
    if pick_side == HOME:
        expected_pick = player1
        expected_opponent = player2
        orientation = "PICK_IS_PLAYER1_HOME"
    elif pick_side == AWAY:
        expected_pick = player2
        expected_opponent = player1
        orientation = "PICK_IS_PLAYER2_AWAY"
    else:
        expected_pick = None
        expected_opponent = None
        orientation = "UNKNOWN_PICK_SIDE"

    pick_matches_expected = normalize_name(pick) == normalize_name(expected_pick)
    opponent_matches_expected = normalize_name(opponent) == normalize_name(expected_opponent)
    return {
        "player1_home": player1,
        "player2_away": player2,
        "pick": pick,
        "opponent": opponent,
        "pick_side": pick_side,
        "opponent_side": AWAY if pick_side == HOME else HOME if pick_side == AWAY else None,
        "pick_is_player1": pick_side == HOME,
        "pick_is_player2": pick_side == AWAY,
        "pick_is_home": pick_side == HOME,
        "pick_is_away": pick_side == AWAY,
        "orientation": orientation,
        "expected_pick_from_side": expected_pick,
        "expected_opponent_from_side": expected_opponent,
        "pick_matches_expected_side": pick_matches_expected,
        "opponent_matches_expected_side": opponent_matches_expected,
        "side_valid": bool(pick_matches_expected and opponent_matches_expected),
    }


def repair_candidate_side(record: Dict[str, Any]) -> Dict[str, Any]:
    """Repair/normalize a candidate so pick/opponent always follows pick_side.

    If pick_side is missing, infer from pick. If inference fails, keep row but
    add side_valid=False in audit. This is intentionally broad and audit-friendly.
    """
    pick_side = str(record.get("pick_side") or "").upper().strip()
    if pick_side not in {HOME, AWAY}:
        inferred = side_from_pick(record.get("player1"), record.get("player2"), record.get("pick"))
        pick_side = inferred or pick_side
    if pick_side in {HOME, AWAY}:
        return derive_side_record(record, pick_side)
    out = dict(record)
    out["side_locked"] = False
    out["side_audit"] = build_side_audit(out)
    return out
