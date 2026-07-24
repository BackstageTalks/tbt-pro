
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


def build_corq_prediction(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    thinq = out.get("thinq") if isinstance(out.get("thinq"), dict) else {}
    edges = extract_edges(out)
    thinq_confidence = as_float(out.get("thinq_confidence"), None)
    if thinq_confidence is None:
        thinq_confidence = as_float(thinq.get("confidence"), 0.0) or 0.0
    flags = list(thinq.get("flags") or out.get("thinq_flags") or [])

    odds = as_float(out.get("odds") or out.get("pick_odds"))
    opponent_odds = as_float(out.get("opponent_odds"))
    implied = round(1.0 / odds, 4) if odds and odds > 1 else None

    components = model_components(edges)
    raw_model_edge = round(sum(components.values()), 4)
    conf_factor = confidence_factor(float(thinq_confidence or 0.0), flags)
    estimated_probability = round(clamp(0.50 + raw_model_edge * conf_factor, 0.05, 0.95), 4)

    trap = is_default_value_trap(out, components)
    corq_edge = round(estimated_probability - implied, 4) if implied is not None else 0.0
    risk_flags = list(out.get("corq_risk_flags") or [])
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
            "thinq_available": bool(thinq) or bool(edges),
            "thinq_edges": edges,
            "thinq_flags": flags,
            "corq_model_version": "CORQ_V1_EXPLAINABLE_EDGE_CONFIDENCE",
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
