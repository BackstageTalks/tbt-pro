
"""CORQ V1 scoring model.

Functional scoring architecture:
- separates model probability from public display score
- uses ELO family + form family + H2H + context
- applies confidence shrinkage toward 50% when data quality is weak
- prevents default-score no-data value traps
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _edge(edges: Dict[str, Any], key: str) -> float:
    return as_float(edges.get(key), 0.0) or 0.0


def _raw_rank(record: Dict[str, Any], side: str) -> Optional[int]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    key = "homeTeam" if side == "HOME" else "awayTeam"
    team = raw.get(key) if isinstance(raw.get(key), dict) else {}
    try:
        value = team.get("ranking")
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def ranking_context_edge(record: Dict[str, Any]) -> float:
    pick_side = str(record.get("pick_side") or "").upper()
    opp_side = "AWAY" if pick_side == "HOME" else "HOME" if pick_side == "AWAY" else ""
    pick_rank = _raw_rank(record, pick_side)
    opp_rank = _raw_rank(record, opp_side)
    if pick_rank is None or opp_rank is None:
        return 0.0
    # Lower rank number is better. Positive means pick has ranking context advantage.
    diff = opp_rank - pick_rank
    return round(clamp(diff / 1000.0, -0.02, 0.02), 4)


def extract_edges(record: Dict[str, Any]) -> Dict[str, Optional[float]]:
    thinq = record.get("thinq") if isinstance(record.get("thinq"), dict) else {}
    thinq_edges = thinq.get("edges") if isinstance(thinq.get("edges"), dict) else {}
    direct_edges = record.get("edges") if isinstance(record.get("edges"), dict) else {}
    merged = {**thinq_edges, **direct_edges}
    if "overall_elo_edge" not in merged and "elo_edge" in merged:
        merged["overall_elo_edge"] = 0.0
    if "surface_elo_edge" not in merged and "elo_edge" in merged:
        merged["surface_elo_edge"] = merged.get("elo_edge")
    merged["ranking_context_edge"] = ranking_context_edge(record)
    merged.setdefault("market_sanity_edge", 0.0)
    keys = [
        "overall_elo_edge",
        "surface_elo_edge",
        "elo_edge",
        "h2h_edge",
        "recent_form_edge",
        "short_form_edge",
        "surface_recent_form_edge",
        "opponent_quality_edge",
        "ranking_context_edge",
        "market_sanity_edge",
        "surface_form_edge",
        "level_form_edge",
        "ta_edge",
        "fatigue_edge",
        "surface_transition_edge",
        "level_context_edge",
        "status_risk_edge",
        "sets_edge",
        "games_edge",
        "tiebreak_edge",
        "decider_edge",
    ]
    return {key: as_float(merged.get(key)) for key in keys if key in merged}


def model_components(edges: Dict[str, Optional[float]]) -> Dict[str, float]:
    # Direct edge-space components. Caps follow CORQ V1 design document.
    overall_elo = clamp(_edge(edges, "overall_elo_edge"), -0.07, 0.07)
    surface_elo = clamp(_edge(edges, "surface_elo_edge"), -0.08, 0.08)
    recent = clamp((_edge(edges, "recent_form_edge") * 0.65) + (_edge(edges, "short_form_edge") * 0.35), -0.05, 0.05)
    surface_recent = clamp(_edge(edges, "surface_recent_form_edge"), -0.05, 0.05)
    opponent_quality = clamp(_edge(edges, "opponent_quality_edge"), -0.03, 0.03)
    h2h = clamp(_edge(edges, "h2h_edge"), -0.04, 0.04)
    ranking = clamp(_edge(edges, "ranking_context_edge"), -0.02, 0.02)
    market = clamp(_edge(edges, "market_sanity_edge"), -0.02, 0.02)
    context = clamp(
        _edge(edges, "surface_form_edge") + _edge(edges, "level_form_edge") + _edge(edges, "ta_edge")
        + _edge(edges, "fatigue_edge") + _edge(edges, "surface_transition_edge") + _edge(edges, "level_context_edge")
        + _edge(edges, "status_risk_edge") + _edge(edges, "sets_edge") + _edge(edges, "games_edge")
        + _edge(edges, "tiebreak_edge") + _edge(edges, "decider_edge"),
        -0.04,
        0.04,
    )
    return {
        "overall_elo_component": round(overall_elo, 4),
        "surface_elo_component": round(surface_elo, 4),
        "recent_form_component": round(recent, 4),
        "surface_recent_form_component": round(surface_recent, 4),
        "opponent_quality_component": round(opponent_quality, 4),
        "h2h_component": round(h2h, 4),
        "ranking_context_component": round(ranking, 4),
        "market_sanity_component": round(market, 4),
        "context_component": round(context, 4),
    }


def confidence_factor(thinq_confidence: float, flags: list[str]) -> float:
    base = 0.35 + clamp(thinq_confidence, 0.0, 1.0) * 0.65
    flag_set = set(flags or [])
    if "MISSING_ELO" in flag_set:
        base -= 0.08
    if "RECENT_FORM_NO_DATA" in flag_set:
        base -= 0.07
    if "NO_H2H_DATA" in flag_set:
        base -= 0.02
    if "SURFACE_RECENT_FORM_THIN" in flag_set:
        base -= 0.04
    return round(clamp(base, 0.25, 1.0), 4)


def is_default_value_trap(record: Dict[str, Any], components: Dict[str, float]) -> bool:
    """Detect no-intelligence outsider value traps.

    Ranking context alone is not intelligence. A row with no ELO, no recent form
    and no H2H must not create a big value edge simply because odds are high.
    """
    odds = as_float(record.get("odds") or record.get("pick_odds"))
    thinq_conf = as_float(record.get("thinq_confidence"), 0.0) or 0.0
    flags = set(record.get("thinq_flags") or [])

    intelligence_keys = [
        "overall_elo_component",
        "surface_elo_component",
        "recent_form_component",
        "surface_recent_form_component",
        "opponent_quality_component",
        "h2h_component",
    ]
    intelligence_strength = sum(abs(float(components.get(key) or 0.0)) for key in intelligence_keys)
    no_intelligence = intelligence_strength < 0.0001
    no_core_data = {"MISSING_ELO", "RECENT_FORM_NO_DATA"}.issubset(flags)
    very_weak_thinq = thinq_conf < 0.50
    high_odds = odds is not None and odds >= 3.0
    return bool(no_intelligence and high_odds and (no_core_data or very_weak_thinq))



def thinq_probability_layer(record: Dict[str, Any]) -> Dict[str, Any]:
    thinq = record.get("thinq") if isinstance(record.get("thinq"), dict) else {}
    layer = thinq.get("thinq_probability_layer") or thinq.get("probability_layer")
    if isinstance(layer, dict):
        return layer
    layer = record.get("thinq_probability_layer") or record.get("probability_layer")
    return layer if isinstance(layer, dict) else {}

def thinq_pick_probability(record: Dict[str, Any]) -> Optional[float]:
    layer = thinq_probability_layer(record)
    value = (
        layer.get("pick_probability")
        or layer.get("probability")
        or record.get("thinq_pick_probability")
        or record.get("thinq_probability")
    )
    val = as_float(value)
    if val is None:
        return None
    return val / 100.0 if val > 1 else val


def _prob_from_any(value: Any) -> Optional[float]:
    val = as_float(value)
    if val is None:
        return None
    if val > 1.0:
        val /= 100.0
    return clamp(val, 0.0, 1.0)


def _first_probability(record: Dict[str, Any], keys: list[str]) -> Optional[float]:
    for key in keys:
        if key in record:
            value = _prob_from_any(record.get(key))
            if value is not None:
                return value
    return None


def marq_pick_probability(record: Dict[str, Any]) -> Optional[float]:
    """Return MarQ/market pick probability in 0..1 scale when available."""
    value = _first_probability(
        record,
        [
            "corq_market_probability",
            "marq_pick_probability",
            "marq_pick_probability_pct",
            "marq_pick_pct",
            "marq_pick_no_vig_probability",
            "marq_no_vig_pick_probability",
            "marq_crowd_pick_pct",
            "market_pick_probability",
            "market_pick_probability_pct",
            "market_pick_no_vig_probability",
            "pick_no_vig_probability",
            "pick_implied_no_vig_probability",
        ],
    )
    if value is not None:
        return value

    # Last-resort market probability from both decimal odds. This is still MarQ
    # fallback because it is a no-vig market view, not a model estimate.
    pick_odds = as_float(record.get("pick_odds") or record.get("odds"))
    opp_odds = as_float(record.get("opponent_odds") or record.get("opp_odds"))
    if pick_odds and opp_odds and pick_odds > 1 and opp_odds > 1:
        pick_imp = 1.0 / pick_odds
        opp_imp = 1.0 / opp_odds
        total = pick_imp + opp_imp
        if total > 0:
            return clamp(pick_imp / total, 0.0, 1.0)
    return None


def _clv_pp(record: Dict[str, Any]) -> Optional[float]:
    for key in ("marq_internal_clv_pp", "internal_clv_pp", "marq_clv_pp", "clv_pp"):
        val = as_float(record.get(key))
        if val is not None:
            return val
    return None


def _model_market_weights(record: Dict[str, Any], data_confidence: float, market_probability: Optional[float]) -> tuple[float, float, str]:
    if market_probability is None:
        return 1.0, 0.0, "THINQ_FALLBACK_NO_MARQ"

    if data_confidence >= 0.80:
        model_weight = 0.70
    elif data_confidence >= 0.70:
        model_weight = 0.65
    else:
        model_weight = 0.55

    move = str(
        record.get("marq_internal_move_signal")
        or record.get("marq_move_signal")
        or record.get("marq_display_move_signal")
        or ""
    ).upper()
    clv = _clv_pp(record)

    # If market movement is against the pick, give MarQ more braking power.
    if "AGAINST" in move or (clv is not None and clv <= -2.0):
        model_weight -= 0.10
    # If market movement supports the pick, still keep MarQ visible but reduce braking.
    elif "TOWARD" in move or "WITH" in move or (clv is not None and clv >= 2.0):
        model_weight += 0.05

    model_weight = clamp(model_weight, 0.50, 0.75)
    market_weight = round(1.0 - model_weight, 4)
    return round(model_weight, 4), market_weight, "THINQ_MARQ_MODEL_MIX"


def apply_corq_market_calibration(record: Dict[str, Any]) -> Dict[str, Any]:
    """Calibrate CorQ as MMx = ThinQ model probability + MarQ market probability.

    This function is intentionally not a filter. It keeps all candidates but makes
    CorQ a genuine final calibrated probability instead of a ThinQ copy.
    """
    out = dict(record)
    thinq_probability = thinq_pick_probability(out)
    if thinq_probability is None:
        thinq_probability = _prob_from_any(
            out.get("corq_raw_model_probability")
            or out.get("corq_estimated_win_probability")
            or out.get("corq_probability")
            or out.get("probability")
        )
    if thinq_probability is None:
        thinq_probability = 0.50

    data_confidence = as_float(out.get("thinq_data_confidence"), None)
    if data_confidence is None:
        data_confidence = as_float(out.get("thinq_confidence"), 0.0) or 0.0
    if data_confidence > 1.0:
        data_confidence /= 100.0
    data_confidence = clamp(float(data_confidence or 0.0), 0.0, 1.0)

    market_probability = marq_pick_probability(out)
    model_weight, market_weight, method = _model_market_weights(out, data_confidence, market_probability)
    if market_probability is None:
        market_probability = thinq_probability

    thinq_input = thinq_probability * model_weight
    marq_input = market_probability * market_weight
    calibrated = clamp(thinq_input + marq_input, 0.05, 0.95)
    adjustment_pp = (calibrated - thinq_probability) * 100.0

    odds = as_float(out.get("pick_odds") or out.get("odds"))
    implied = round(1.0 / odds, 4) if odds and odds > 1 else None
    corq_edge = round(calibrated - implied, 4) if implied is not None else as_float(out.get("corq_edge"), 0.0) or 0.0

    out.update(
        {
            "corq_raw_model_probability": round(thinq_probability, 4),
            "corq_raw_model_probability_pct": round(thinq_probability * 100.0, 2),
            "corq_market_probability": round(market_probability, 4),
            "corq_market_probability_pct": round(market_probability * 100.0, 2),
            "corq_model_weight": round(model_weight, 4),
            "corq_market_weight": round(market_weight, 4),
            "corq_model_mix_label": f"ThinQ {int(round(model_weight * 100))}% / MarQ {int(round(market_weight * 100))}%",
            "corq_thinq_input_pp": round(thinq_input * 100.0, 2),
            "corq_marq_input_pp": round(marq_input * 100.0, 2),
            "corq_calibrated_probability": round(calibrated, 4),
            "corq_calibrated_probability_pct": round(calibrated * 100.0, 2),
            "corq_market_adjustment_pp": round(adjustment_pp, 2),
            "corq_calibration_method": method,
            "corq_probability": round(calibrated, 4),
            "corq_estimated_win_probability": round(calibrated, 4),
            "estimated_win_pct": round(calibrated * 100.0, 2),
            "corq_score": round(calibrated, 4),
            "probability": round(calibrated, 4),
            "corq_edge": corq_edge,
            "value_edge": corq_edge,
            "edge": corq_edge,
        }
    )
    return out

def build_corq_prediction(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    thinq = out.get("thinq") if isinstance(out.get("thinq"), dict) else {}
    edges = extract_edges(out)
    thinq_confidence = as_float(out.get("thinq_data_confidence"), None)
    if thinq_confidence is None:
        thinq_confidence = as_float(out.get("thinq_confidence"), None)
    if thinq_confidence is None:
        thinq_confidence = as_float(thinq.get("thinq_data_confidence"), None)
    if thinq_confidence is None:
        thinq_confidence = as_float(thinq.get("confidence"), 0.0) or 0.0
    flags = list(thinq.get("flags") or out.get("thinq_flags") or [])

    odds = as_float(out.get("odds") or out.get("pick_odds"))
    opponent_odds = as_float(out.get("opponent_odds"))
    implied = round(1.0 / odds, 4) if odds and odds > 1 else None

    components = model_components(edges)
    raw_model_edge = round(sum(components.values()), 4)
    conf_factor = confidence_factor(float(thinq_confidence or 0.0), flags)

    thinq_layer = thinq_probability_layer(out)
    thinq_probability = thinq_pick_probability(out)
    if thinq_probability is not None:
        # Current CorQ probability is primarily the clean ThinQ probability.
        # Later MARQ can add a capped market adjustment, but no adapter logic is used here.
        estimated_probability = round(clamp(thinq_probability, 0.05, 0.95), 4)
        raw_model_edge = round(estimated_probability - 0.50, 4)
        conf_factor = as_float(thinq_layer.get("confidence"), conf_factor) or conf_factor
    else:
        estimated_probability = round(clamp(0.50 + raw_model_edge * conf_factor, 0.05, 0.95), 4)

    trap = is_default_value_trap(out, components)
    corq_edge = round(estimated_probability - implied, 4) if implied is not None else 0.0
    risk_flags = list(out.get("corq_risk_flags") or [])

    # Flatten the key ThinQ source fields into the CorQ row.  Render and ranking
    # must not guess across multiple nested shapes.
    elo_ctx = thinq.get("elo") if isinstance(thinq.get("elo"), dict) else {}
    recent_ctx = thinq.get("recent_form") if isinstance(thinq.get("recent_form"), dict) else {}
    pick_form_ctx = recent_ctx.get("pick") if isinstance(recent_ctx.get("pick"), dict) else {}
    opp_form_ctx = recent_ctx.get("opponent") if isinstance(recent_ctx.get("opponent"), dict) else {}
    pick_last10 = pick_form_ctx.get("last10") if isinstance(pick_form_ctx.get("last10"), dict) else {}
    opp_last10 = opp_form_ctx.get("last10") if isinstance(opp_form_ctx.get("last10"), dict) else {}
    pick_surface = pick_form_ctx.get("surface_last10") if isinstance(pick_form_ctx.get("surface_last10"), dict) else {}
    opp_surface = opp_form_ctx.get("surface_last10") if isinstance(opp_form_ctx.get("surface_last10"), dict) else {}
    if trap:
        risk_flags.append("DEFAULT_SCORE_VALUE_TRAP")
        risk_flags.append("NO_INTELLIGENCE_OUTSIDER_VALUE_TRAP")
        # Do not create fake value edge from a neutral/no-intelligence estimate.
        corq_edge = 0.0

    out.update(
        {
            "odds": odds,
            "pick_odds": odds,
            "opponent_odds": opponent_odds,
            "implied_probability": implied,
            "thinq_confidence": round(float(thinq_confidence or 0.0), 4),
            "thinq_data_confidence": round(float(thinq_confidence or 0.0), 4),
            "thinq_data_confidence_pct": round(float(thinq_confidence or 0.0) * 100.0, 2),
            "thinq_pick_probability": thinq_probability,
            "thinq_pick_probability_pct": round(thinq_probability * 100.0, 2) if thinq_probability is not None else None,
            "thinq_available": bool(thinq) or bool(edges),
            "thinq_edges": edges,
            "thinq_flags": flags,
            "thinq_elo_status": elo_ctx.get("status") or out.get("thinq_elo_status"),
            "thinq_recent_form_status": recent_ctx.get("status") or out.get("thinq_recent_form_status"),
            "thinq_recent_form_reason": recent_ctx.get("reason") or out.get("thinq_recent_form_reason"),
            "thinq_overall_elo_edge": elo_ctx.get("overall_elo_edge", edges.get("overall_elo_edge")),
            "thinq_surface_elo_edge": elo_ctx.get("surface_elo_edge", edges.get("surface_elo_edge")),
            "thinq_elo_edge": elo_ctx.get("elo_edge", edges.get("elo_edge")),
            "overall_elo_edge": elo_ctx.get("overall_elo_edge", edges.get("overall_elo_edge")),
            "surface_elo_edge": elo_ctx.get("surface_elo_edge", edges.get("surface_elo_edge")),
            "elo_edge": elo_ctx.get("elo_edge", edges.get("elo_edge")),
            "pick_last10_record": pick_last10.get("record"),
            "opponent_last10_record": opp_last10.get("record"),
            "pick_surface_record": pick_surface.get("record"),
            "opponent_surface_record": opp_surface.get("record"),
            "pick_last10_count": pick_last10.get("count"),
            "opponent_last10_count": opp_last10.get("count"),
            "pick_surface_count": pick_surface.get("count"),
            "opponent_surface_count": opp_surface.get("count"),
            "recent_form_edge": recent_ctx.get("recent_form_edge", edges.get("recent_form_edge")),
            "short_form_edge": recent_ctx.get("short_form_edge", edges.get("short_form_edge")),
            "surface_recent_form_edge": recent_ctx.get("surface_recent_form_edge", edges.get("surface_recent_form_edge")),
            "opponent_quality_edge": recent_ctx.get("opponent_quality_edge", edges.get("opponent_quality_edge")),
            "form_confidence": recent_ctx.get("form_confidence"),
            "form_data_depth": recent_ctx.get("form_data_depth"),
            "corq_model_version": "CORQ_V1_THINQ_PRIMARY_PROBABILITY",
            "corq_probability_source": "THINQ_PICK_PROBABILITY" if thinq_probability is not None else "CORQ_COMPONENT_FALLBACK",
            "corq_thinq_probability": thinq_probability,
            "corq_components": components,
            "corq_raw_model_edge": raw_model_edge,
            "corq_confidence_factor": conf_factor,
            "corq_estimated_win_probability": estimated_probability,
            "estimated_win_pct": round(estimated_probability * 100.0, 2),
            "corq_score": estimated_probability,
            "corq_edge": corq_edge,
            "corq_risk_flags": sorted(set(risk_flags)),
        }
    )
    return out

# ---------------------------------------------------------------------------
# 2026-08-04 CorQ MarQ dynamic-weight override
# ---------------------------------------------------------------------------
# MarQ can no longer have one fixed influence regardless of data quality.
# Provider V2 writes marq_data_status / marq_confidence / marq_movement_status.
# CorQ uses those fields to decide whether MarQ is a strong market calibration
# input, a light current-only sanity check, a thin fallback, or unavailable.

_CORQ_MARQ_DYNAMIC_WEIGHT_VERSION = "2026-08-04-marq-dynamic-weight-v1"


def _pick_outcome_key(record: Dict[str, Any]) -> str:
    key = str(record.get("pick_outcome_key") or record.get("marq_pick_outcome_key") or "").strip().lower()
    if key in {"od2", "2", "away"}:
        return "od2"
    return "od1"


def _marq_no_vig_probability_for_pick(record: Dict[str, Any]) -> Optional[float]:
    pick_key = _pick_outcome_key(record)
    if pick_key == "od2":
        value = _prob_from_any(
            record.get("marq_no_vig_probability_2")
            or record.get("marq_v2_no_vig_2")
            or record.get("marq_opp_no_vig_probability")
            or record.get("marq_no_vig_opp_probability")
        )
    else:
        value = _prob_from_any(
            record.get("marq_no_vig_probability_1")
            or record.get("marq_v2_no_vig_1")
            or record.get("marq_pick_no_vig_probability")
            or record.get("marq_no_vig_pick_probability")
        )
    return value


def marq_pick_probability(record: Dict[str, Any]) -> Optional[float]:
    """Return MarQ market probability for the displayed pick in 0..1 scale.

    V2 prefers TennisApi no-vig probabilities from the exact-event provider.
    If those are missing, it falls back to legacy fields and finally to a no-vig
    calculation from paired pick/opponent odds. It does not invent probabilities.
    """
    value = _marq_no_vig_probability_for_pick(record)
    if value is not None:
        return value

    value = _first_probability(
        record,
        [
            "corq_market_probability",
            "marq_pick_probability",
            "marq_pick_probability_pct",
            "marq_pick_pct",
            "marq_pick_no_vig_probability",
            "marq_no_vig_pick_probability",
            "marq_crowd_pick_pct",
            "market_pick_probability",
            "market_pick_probability_pct",
            "market_pick_no_vig_probability",
            "pick_no_vig_probability",
            "pick_implied_no_vig_probability",
        ],
    )
    if value is not None:
        return value

    pick_odds = as_float(record.get("pick_odds") or record.get("odds"))
    opp_odds = as_float(record.get("opponent_odds") or record.get("opp_odds"))
    if pick_odds and opp_odds and pick_odds > 1 and opp_odds > 1:
        pick_imp = 1.0 / pick_odds
        opp_imp = 1.0 / opp_odds
        total = pick_imp + opp_imp
        if total > 0:
            return clamp(pick_imp / total, 0.0, 1.0)
    return None


def marq_quality_tier(record: Dict[str, Any], market_probability: Optional[float] = None) -> tuple[str, float, str]:
    """Return (tier, market_weight, reason) for CorQ market calibration.

    Target policy:
    - High MarQ: 20-30% weight
    - Medium current-only MarQ: 10-15% weight
    - Thin fallback: 0-5% weight
    - No MarQ: 0% weight
    """
    if market_probability is None:
        return "NO_MARQ", 0.0, "no market probability available"

    data_status = str(record.get("marq_data_status") or record.get("marq_source_quality") or "").upper()
    confidence = str(record.get("marq_confidence") or "").upper()
    movement_status = str(record.get("marq_movement_status") or "").upper()
    source_policy = str(record.get("marq_source_policy") or "").upper()
    fallback_reason = str(record.get("marq_fallback_reason") or "").upper()
    exact_used = bool(record.get("marq_exact_event_id_used"))

    if "FALLBACK_EXISTING_ODDS_THIN" in data_status or "THIN" in data_status or "THIN" in fallback_reason:
        return "THIN_FALLBACK", 0.03, "thin existing-odds fallback only"

    if not exact_used and "TENNISAPI_ONLY" not in source_policy:
        return "THIN_FALLBACK", 0.03, "market odds not tied to exact TennisApi event id"

    if "REAL_OPENING_CURRENT_AVAILABLE" in movement_status or "WITH_OPENING" in data_status or confidence == "HIGH":
        return "HIGH", 0.25, "exact TennisApi odds with real opening/current market data"

    if "CURRENT_ONLY" in movement_status or "CURRENT_ONLY" in data_status or "OPENING_EQUALS_CURRENT" in movement_status:
        return "MEDIUM_CURRENT_ONLY", 0.12, "exact TennisApi current odds only, no real movement signal"

    if exact_used:
        return "MEDIUM_CURRENT_ONLY", 0.10, "exact TennisApi odds with partial MarQ data"

    return "NO_MARQ", 0.0, "MarQ data quality unavailable"


def _model_market_weights(record: Dict[str, Any], data_confidence: float, market_probability: Optional[float]) -> tuple[float, float, str]:
    tier, base_market_weight, reason = marq_quality_tier(record, market_probability)
    if market_probability is None or base_market_weight <= 0:
        record["corq_marq_quality_tier"] = tier
        record["corq_marq_weight_reason"] = reason
        return 1.0, 0.0, "THINQ_ONLY_NO_USABLE_MARQ"

    move = str(
        record.get("marq_internal_move_signal")
        or record.get("marq_move_signal")
        or record.get("marq_display_move_signal")
        or ""
    ).upper()
    clv = _clv_pp(record)

    market_weight = float(base_market_weight)

    # Only real high-quality movement may adjust MarQ weight. Current-only and
    # thin fallback must not turn into a false 30% signal.
    if tier == "HIGH":
        if "AGAINST" in move or (clv is not None and clv <= -2.0):
            market_weight += 0.05
            reason += "; real movement/CLV against pick, market brake increased"
        elif "TOWARD" in move or "WITH" in move or (clv is not None and clv >= 2.0):
            market_weight -= 0.03
            reason += "; real movement supports pick, market brake reduced"
        market_weight = clamp(market_weight, 0.20, 0.30)
    elif tier == "MEDIUM_CURRENT_ONLY":
        market_weight = clamp(market_weight, 0.10, 0.15)
    elif tier == "THIN_FALLBACK":
        market_weight = clamp(market_weight, 0.00, 0.05)

    # If ThinQ data confidence is poor, do not blindly increase MarQ. A weak
    # model plus thin/current-only market is not stronger evidence.
    if data_confidence < 0.55 and tier != "HIGH":
        market_weight = min(market_weight, 0.10)
        reason += "; low ThinQ confidence caps non-high MarQ weight"

    model_weight = round(1.0 - market_weight, 4)
    market_weight = round(market_weight, 4)
    record["corq_marq_quality_tier"] = tier
    record["corq_marq_weight_reason"] = reason
    return model_weight, market_weight, f"DYNAMIC_MARQ_WEIGHT_{tier}"


def _value_metrics_for_probability(probability: float, odds: Optional[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if odds is None or odds <= 1:
        return None, None, None
    implied = 1.0 / odds
    value_delta_pp = (probability - implied) * 100.0
    expected_value_pct = (probability * odds - 1.0) * 100.0
    return implied, value_delta_pp, expected_value_pct


def apply_corq_market_calibration(record: Dict[str, Any]) -> Dict[str, Any]:
    """Calibrate CorQ with dynamic MarQ weighting.

    MarQ weight now depends on data quality:
    High exact market data: 20-30%; current-only: 10-15%; thin fallback: 0-5%;
    missing/no usable MarQ: 0%.
    """
    out = dict(record)
    thinq_probability = thinq_pick_probability(out)
    if thinq_probability is None:
        thinq_probability = _prob_from_any(
            out.get("corq_raw_model_probability")
            or out.get("corq_estimated_win_probability")
            or out.get("corq_probability")
            or out.get("probability")
        )
    if thinq_probability is None:
        thinq_probability = 0.50

    data_confidence = as_float(out.get("thinq_data_confidence"), None)
    if data_confidence is None:
        data_confidence = as_float(out.get("thinq_confidence"), 0.0) or 0.0
    if data_confidence > 1.0:
        data_confidence /= 100.0
    data_confidence = clamp(float(data_confidence or 0.0), 0.0, 1.0)

    market_probability = marq_pick_probability(out)
    model_weight, market_weight, method = _model_market_weights(out, data_confidence, market_probability)
    if market_probability is None:
        market_probability = thinq_probability

    thinq_input = thinq_probability * model_weight
    marq_input = market_probability * market_weight
    calibrated = clamp(thinq_input + marq_input, 0.05, 0.95)
    adjustment_pp = (calibrated - thinq_probability) * 100.0

    odds = as_float(out.get("pick_odds") or out.get("odds"))
    implied, value_delta_pp, expected_value_pct = _value_metrics_for_probability(calibrated, odds)
    corq_edge = round(calibrated - implied, 4) if implied is not None else as_float(out.get("corq_edge"), 0.0) or 0.0

    marq_implied, marq_value_delta_pp, marq_expected_value_pct = _value_metrics_for_probability(thinq_probability, odds)
    if marq_implied is not None and market_probability is not None:
        # Model-vs-market value is better represented by ThinQ/model probability
        # against market no-vig probability, not only raw break-even.
        marq_value_delta_pp = (thinq_probability - market_probability) * 100.0

    out.update(
        {
            "corq_raw_model_probability": round(thinq_probability, 4),
            "corq_raw_model_probability_pct": round(thinq_probability * 100.0, 2),
            "corq_market_probability": round(market_probability, 4),
            "corq_market_probability_pct": round(market_probability * 100.0, 2),
            "corq_model_weight": round(model_weight, 4),
            "corq_market_weight": round(market_weight, 4),
            "corq_model_mix_label": f"ThinQ {int(round(model_weight * 100))}% / MarQ {int(round(market_weight * 100))}%",
            "corq_thinq_input_pp": round(thinq_input * 100.0, 2),
            "corq_marq_input_pp": round(marq_input * 100.0, 2),
            "corq_calibrated_probability": round(calibrated, 4),
            "corq_calibrated_probability_pct": round(calibrated * 100.0, 2),
            "corq_market_adjustment_pp": round(adjustment_pp, 2),
            "corq_calibration_method": method,
            "corq_marq_dynamic_weight_version": _CORQ_MARQ_DYNAMIC_WEIGHT_VERSION,
            "corq_marq_quality_tier": out.get("corq_marq_quality_tier"),
            "corq_marq_weight_reason": out.get("corq_marq_weight_reason"),
            "corq_probability": round(calibrated, 4),
            "corq_estimated_win_probability": round(calibrated, 4),
            "estimated_win_pct": round(calibrated * 100.0, 2),
            "corq_score": round(calibrated, 4),
            "probability": round(calibrated, 4),
            "corq_edge": corq_edge,
            "value_edge": corq_edge,
            "edge": corq_edge,
            "corq_value_delta_pp": round(value_delta_pp, 2) if value_delta_pp is not None else None,
            "expected_value_pct": round(expected_value_pct, 2) if expected_value_pct is not None else None,
            "marq_v2_model_probability": round(thinq_probability, 4),
            "marq_v2_market_probability": round(market_probability, 4),
            "marq_v2_value_delta_pp": round(marq_value_delta_pp, 2) if marq_value_delta_pp is not None else None,
            "marq_v2_expected_value_pct": round(marq_expected_value_pct, 2) if marq_expected_value_pct is not None else None,
            "marq_v2_data_status": out.get("marq_data_status") or out.get("marq_source_quality"),
            "marq_v2_confidence": out.get("marq_confidence"),
            "marq_v2_movement_status": out.get("marq_movement_status"),
        }
    )
    return out

# Final ThinQ V3 contract guard.
_CORQ_BASE_BUILD_PREDICTION = build_corq_prediction
_CORQ_BASE_APPLY_MARKET_CALIBRATION = apply_corq_market_calibration


def _is_no_prediction(record: Dict[str, Any]) -> bool:
    layer = thinq_probability_layer(record)
    status = str(
        record.get("corq_prediction_status")
        or record.get("thinq_prediction_status")
        or layer.get("prediction_status")
        or layer.get("status")
        or ""
    ).upper()
    probability = thinq_pick_probability(record)
    return status == "NO_PREDICTION" or (
        probability is not None
        and abs(probability - 0.50) < 1e-12
        and layer.get("winner") is None
    )


def _apply_no_prediction_guard(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    out.update({
        "corq_status": "NO_PREDICTION",
        "corq_prediction_status": "NO_PREDICTION",
        "corq_winner": None,
        "corq_winner_side": None,
        "corq_probability": 0.50,
        "corq_estimated_win_probability": 0.50,
        "corq_calibrated_probability": 0.50,
        "corq_calibrated_probability_pct": 50.0,
        "estimated_win_pct": 50.0,
        "corq_score": 0.50,
        "corq_edge": 0.0,
        "value_edge": 0.0,
        "edge": 0.0,
        "corq_market_adjustment_pp": 0.0,
        "corq_probability_source": "THINQ_NO_PREDICTION",
        "corq_calibration_method": "NO_PREDICTION_PASSTHROUGH",
    })
    out["corq_risk_flags"] = sorted(set(list(out.get("corq_risk_flags") or []) + ["CORQ_NO_PREDICTION_FROM_THINQ"]))
    return out


def build_corq_prediction(record: Dict[str, Any]) -> Dict[str, Any]:
    out = _CORQ_BASE_BUILD_PREDICTION(record)
    if _is_no_prediction(out):
        return _apply_no_prediction_guard(out)
    out["corq_status"] = "OK"
    out["corq_prediction_status"] = "PREDICTION"
    return out


def apply_corq_market_calibration(record: Dict[str, Any]) -> Dict[str, Any]:
    if _is_no_prediction(record):
        return _apply_no_prediction_guard(record)
    out = _CORQ_BASE_APPLY_MARKET_CALIBRATION(record)
    out["corq_status"] = "OK"
    out["corq_prediction_status"] = "PREDICTION"
    return out
