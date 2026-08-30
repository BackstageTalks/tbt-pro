"""BlinQ private ELO model and public anonymized index contract.

Raw ratings remain internal to BlinQ. Public consumers receive rounded strength
indices and source-depth metadata, never raw ELO values or rating differences.
"""
from __future__ import annotations
import math
from typing import Any, Dict, Optional

MODEL_VERSION = "BLINQ_PRIVATE_INDEX_MODEL_V2"
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


def _round_index(value: float, low: int = 5, high: int = 95) -> int:
    return max(low, min(high, int(round(value / 5.0) * 5)))


def _pair_index(rating1: Optional[float], rating2: Optional[float], label: str) -> Dict[str, Any]:
    if rating1 is None or rating2 is None:
        return {"available": False, "p1": None, "p2": None, "label": label}
    probability1 = 1.0 / (1.0 + math.pow(10.0, -(rating1 - rating2) / 400.0))
    p1 = _round_index(probability1 * 100.0)
    return {"available": True, "p1": p1, "p2": 100 - p1, "label": label}


def predict_from_elo(player1: Dict[str, Any], player2: Dict[str, Any], surface: Optional[str] = None) -> Dict[str, Any]:
    requested_key = _surface_key(surface)
    overall1, _, overall_flags1 = _rating(player1, "elo")
    overall2, _, overall_flags2 = _rating(player2, "elo")
    selected1, selected_source1, selected_flags1 = _rating(player1, requested_key)
    selected2, selected_source2, selected_flags2 = _rating(player2, requested_key)
    name1 = player1.get("player") or player1.get("name")
    name2 = player2.get("player") or player2.get("name")
    flags = sorted(set(overall_flags1 + overall_flags2 + selected_flags1 + selected_flags2))

    indices = {
        "strength": _pair_index(overall1, overall2, "E-INDEX"),
        "surface_strength": (
            _pair_index(selected1, selected2, "SE-INDEX")
            if requested_key != "elo" and selected_source1 == requested_key and selected_source2 == requested_key
            else {"available": False, "p1": None, "p2": None, "label": "SE-INDEX"}
        ),
    }
    depth_checks = [overall1 is not None, overall2 is not None]
    if requested_key != "elo":
        depth_checks.extend([selected_source1 == requested_key, selected_source2 == requested_key])
    data_depth = round(sum(depth_checks) / len(depth_checks) * 100.0, 1)

    public = {
        "model": "BlinQ",
        "model_version": MODEL_VERSION,
        "surface": str(surface or "Overall"),
        "requested_elo_type": requested_key,
        "player1": name1,
        "player2": name2,
        "indices": indices,
        "elo_data_depth": data_depth,
        "flags": flags,
    }
    if selected1 is None or selected2 is None:
        return {**public, "status": "NO_DATA", "winner": None, "winner_side": None,
                "player1_probability": None, "player2_probability": None}

    diff = selected1 - selected2
    probability1 = 1.0 / (1.0 + math.pow(10.0, -diff / 400.0))
    probability2 = 1.0 - probability1
    if abs(probability1 - 0.5) <= EPSILON:
        status, winner, side = "NO_PREDICTION", None, None
    elif probability1 > 0.5:
        status, winner, side = "PREDICTION", name1, "PLAYER1"
    else:
        status, winner, side = "PREDICTION", name2, "PLAYER2"
    return {
        **public,
        "status": status,
        "winner": winner,
        "winner_side": side,
        "player1_probability": round(probability1, 12),
        "player2_probability": round(probability2, 12),
        "player1_probability_pct": round(probability1 * 100.0, 2),
        "player2_probability_pct": round(probability2 * 100.0, 2),
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
