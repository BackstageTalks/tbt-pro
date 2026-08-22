"""BlinQ service consuming completed ThinQ contexts without API calls."""
from __future__ import annotations
from typing import Any, Dict, Mapping, Optional
from .model import audit_blinq_symmetry, build_blinq_prediction
EDGE_KEYS = ("elo_edge","h2h_edge","recent_form_edge","surface_recent_form_edge","opponent_quality_edge")

def _map(value: Any) -> Mapping[str, Any]: return value if isinstance(value, Mapping) else {}
def _swap(edges: Mapping[str, Any]) -> Dict[str, Any]:
    out = {}
    for key in EDGE_KEYS:
        try: out[key] = -float(edges[key]) if edges.get(key) not in (None,"") else None
        except (TypeError,ValueError): out[key] = None
    return out

class BlinqService:
    def build_match_features(self, *, player1: str, player2: str, pick: str, opponent: str, pick_side: Optional[str], opponent_side: Optional[str], thinq: Mapping[str, Any], **_: Any) -> Dict[str, Any]:
        thinq = _map(thinq); edges = _map(thinq.get("edges")); source = _map(thinq.get("thinq_source_status"))
        common = {"source_status":source, "upstream_confidence":thinq.get("thinq_data_confidence",thinq.get("confidence")), "flags":thinq.get("flags") or thinq.get("thinq_flags") or []}
        ab = build_blinq_prediction(player_a=pick,player_b=opponent,side_a=pick_side,side_b=opponent_side,edges={k:edges.get(k) for k in EDGE_KEYS},**common)
        ba = build_blinq_prediction(player_a=opponent,player_b=pick,side_a=opponent_side,side_b=pick_side,edges=_swap(edges),**common)
        audit = audit_blinq_symmetry(ab,ba)
        if audit["status"] != "PASS":
            ab.update(status="SYMMETRY_FAIL",prediction_status="NO_PREDICTION",winner=None,winner_side=None)
            ab["flags"] = sorted(set(ab.get("flags",[]))|{"BLINQ_SYMMETRY_FAIL"})
        return {"available":True,"model":"blinq","blinq":ab,"blinq_swapped_audit_run":ba,"blinq_symmetry_audit":audit,"blinq_status":ab["status"],"blinq_prediction_status":ab["prediction_status"],"blinq_probability":ab["probability_a"],"blinq_probability_pct":ab["probability_a_pct"],"blinq_opponent_probability":ab["probability_b"],"blinq_winner":ab["winner"],"blinq_winner_side":ab["winner_side"],"blinq_confidence":ab["confidence"],"blinq_flags":ab["flags"]}

def build_match_features(**kwargs: Any) -> Dict[str, Any]: return BlinqService().build_match_features(**kwargs)
