"""
THINQ Surface Transition Context

Detects risk when recent surface context differs from current surface.
Requires recent_matches in History data when available.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _norm(surface: Optional[str]) -> Optional[str]:
    if not surface:
        return None
    value = str(surface).strip().lower()
    mapping = {"i.hard": "indoor hard", "indoor": "indoor hard"}
    return mapping.get(value, value)


def _last_surface(history: Dict[str, Any]) -> Optional[str]:
    matches = history.get("recent_matches")
    if not isinstance(matches, list) or not matches:
        return None
    return _norm(matches[0].get("surface"))


def build_surface_transition_context(raw: Dict[str, Any], surface: Optional[str]) -> Dict[str, Any]:
    current = _norm(surface)
    p1 = raw.get("player1", {}) if isinstance(raw.get("player1"), dict) else {}
    p2 = raw.get("player2", {}) if isinstance(raw.get("player2"), dict) else {}
    p1_hist = p1.get("history", p1.get("History", {}))
    p2_hist = p2.get("history", p2.get("History", {}))

    p1_prev = _last_surface(p1_hist)
    p2_prev = _last_surface(p2_hist)

    p1_risk = 1 if current and p1_prev and current != p1_prev else 0
    p2_risk = 1 if current and p2_prev and current != p2_prev else 0

    # Positive edge favors player1, so if player2 has transition risk edge is positive.
    edge = (p2_risk - p1_risk) * 0.015

    flags = []
    if p1_risk:
        flags.append("PLAYER1_SURFACE_TRANSITION")
    if p2_risk:
        flags.append("PLAYER2_SURFACE_TRANSITION")

    return {
        "surface_transition_edge": round(edge, 4),
        "player1_previous_surface": p1_prev,
        "player2_previous_surface": p2_prev,
        "current_surface": current,
        "flags": flags,
    }
