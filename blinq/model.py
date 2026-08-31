"""BlinQ private ELO context.

ELO is a real input signal and an anonymized display index. It is never a
standalone BlinQ prediction. Missing surface ELO remains NO DATA and is not
replaced with overall ELO.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

MODEL_VERSION = "BLINQ_ELO_CONTEXT_V3"


def _number(value: Any) -> Optional[float]:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _surface_key(surface: Optional[str]) -> Optional[str]:
    token = str(surface or "").strip().lower()
    if "clay" in token:
        return "clay_elo"
    if "grass" in token:
        return "grass_elo"
    if "hard" in token or "indoor" in token or "carpet" in token:
        return "hard_elo"
    return None


def _pair_index(rating1: Optional[float], rating2: Optional[float], label: str) -> Dict[str, Any]:
    if rating1 is None or rating2 is None:
        return {"available": False, "p1": None, "p2": None, "label": label}
    p1 = 100.0 / (1.0 + math.pow(10.0, -(rating1 - rating2) / 400.0))
    return {"available": True, "p1": round(p1, 1), "p2": round(100.0 - p1, 1), "label": label}


def build_elo_context(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    surface_key = _surface_key(surface)
    overall1, overall2 = _number(player1.get("elo")), _number(player2.get("elo"))
    surface1 = _number(player1.get(surface_key)) if surface_key else None
    surface2 = _number(player2.get(surface_key)) if surface_key else None
    indices = {
        "strength": _pair_index(overall1, overall2, "E-INDEX"),
        "surface_strength": _pair_index(surface1, surface2, "SE-INDEX"),
    }
    flags = []
    if overall1 is None or overall2 is None:
        flags.append("MISSING_ELO")
    if surface_key and (surface1 is None or surface2 is None):
        flags.append("MISSING_SURFACE_ELO")
    return {
        "model": "BlinQ",
        "model_version": MODEL_VERSION,
        "status": "OK" if indices["strength"]["available"] else "NO_DATA",
        "prediction_status": "NO_PREDICTION",
        "winner": None,
        "winner_side": None,
        "player1_probability": None,
        "player2_probability": None,
        "surface": str(surface or "Overall"),
        "requested_elo_type": surface_key or "elo",
        "indices": indices,
        "flags": flags,
        "standalone_prediction_allowed": False,
    }


def predict_from_elo(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    """Compatibility entrypoint. ELO-only output is always NO_PREDICTION."""
    return build_elo_context(player1, player2, surface)


def symmetry_audit(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    forward = build_elo_context(player1, player2, surface)
    reverse = build_elo_context(player2, player1, surface)
    checks = []
    for key in ("strength", "surface_strength"):
        first = forward["indices"][key]
        swapped = reverse["indices"][key]
        if first["available"] and swapped["available"]:
            checks.append(abs(float(first["p1"]) + float(swapped["p1"]) - 100.0) <= 0.2)
    return {"ok": all(checks) if checks else None, "forward": forward, "reverse": reverse}
