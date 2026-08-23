"""BlinQ symmetric ELO model using only real ELO cache values."""
from __future__ import annotations
import math
from typing import Any, Dict, Optional

MODEL_VERSION = "BLINQ_ELO_SYMMETRIC_V1"
EPSILON = 1e-12


def _number(value: Any) -> Optional[float]:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _surface_key(surface: Optional[str]) -> str:
    token = str(surface or "").strip().lower()
    if "clay" in token:
        return "clay_elo"
    if "grass" in token:
        return "grass_elo"
    if "hard" in token or "indoor" in token or "carpet" in token:
        return "hard_elo"
    return "elo"


def _rating(row: Dict[str, Any], key: str) -> tuple[Optional[float], str, list[str]]:
    value = _number(row.get(key))
    if value is not None:
        return value, key, []
    overall = _number(row.get("elo"))
    if overall is not None and key != "elo":
        return overall, "elo", ["SURFACE_ELO_FALLBACK_OVERALL"]
    return None, key, ["MISSING_ELO"]


def predict_from_elo(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    key = _surface_key(surface)
    rating1, source1, flags1 = _rating(player1, key)
    rating2, source2, flags2 = _rating(player2, key)
    name1 = player1.get("player") or player1.get("name")
    name2 = player2.get("player") or player2.get("name")
    out = {
        "model": "BlinQ", "model_version": MODEL_VERSION,
        "surface": str(surface or "Overall"), "requested_elo_type": key,
        "player1": name1, "player2": name2,
        "player1_elo": rating1, "player2_elo": rating2,
        "player1_elo_type": source1, "player2_elo_type": source2,
        "flags": sorted(set(flags1 + flags2)),
    }
    if rating1 is None or rating2 is None:
        return {**out, "status": "NO_DATA", "winner": None, "winner_side": None,
                "player1_probability": None, "player2_probability": None, "elo_diff": None}
    diff = rating1 - rating2
    probability1 = 1.0 / (1.0 + math.pow(10.0, -diff / 400.0))
    probability2 = 1.0 - probability1
    if abs(probability1 - 0.5) <= EPSILON:
        status, winner, side = "NO_PREDICTION", None, None
    elif probability1 > 0.5:
        status, winner, side = "PREDICTION", name1, "PLAYER1"
    else:
        status, winner, side = "PREDICTION", name2, "PLAYER2"
    return {
        **out, "status": status, "winner": winner, "winner_side": side,
        "player1_probability": round(probability1, 12),
        "player2_probability": round(probability2, 12),
        "player1_probability_pct": round(probability1 * 100.0, 2),
        "player2_probability_pct": round(probability2 * 100.0, 2),
        "elo_diff": round(diff, 2),
    }


def symmetry_audit(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    forward = predict_from_elo(player1, player2, surface)
    reverse = predict_from_elo(player2, player1, surface)
    first = forward.get("player1_probability")
    swapped = reverse.get("player1_probability")
    if first is None or swapped is None:
        return {"ok": None, "error": None, "forward": forward, "reverse": reverse}
    error = abs(float(first) + float(swapped) - 1.0)
    return {"ok": error <= EPSILON, "error": error, "forward": forward, "reverse": reverse}
