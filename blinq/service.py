"""BlinQ service facade."""
from __future__ import annotations

from typing import Any, Dict

from .model import build_blinq_prediction


class BlinqService:
    def __init__(self, *, dead_zone: float = 0.015, min_confidence: float = 0.45) -> None:
        self.dead_zone = dead_zone
        self.min_confidence = min_confidence

    def build_match_prediction(self, thinq_result: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(thinq_result, dict):
            return {
                "model": "BlinQ",
                "model_version": "BLINQ_V1_THINQ_DECISION",
                "status": "NO_PREDICTION",
                "prediction_status": "NO_PREDICTION",
                "winner": None,
                "reasons": ["INVALID_THINQ_INPUT"],
                "source_policy": "THINQ_OUTPUT_ONLY_NO_API_NO_FALLBACK",
            }
        return build_blinq_prediction(
            thinq_result,
            dead_zone=self.dead_zone,
            min_confidence=self.min_confidence,
        )


def build_match_prediction(thinq_result: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    return BlinqService(**kwargs).build_match_prediction(thinq_result)
