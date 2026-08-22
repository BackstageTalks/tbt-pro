"""BlinQ service consuming completed ThinQ contexts without API calls."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from .model import COMPONENTS, audit_blinq_symmetry, build_blinq_prediction

EDGE_KEYS = tuple(COMPONENTS.keys())


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _swap_edges(edges: Mapping[str, Any]) -> Dict[str, Any]:
    swapped: Dict[str, Any] = {}
    for key in EDGE_KEYS:
        value = edges.get(key)
        try:
            swapped[key] = -float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            swapped[key] = None
    return swapped


class BlinqService:
    def build_match_features(
        self,
        *,
        player1: str,
        player2: str,
        pick: str,
        opponent: str,
        pick_side: Optional[str],
        opponent_side: Optional[str],
        thinq: Mapping[str, Any],
        **_: Any,
    ) -> Dict[str, Any]:
        thinq = _mapping(thinq)
        edges = _mapping(thinq.get("edges"))
        source_status = _mapping(thinq.get("thinq_source_status"))
        common = {
            "source_status": source_status,
            "upstream_confidence": thinq.get("thinq_data_confidence", thinq.get("confidence")),
            "flags": thinq.get("flags") or thinq.get("thinq_flags") or [],
        }

        edges_ab = {key: edges.get(key) for key in EDGE_KEYS}
        result_ab = build_blinq_prediction(
            player_a=pick,
            player_b=opponent,
            side_a=pick_side,
            side_b=opponent_side,
            edges=edges_ab,
            **common,
        )
        result_ba = build_blinq_prediction(
            player_a=opponent,
            player_b=pick,
            side_a=opponent_side,
            side_b=pick_side,
            edges=_swap_edges(edges_ab),
            **common,
        )
        symmetry_audit = audit_blinq_symmetry(result_ab, result_ba)

        if symmetry_audit["status"] != "PASS":
            result_ab.update(
                status="SYMMETRY_FAIL",
                prediction_status="NO_PREDICTION",
                winner=None,
                winner_side=None,
                loser=None,
                loser_side=None,
                winner_probability=0.5,
            )
            result_ab["flags"] = sorted(set(result_ab.get("flags", [])) | {"BLINQ_SYMMETRY_FAIL"})

        return {
            "available": True,
            "model": "blinq",
            "mode": "AUDIT_ONLY_NO_CORQ_RANKING_EFFECT",
            "blinq": result_ab,
            "blinq_swapped_audit_run": result_ba,
            "blinq_symmetry_audit": symmetry_audit,
            "blinq_status": result_ab["status"],
            "blinq_prediction_status": result_ab["prediction_status"],
            "blinq_probability": result_ab["probability_a"],
            "blinq_probability_pct": result_ab["probability_a_pct"],
            "blinq_opponent_probability": result_ab["probability_b"],
            "blinq_winner": result_ab["winner"],
            "blinq_winner_side": result_ab["winner_side"],
            "blinq_confidence": result_ab["confidence"],
            "blinq_data_quality_score": result_ab["data_quality_score"],
            "blinq_feature_coverage": result_ab["feature_coverage"],
            "blinq_flags": result_ab["flags"],
        }


def build_match_features(**kwargs: Any) -> Dict[str, Any]:
    return BlinqService().build_match_features(**kwargs)
