"""BlinQ V2.1: symmetric, real-data-only probability model with decision guards."""
from __future__ import annotations

from math import exp, isfinite
from typing import Any, Dict, Iterable, Mapping, Optional

BLINQ_MODEL_VERSION = "BLINQ_V2_1_DEAD_ZONE_LOW_DATA_GUARD"
TOLERANCE = 1e-8
TIE_TOLERANCE = 1e-12
DEAD_ZONE = 0.005
LOW_DATA_CONFIDENCE_THRESHOLD = 0.40

COMPONENTS: Dict[str, Dict[str, Any]] = {
    "elo_edge": {"weight": 1.00, "cap": 0.10, "source": "elo"},
    "h2h_edge": {"weight": 0.45, "cap": 0.04, "source": "h2h"},
    "recent_form_edge": {"weight": 0.55, "cap": 0.05, "source": "recent_form"},
    "short_form_edge": {"weight": 0.25, "cap": 0.035, "source": "recent_form"},
    "surface_recent_form_edge": {"weight": 0.65, "cap": 0.05, "source": "recent_form"},
    "opponent_quality_edge": {"weight": 0.35, "cap": 0.03, "source": "recent_form"},
}


def _num(value: Any) -> Optional[float]:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _source_usable(statuses: Mapping[str, Any], source: str) -> bool:
    status = str(statuses.get(source) or "UNKNOWN").upper()
    if source == "h2h" and status in {"NO_PREVIOUS_H2H", "NO_PREVIOUS_MATCHES"}:
        return True
    return status == "OK"


def _components(edges: Mapping[str, Any], statuses: Mapping[str, Any]) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    active: Dict[str, float] = {}
    audit: Dict[str, Dict[str, Any]] = {}
    for name, cfg in COMPONENTS.items():
        raw = _num(edges.get(name))
        source = str(cfg["source"])
        available = raw is not None and _source_usable(statuses, source)
        capped = _clamp(raw, -float(cfg["cap"]), float(cfg["cap"])) if available else None
        if capped is not None:
            active[name] = capped
        audit[name] = {
            "raw": raw, "capped": capped, "available": available,
            "source": source,
            "source_status": str(statuses.get(source) or "UNKNOWN").upper(),
            "neutral_zero": available and capped == 0.0,
        }
    return active, audit


def build_blinq_prediction(
    *, player_a: str, player_b: str, side_a: Optional[str], side_b: Optional[str],
    edges: Mapping[str, Any], source_status: Optional[Mapping[str, Any]] = None,
    upstream_confidence: Any = None, flags: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    statuses = source_status if isinstance(source_status, Mapping) else {}
    side_a = str(side_a or "").upper().strip() or None
    side_b = str(side_b or "").upper().strip() or None
    valid = bool(player_a and player_b and player_a != player_b and side_a in {"HOME", "AWAY"} and side_b in {"HOME", "AWAY"} and side_a != side_b)

    active, input_audit = _components(edges, statuses)
    active_weight = sum(float(COMPONENTS[k]["weight"]) for k in active)
    total_weight = sum(float(v["weight"]) for v in COMPONENTS.values())
    coverage = active_weight / total_weight if total_weight else 0.0
    raw_score = sum(active[k] * float(COMPONENTS[k]["weight"]) for k in active) / active_weight if active_weight else 0.0
    upstream = _num(upstream_confidence)
    upstream = _clamp(upstream, 0.0, 1.0) if upstream is not None else 0.0
    groups = {str(COMPONENTS[k]["source"]) for k in active}
    diversity = min(len(groups) / 3.0, 1.0)
    data_quality = _clamp(0.65 * coverage + 0.25 * upstream + 0.10 * diversity, 0.0, 1.0)
    confidence = _clamp(coverage * upstream * (0.80 + 0.20 * diversity), 0.0, 1.0)
    effective_score = raw_score * confidence
    pa = round(_clamp(1.0 / (1.0 + exp(-8.0 * effective_score)), 0.05, 0.95), 10)
    pb = round(1.0 - pa, 10)

    distance = abs(pa - 0.5)
    exact_tie = distance <= TIE_TOLERANCE
    dead_zone = not exact_tie and distance <= DEAD_ZONE
    no_data = not active or confidence <= 0.0
    low_data = "elo_edge" not in active and confidence < LOW_DATA_CONFIDENCE_THRESHOLD
    output_flags = {str(x) for x in (flags or []) if x}
    if not valid: output_flags.add("BLINQ_INVALID_INPUT")
    if no_data: output_flags.add("BLINQ_NO_USABLE_REAL_DATA")
    if coverage < 0.50: output_flags.add("BLINQ_LOW_FEATURE_COVERAGE")
    if exact_tie: output_flags.add("BLINQ_EXACT_50_50_NO_PREDICTION")
    if dead_zone: output_flags.add("BLINQ_DEAD_ZONE_NO_PREDICTION")
    if low_data: output_flags.add("BLINQ_LOW_DATA_NO_PREDICTION")

    predict = valid and not no_data and not exact_tie and not dead_zone and not low_data
    a_wins = pa > pb
    winner = (player_a if a_wins else player_b) if predict else None
    winner_side = (side_a if a_wins else side_b) if predict else None
    loser = (player_b if a_wins else player_a) if predict else None
    loser_side = (side_b if a_wins else side_a) if predict else None
    status = (
        "OK" if predict else "INVALID_INPUT" if not valid else "NO_DATA" if no_data
        else "NO_PREDICTION_EXACT_TIE" if exact_tie
        else "NO_PREDICTION_DEAD_ZONE" if dead_zone
        else "NO_PREDICTION_LOW_DATA"
    )
    return {
        "status": status, "prediction_status": "PREDICTION" if predict else "NO_PREDICTION",
        "model_version": BLINQ_MODEL_VERSION,
        "source_policy": "REAL_DATA_ONLY_API_PRO_PLUS_TA_ELO_CACHE_ALLOWED",
        "player_a": player_a, "player_b": player_b, "side_a": side_a, "side_b": side_b,
        "probability_a": pa, "probability_b": pb,
        "probability_a_pct": round(pa * 100, 4), "probability_b_pct": round(pb * 100, 4),
        "winner": winner, "winner_side": winner_side, "loser": loser, "loser_side": loser_side,
        "winner_probability": round(max(pa, pb) if predict else 0.5, 10),
        "raw_score": round(raw_score, 10), "effective_score": round(effective_score, 10),
        "confidence": round(confidence, 10), "data_quality_score": round(data_quality, 10),
        "feature_coverage": round(coverage, 10), "available_component_count": len(active),
        "source_diversity": round(diversity, 10), "components": active,
        "component_input_audit": input_audit, "source_status": dict(statuses),
        "decision_guard": {
            "exact_tie": exact_tie, "dead_zone": dead_zone, "dead_zone_half_width": DEAD_ZONE,
            "low_data": low_data, "low_data_confidence_threshold": LOW_DATA_CONFIDENCE_THRESHOLD,
        },
        "symmetry_contract": {
            "status": "PASS" if abs(pa + pb - 1.0) <= TOLERANCE else "FAIL",
            "rule": "P(A,B)+P(B,A)=1 and each signed component(A,B)=-component(B,A)",
            "complement_sum": round(pa + pb, 10), "exact_50_50": exact_tie,
            "dead_zone": dead_zone, "low_data_guard": low_data,
        },
        "flags": sorted(output_flags),
    }


def audit_blinq_symmetry(result_ab: Mapping[str, Any], result_ba: Mapping[str, Any], tolerance: float = TOLERANCE) -> Dict[str, Any]:
    pa, pb = _num(result_ab.get("probability_a")), _num(result_ba.get("probability_a"))
    sa, sb = _num(result_ab.get("raw_score")), _num(result_ba.get("raw_score"))
    ca = result_ab.get("components") if isinstance(result_ab.get("components"), Mapping) else {}
    cb = result_ba.get("components") if isinstance(result_ba.get("components"), Mapping) else {}
    checks: Dict[str, Dict[str, Any]] = {}
    for name in COMPONENTS:
        a, b = _num(ca.get(name)), _num(cb.get(name))
        passed = (a is None and b is None) or (a is not None and b is not None and abs(a + b) <= tolerance)
        checks[name] = {"ab": a, "ba": b, "sum": round((a or 0.0) + (b or 0.0), 10), "status": "PASS" if passed else "FAIL"}
    probability_ok = pa is not None and pb is not None and abs(pa + pb - 1.0) <= tolerance
    score_ok = sa is not None and sb is not None and abs(sa + sb) <= tolerance
    components_ok = all(x["status"] == "PASS" for x in checks.values())
    decision_ok = result_ab.get("prediction_status") == result_ba.get("prediction_status")
    winner_ok = result_ab.get("winner") == result_ba.get("winner")
    passed = probability_ok and score_ok and components_ok and decision_ok and winner_ok
    return {
        "status": "PASS" if passed else "FAIL", "probability_complement_ok": probability_ok,
        "score_antisymmetry_ok": score_ok, "component_antisymmetry_ok": components_ok,
        "decision_symmetry_ok": decision_ok, "winner_symmetry_ok": winner_ok,
        "tie_ok": decision_ok, "probability_sum": round((pa or 0.0) + (pb or 0.0), 10),
        "score_sum": round((sa or 0.0) + (sb or 0.0), 10),
        "component_checks": checks, "tolerance": tolerance,
    }
