"""
THINQ Schedule / Fatigue Context

Uses History matches when available to estimate recent load:
- matches in last 7 days
- played yesterday

Set counts are left as None until a reliable score/set datasource is connected.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ["%Y%m%d", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text[:10], fmt)
        except Exception:
            continue
    return None


def _recent_matches(history: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Future-proof: if sackmann loader later exposes recent_matches, this module will use them.
    matches = history.get("recent_matches")
    return matches if isinstance(matches, list) else []


def _build_player_load(history: Dict[str, Any], as_of_date: Optional[str]) -> Dict[str, Any]:
    matches = _recent_matches(history)
    anchor = _parse_date(as_of_date) or datetime.utcnow()
    cutoff = anchor - timedelta(days=7)
    yesterday = anchor - timedelta(days=1)

    matches_last_7d = 0
    played_yesterday = False
    for match in matches:
        dt = _parse_date(match.get("date"))
        if not dt:
            continue
        if cutoff <= dt <= anchor:
            matches_last_7d += 1
        if dt.date() == yesterday.date():
            played_yesterday = True

    return {
        "matches_last_7d": matches_last_7d,
        "sets_last_7d": None,
        "played_yesterday": played_yesterday,
    }


def build_fatigue_context(raw: Dict[str, Any], as_of_date: Optional[str] = None) -> Dict[str, Any]:
    p1 = raw.get("player1", {}) if isinstance(raw.get("player1"), dict) else {}
    p2 = raw.get("player2", {}) if isinstance(raw.get("player2"), dict) else {}
    p1_hist = p1.get("history", p1.get("History", {}))
    p2_hist = p2.get("history", p2.get("History", {}))

    p1_load = _build_player_load(p1_hist, as_of_date)
    p2_load = _build_player_load(p2_hist, as_of_date)

    diff = p2_load["matches_last_7d"] - p1_load["matches_last_7d"]
    fatigue_edge = max(min(diff * 0.01, 0.04), -0.04)

    if p1_load["played_yesterday"] and not p2_load["played_yesterday"]:
        fatigue_edge -= 0.01
    elif p2_load["played_yesterday"] and not p1_load["played_yesterday"]:
        fatigue_edge += 0.01

    flags = []
    if p1_load["matches_last_7d"] >= 4:
        flags.append("PLAYER1_HIGH_RECENT_LOAD")
    if p2_load["matches_last_7d"] >= 4:
        flags.append("PLAYER2_HIGH_RECENT_LOAD")
    if p1_load["played_yesterday"]:
        flags.append("PLAYER1_PLAYED_YESTERDAY")
    if p2_load["played_yesterday"]:
        flags.append("PLAYER2_PLAYED_YESTERDAY")

    return {
        "fatigue_edge": round(fatigue_edge, 4),
        "player1_load": p1_load,
        "player2_load": p2_load,
        "flags": flags,
    }
