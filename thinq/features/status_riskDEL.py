"""
THINQ Status Risk

Keeps status risk separate from prediction.
Uses player/status fields if API loaders later provide them.
"""

from __future__ import annotations

from typing import Any, Dict

RISKY_STATUS = {"retired", "withdrawn", "walkover", "inactive", "injury", "medical"}


def _status(player: Dict[str, Any]) -> str:
    for layer_name in ["ta", "taq", "history", "History", "elo", "eloq"]:
        layer = player.get(layer_name)
        if isinstance(layer, dict):
            value = layer.get("status") or layer.get("player_status") or layer.get("last_match_status")
            if value:
                return str(value).strip().lower()
    return ""


def build_status_risk(raw: Dict[str, Any]) -> Dict[str, Any]:
    p1 = raw.get("player1", {}) if isinstance(raw.get("player1"), dict) else {}
    p2 = raw.get("player2", {}) if isinstance(raw.get("player2"), dict) else {}
    p1_status = _status(p1)
    p2_status = _status(p2)

    p1_risk = any(token in p1_status for token in RISKY_STATUS)
    p2_risk = any(token in p2_status for token in RISKY_STATUS)

    # Positive favors player1, so player2 risk is positive edge.
    edge = 0.0
    if p1_risk and not p2_risk:
        edge = -0.03
    elif p2_risk and not p1_risk:
        edge = 0.03

    flags = []
    if p1_risk:
        flags.append("PLAYER1_STATUS_RISK")
    if p2_risk:
        flags.append("PLAYER2_STATUS_RISK")

    return {
        "status_risk_edge": round(edge, 4),
        "player1_status": p1_status or None,
        "player2_status": p2_status or None,
        "flags": flags,
    }
