"""BlinQ V2 symmetric probability model.

BlinQ consumes signed, real-data ThinQ edges. Missing values remain missing,
zero is treated as an available neutral signal only when its source is valid,
and every published prediction must pass a real A/B swap audit.
"""
from __future__ import annotations

from math import exp, isfinite
from typing import Any, Dict, Iterable, Mapping, Optional

BLINQ_MODEL_VERSION = "BLINQ_V2_COMPONENT_SYMMETRY_DATA_QUALITY"
TOLERANCE = 1e-8
TIE_TOLERANCE = 1e-12

COMPONENTS: Dict[str, Dict[str, Any]] = {
    "elo_edge": {"weight": 1.00, "cap": 0.10, "source": "elo"},
    "h2h_edge": {"weight": 0.45, "cap": 0.04, "source": "h2h"},
    "recent_form_edge": {"weight": 0.55, "cap": 0.05, "source": "recent_form"},
    "short_form_edge": {"weight": 0.25, "cap": 0.035, "source": "recent_form"},
    "surface_recent_form_edge": {"weight": 0.65, "cap": 0.05, "source": "recent_form"},
    "opponent_quality_edge": {"weight": 0.35, "cap": 0.03, "source": "recent_form"},
}

VALID_SOURCE_STATUSES = {"OK", "NO_PREVIOUS_H2H", "NO_PREVIOUS_MATCHES"}


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


def _source_is_usable(source_status: Mapping[str, Any], source: str) -> bool:
    status = str(source_status.get(source) or "UNKNOWN").upper()
    if source == "h2h" and status in {"NO_PREVIOUS_H2H", "NO_PREVIOUS_MATCHES"}:
        return True
    return status == "OK"


def _component_inputs(
    edges: Mapping[str, Any], source_status: Mapping[str, Any]
) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    active: Dict[str, float] = {}
    audit: Dict[str, Dict[str, Any]] = {}
    for name, config in COMPONENTS.items():
        raw = _num(edges.get(name))
        source = str(config["source"])
        source_usable = _source_is_usable(source_status, source)
        available = raw is not None and source_usable
        capped = _clamp(raw, -float(config["cap"]), float(config["cap"])) if available else None
        if capped is not None:
            active[name] = capped
        audit[name] = {
            "raw": raw,
            "capped": capped,
            "available": available,
            "source": source,
            "source_status": str(source_status.get(source) or "UNKNOWN").upper(),
            "neutral_zero": available and capped == 0.0,
        }
    return active, audit


def build_blinq_prediction(
    *,
    player_a: str,
    player_b: str,
    side_a: Optional[str],
    side_b: Optional[str],
    edges: Mapping[str, Any],
    source_status: Optional[Mapping[str, Any]] = None,
    upstream_confidence: Any = None,
    flags: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    source_status = source_status if isinstance(source_status, Mapping) else {}
    side_a = str(side_a or "").upper().strip() or None
    side_b = str(side_b or "").upper().strip() or None
    valid_input = bool(
        str(player_a or "").strip()
        and str(player_b or "").strip()
        and player_a != player_b
        and side_a in {"HOME", "AWAY"}
        and side_b in {"HOME", "AWAY"}
        and side_a != side_b
    )

    active, component_audit = _component_inputs(edges, source_status)
    available_weight = sum(float(COMPONENTS[name]["weight"]) for name in active)
    total_weight = sum(float(config["weight"]) for config in COMPONENTS.values())
    coverage = available_weight / total_weight if total_weight else 0.0
    score = (
        sum(active[name] * float(COMPONENTS[name]["weight"]) for name in active) / available_weight
        if available_weight
        else 0.0
    )

    upstream = _num(upstream_confidence)
    upstream = _clamp(upstream, 0.0, 1.0) if upstream is not None else 0.0
    source_groups = {str(COMPONENTS[name]["source"]) for name in active}
    source_diversity = min(len(source_groups) / 3.0, 1.0)
    data_quality = _clamp((0.65 * coverage) + (0.25 * upstream) + (0.10 * source_diversity), 0.0, 1.0)
    confidence = _clamp(coverage * upstream * (0.80 + 0.20 * source_diversity), 0.0, 1.0)
    effective_score = score * confidence

    probability_a = round(_clamp(1.0 / (1.0 + exp(-8.0 * effective_score)), 0.05, 0.95), 10)
    probability_b = round(1.0 - probability_a, 10)
    exact_tie = abs(probability_a - 0.5) <= TIE_TOLERANCE
    no_data = not active or confidence <= 0.0

    output_flags = {str(value) for value in (flags or []) if value}
    if not valid_input:
        output_flags.add("BLINQ_INVALID_INPUT")
    if no_data:
        output_flags.add("BLINQ_NO_USABLE_REAL_DATA")
    if coverage < 0.50:
        output_flags.add("BLINQ_LOW_FEATURE_COVERAGE")
    if exact_tie:
        output_flags.add("BLINQ_EXACT_50_50_NO_PREDICTION")

    predict = valid_input and not no_data and not exact_tie
    a_wins = probability_a > probability_b
    winner = (player_a if a_wins else player_b) if predict else None
    winner_side = (side_a if a_wins else side_b) if predict else None
    loser = (player_b if a_wins else player_a) if predict else None
    loser_side = (side_b if a_wins else side_a) if predict else None

    status = "OK" if predict else "INVALID_INPUT" if not valid_input else "NO_DATA" if no_data else "NO_PREDICTION"
    return {
        "status": status,
        "prediction_status": "PREDICTION" if predict else "NO_PREDICTION",
        "model_version": BLINQ_MODEL_VERSION,
        "source_policy": "REAL_DATA_ONLY_API_PRO_PLUS_TA_ELO_CACHE_ALLOWED",
        "player_a": player_a,
        "player_b": player_b,
        "side_a": side_a,
        "side_b": side_b,
        "probability_a": probability_a,
        "probability_b": probability_b,
        "probability_a_pct": round(probability_a * 100.0, 4),
        "probability_b_pct": round(probability_b * 100.0, 4),
        "winner": winner,
        "winner_side": winner_side,
        "loser": loser,
        "loser_side": loser_side,
        "winner_probability": round(max(probability_a, probability_b) if predict else 0.5, 10),
        "raw_score": round(score, 10),
        "effective_score": round(effective_score, 10),
        "confidence": round(confidence, 10),
        "data_quality_score": round(data_quality, 10),
        "feature_coverage": round(coverage, 10),
        "available_component_count": len(active),
        "source_diversity": round(source_diversity, 10),
        "components": active,
        "component_input_audit": component_audit,
        "source_status": dict(source_status),
        "symmetry_contract": {
            "status": "PASS" if abs(probability_a + probability_b - 1.0) <= TOLERANCE else "FAIL",
            "rule": "P(A,B)+P(B,A)=1 and each signed component(A,B)=-component(B,A)",
            "complement_sum": round(probability_a + probability_b, 10),
            "exact_50_50": exact_tie,
        },
        "flags": sorted(output_flags),
    }


def audit_blinq_symmetry(
    result_ab: Mapping[str, Any], result_ba: Mapping[str, Any], tolerance: float = TOLERANCE
) -> Dict[str, Any]:
    p_ab = _num(result_ab.get("probability_a"))
    p_ba = _num(result_ba.get("probability_a"))
    score_ab = _num(result_ab.get("raw_score"))
    score_ba = _num(result_ba.get("raw_score"))
    components_ab = result_ab.get("components") if isinstance(result_ab.get("components"), Mapping) else {}
    components_ba = result_ba.get("components") if isinstance(result_ba.get("components"), Mapping) else {}

    component_checks: Dict[str, Dict[str, Any]] = {}
    for name in COMPONENTS:
        a = _num(components_ab.get(name))
        b = _num(components_ba.get(name))
        both_missing = a is None and b is None
        passed = both_missing or (a is not None and b is not None and abs(a + b) <= tolerance)
        component_checks[name] = {"ab": a, "ba": b, "sum": round((a or 0.0) + (b or 0.0), 10), "status": "PASS" if passed else "FAIL"}

    probability_ok = p_ab is not None and p_ba is not None and abs(p_ab + p_ba - 1.0) <= tolerance
    score_ok = score_ab is not None and score_ba is not None and abs(score_ab + score_ba) <= tolerance
    components_ok = all(item["status"] == "PASS" for item in component_checks.values())

    def tie_ok(result: Mapping[str, Any], probability: Optional[float]) -> bool:
        return probability is None or abs(probability - 0.5) > tolerance or (
            result.get("prediction_status") == "NO_PREDICTION" and result.get("winner") is None
        )

    ties_ok = tie_ok(result_ab, p_ab) and tie_ok(result_ba, p_ba)
    passed = probability_ok and score_ok and components_ok and ties_ok
    return {
        "status": "PASS" if passed else "FAIL",
        "probability_complement_ok": probability_ok,
        "score_antisymmetry_ok": score_ok,
        "component_antisymmetry_ok": components_ok,
        "tie_ok": ties_ok,
        "probability_sum": round((p_ab or 0.0) + (p_ba or 0.0), 10),
        "score_sum": round((score_ab or 0.0) + (score_ba or 0.0), 10),
        "component_checks": component_checks,
        "tolerance": tolerance,
    }
