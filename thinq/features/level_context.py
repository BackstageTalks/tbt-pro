"""
THINQ Level Context

Compares current/recent level context. This is conservative until richer level history is available.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

LEVEL_SCORE = {
    "G": 1.00,
    "GRAND SLAM": 1.00,
    "M": 0.90,
    "MASTERS": 0.90,
    "WTA1000": 0.90,
    "ATP500": 0.75,
    "WTA500": 0.75,
    "A": 0.65,
    "ATP250": 0.65,
    "WTA250": 0.65,
    "C": 0.45,
    "CHALLENGER": 0.45,
    "F": 0.25,
    "ITF": 0.25,
}


def _score(level: Optional[str]) -> Optional[float]:
    if not level:
        return None
    key = str(level).strip().upper()
    return LEVEL_SCORE.get(key)


def build_level_context(raw: Dict[str, Any], level: Optional[str]) -> Dict[str, Any]:
    p1 = raw.get("player1", {}) if isinstance(raw.get("player1"), dict) else {}
    p2 = raw.get("player2", {}) if isinstance(raw.get("player2"), dict) else {}
    p1_hist = p1.get("history", p1.get("History", {}))
    p2_hist = p2.get("history", p2.get("History", {}))

    current_score = _score(level)
    p1_level = p1_hist.get("recent_level") or p1_hist.get("level")
    p2_level = p2_hist.get("recent_level") or p2_hist.get("level")
    p1_score = _score(p1_level)
    p2_score = _score(p2_level)

    edge = 0.0
    if p1_score is not None and p2_score is not None:
        edge = max(min((p1_score - p2_score) * 0.04, 0.04), -0.04)

    flags = []
    if current_score is not None and p1_score is not None and p1_score + 0.25 < current_score:
        flags.append("PLAYER1_LEVEL_JUMP")
    if current_score is not None and p2_score is not None and p2_score + 0.25 < current_score:
        flags.append("PLAYER2_LEVEL_JUMP")

    return {
        "level_context_edge": round(edge, 4),
        "current_level": level,
        "player1_recent_level": p1_level,
        "player2_recent_level": p2_level,
        "flags": flags,
    }
