"""CORQ scoring model.

CORQ consumes THINQ intelligence signals and turns them into a ranked score.
THINQ remains the intelligence layer. CORQ does not expose corq_probability
and AI Match is intentionally skipped until MARQ is introduced.
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


def extract_edges(record: Dict[str, Any]) -> Dict[str, Optional[float]]:
    thinq = record.get("thinq") if isinstance(record.get("thinq"), dict) else {}
    thinq_edges = thinq.get("edges") if isinstance(thinq.get("edges"), dict) else {}
    direct_edges = record.get("edges") if isinstance(record.get("edges"), dict) else {}
    merged = {**thinq_edges, **direct_edges}

    keys = [
        "elo_edge",
        "h2h_edge",
        "surface_form_edge",
        "recent_form_edge",
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


def build_corq_score(edges: Dict[str, Optional[float]], thinq_confidence: float = 0.0) -> float:
    """Return CORQ score in 0.05..0.95 range.

    The score is a ranking strength score, not a standalone probability label.
    Confidence gently scales context/noisy edges while ELO, H2H and core form
    edges remain the main drivers.
    """
    confidence = clamp(thinq_confidence, 0.0, 1.0)

    core = (
        _edge(edges, "elo_edge")
        + _edge(edges, "h2h_edge")
        + _edge(edges, "surface_form_edge")
        + _edge(edges, "recent_form_edge")
        + _edge(edges, "level_form_edge")
        + _edge(edges, "ta_edge")
    )

    context = (
        _edge(edges, "fatigue_edge")
        + _edge(edges, "surface_transition_edge")
        + _edge(edges, "level_context_edge")
        + _edge(edges, "status_risk_edge")
        + _edge(edges, "sets_edge")
        + _edge(edges, "games_edge")
        + _edge(edges, "tiebreak_edge")
        + _edge(edges, "decider_edge")
    )

    raw_score = 0.50 + core + (context * max(confidence, 0.35))
    return round(clamp(raw_score, 0.05, 0.95), 4)


def build_corq_prediction(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    thinq = out.get("thinq") if isinstance(out.get("thinq"), dict) else {}
    edges = extract_edges(out)
    thinq_confidence = as_float(out.get("thinq_confidence"), None)
    if thinq_confidence is None:
        thinq_confidence = as_float(thinq.get("confidence"), 0.0) or 0.0

    odds = as_float(out.get("odds") or out.get("pick_odds"))
    opponent_odds = as_float(out.get("opponent_odds"))
    implied = round(1.0 / odds, 4) if odds and odds > 1 else None

    corq_score = build_corq_score(edges, thinq_confidence)
    corq_edge = round(corq_score - implied, 4) if implied is not None else 0.0

    out.update(
        {
            "odds": odds,
            "pick_odds": odds,
            "opponent_odds": opponent_odds,
            "implied_probability": implied,
            "thinq_confidence": round(thinq_confidence, 4),
            "thinq_available": bool(thinq) or bool(edges),
            "thinq_edges": edges,
            "thinq_flags": list(thinq.get("flags") or out.get("thinq_flags") or []),
            "corq_score": corq_score,
            "corq_edge": corq_edge,
        }
    )
    return out
