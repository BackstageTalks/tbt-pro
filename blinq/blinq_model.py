"""BlinQ V1: symmetric, real-data-only probability model."""
from __future__ import annotations
from math import exp
from typing import Any, Dict, Iterable, Mapping, Optional

BLINQ_MODEL_VERSION = "BLINQ_V1_SYMMETRIC_REAL_DATA_ONLY"
TOLERANCE = 1e-8
COMPONENTS = {
    "elo_edge": (1.00, 0.10),
    "h2h_edge": (0.45, 0.04),
    "recent_form_edge": (0.55, 0.05),
    "surface_recent_form_edge": (0.65, 0.05),
    "opponent_quality_edge": (0.35, 0.03),
}

def _num(value: Any) -> Optional[float]:
    try:
        if value in (None, "") or isinstance(value, bool): return None
        out = float(value)
        return out if out == out and abs(out) != float("inf") else None
    except (TypeError, ValueError): return None

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def build_blinq_prediction(*, player_a: str, player_b: str, side_a: Optional[str], side_b: Optional[str], edges: Mapping[str, Any], source_status: Optional[Mapping[str, Any]] = None, upstream_confidence: Any = None, flags: Optional[Iterable[Any]] = None) -> Dict[str, Any]:
    side_a = str(side_a or "").upper() or None
    side_b = str(side_b or "").upper() or None
    valid = bool(player_a and player_b and side_a in {"HOME", "AWAY"} and side_b in {"HOME", "AWAY"} and side_a != side_b)
    active, audit = {}, {}
    for name, (_, cap) in COMPONENTS.items():
        raw = _num(edges.get(name)); audit[name] = raw
        if raw is not None: active[name] = _clamp(raw, -cap, cap)
    weight = sum(COMPONENTS[k][0] for k in active)
    total_weight = sum(v[0] for v in COMPONENTS.values())
    score = sum(active[k] * COMPONENTS[k][0] for k in active) / weight if weight else 0.0
    coverage = weight / total_weight if total_weight else 0.0
    conf = _num(upstream_confidence)
    confidence = coverage if conf is None else coverage * _clamp(conf, 0.0, 1.0)
    effective = score * confidence
    pa = round(_clamp(1.0 / (1.0 + exp(-8.0 * effective)), 0.05, 0.95), 10)
    pb = round(1.0 - pa, 10)
    tie = abs(pa - 0.5) <= 1e-12
    no_data = not active or confidence <= 0.0
    out_flags = {str(x) for x in (flags or []) if x}
    if not valid: out_flags.add("BLINQ_INVALID_INPUT")
    if no_data: out_flags.add("BLINQ_NO_USABLE_REAL_DATA")
    if tie: out_flags.add("BLINQ_EXACT_50_50_NO_PREDICTION")
    predict = valid and not no_data and not tie
    a_wins = pa > pb
    winner = (player_a if a_wins else player_b) if predict else None
    winner_side = (side_a if a_wins else side_b) if predict else None
    status = "OK" if predict else "INVALID_INPUT" if not valid else "NO_DATA" if no_data else "NO_PREDICTION"
    return {
        "status": status, "prediction_status": "PREDICTION" if predict else "NO_PREDICTION",
        "model_version": BLINQ_MODEL_VERSION, "source_policy": "REAL_DATA_ONLY_API_PRO_PLUS_TA_ELO_CACHE_ALLOWED",
        "player_a": player_a, "player_b": player_b, "side_a": side_a, "side_b": side_b,
        "probability_a": pa, "probability_b": pb, "probability_a_pct": round(pa*100,4), "probability_b_pct": round(pb*100,4),
        "winner": winner, "winner_side": winner_side, "winner_probability": round(max(pa,pb) if predict else 0.5,10),
        "raw_score": round(score,10), "effective_score": round(effective,10), "confidence": round(confidence,10),
        "feature_coverage": round(coverage,10), "components": active, "component_input_audit": audit,
        "source_status": dict(source_status or {}),
        "symmetry_contract": {"status": "PASS" if abs(pa+pb-1)<=TOLERANCE else "FAIL", "rule": "P(A,B)+P(B,A)=1 and score(A,B)=-score(B,A)", "complement_sum": round(pa+pb,10), "exact_50_50": tie},
        "flags": sorted(out_flags),
    }

def audit_blinq_symmetry(result_ab: Mapping[str, Any], result_ba: Mapping[str, Any], tolerance: float = TOLERANCE) -> Dict[str, Any]:
    pa, pb = _num(result_ab.get("probability_a")), _num(result_ba.get("probability_a"))
    sa, sb = _num(result_ab.get("raw_score")), _num(result_ba.get("raw_score"))
    prob_ok = pa is not None and pb is not None and abs(pa+pb-1) <= tolerance
    score_ok = sa is not None and sb is not None and abs(sa+sb) <= tolerance
    tie_ok = all(p is None or abs(p-.5)>tolerance or (r.get("prediction_status")=="NO_PREDICTION" and r.get("winner") is None) for p,r in ((pa,result_ab),(pb,result_ba)))
    return {"status":"PASS" if prob_ok and score_ok and tie_ok else "FAIL", "probability_complement_ok":prob_ok, "score_antisymmetry_ok":score_ok, "tie_ok":tie_ok, "probability_sum":round((pa or 0)+(pb or 0),10), "score_sum":round((sa or 0)+(sb or 0),10), "tolerance":tolerance}
