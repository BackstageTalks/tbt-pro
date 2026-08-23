"""BlinQ decision layer.

BlinQ consumes an already calculated ThinQ result. It does not call external
APIs and does not fabricate missing values.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

MODEL_VERSION = "BLINQ_V1_THINQ_DECISION"
DEFAULT_DEAD_ZONE = 0.015
DEFAULT_MIN_CONFIDENCE = 0.45


def _float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _probability_layer(thinq: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("thinq_probability_layer", "probability_layer"):
        value = thinq.get(key)
        if isinstance(value, dict):
            return value
    nested = _dict(thinq.get("thinq"))
    for key in ("thinq_probability_layer", "probability_layer"):
        value = nested.get(key)
        if isinstance(value, dict):
            return value
    return thinq


def build_blinq_prediction(
    thinq: Dict[str, Any],
    *,
    dead_zone: float = DEFAULT_DEAD_ZONE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> Dict[str, Any]:
    layer = _probability_layer(thinq)
    pick = layer.get("pick") or thinq.get("pick")
    opponent = layer.get("opponent") or thinq.get("opponent")
    pick_probability = _float(layer.get("pick_probability"))
    opponent_probability = _float(layer.get("opponent_probability"))
    confidence = _float(layer.get("confidence"), _float(thinq.get("thinq_data_confidence"), 0.0)) or 0.0
    symmetry = _dict(layer.get("symmetry_audit") or thinq.get("thinq_symmetry_audit"))
    flags = {str(x) for x in (layer.get("flags") or thinq.get("flags") or []) if x}

    reasons = []
    if not pick or not opponent:
        reasons.append("MISSING_PLAYER_IDENTITY")
    if pick_probability is None or opponent_probability is None:
        reasons.append("MISSING_THINQ_PROBABILITY")
    elif abs((pick_probability + opponent_probability) - 1.0) > 0.0001:
        reasons.append("PROBABILITY_NOT_COMPLEMENTARY")
    if symmetry.get("status") != "PASS":
        reasons.append("SYMMETRY_AUDIT_FAILED")
    if confidence < min_confidence:
        reasons.append("LOW_DATA_CONFIDENCE")

    exact_tie = pick_probability == 0.50 and opponent_probability == 0.50
    if exact_tie:
        reasons.append("EXACT_50_50")

    edge = None if pick_probability is None else round(pick_probability - 0.50, 4)
    in_dead_zone = edge is not None and abs(edge) < max(0.0, float(dead_zone))
    if in_dead_zone and not exact_tie:
        reasons.append("DEAD_ZONE")

    prediction_allowed = not reasons
    if prediction_allowed:
        pick_is_winner = bool(pick_probability > opponent_probability)
        winner = pick if pick_is_winner else opponent
        winner_side = layer.get("pick_side") if pick_is_winner else layer.get("opponent_side")
        winner_probability = max(pick_probability, opponent_probability)
        status = "PREDICTION"
    else:
        winner = None
        winner_side = None
        winner_probability = 0.50 if exact_tie else None
        status = "NO_PREDICTION"

    return {
        "model": "BlinQ",
        "model_version": MODEL_VERSION,
        "status": status,
        "prediction_status": status,
        "pick": pick,
        "pick_side": layer.get("pick_side"),
        "opponent": opponent,
        "opponent_side": layer.get("opponent_side"),
        "pick_probability": pick_probability,
        "opponent_probability": opponent_probability,
        "winner": winner,
        "winner_side": winner_side,
        "winner_probability": winner_probability,
        "confidence": round(confidence, 4),
        "data_quality": "LOW" if confidence < min_confidence else "OK",
        "edge": edge,
        "dead_zone": round(float(dead_zone), 4),
        "in_dead_zone": bool(in_dead_zone),
        "symmetry_audit": symmetry,
        "symmetry_status": symmetry.get("status") or "MISSING",
        "reasons": sorted(set(reasons)),
        "flags": sorted(flags),
        "source_policy": "THINQ_OUTPUT_ONLY_NO_API_NO_FALLBACK",
    }
