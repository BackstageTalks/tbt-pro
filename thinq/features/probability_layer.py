"""ThinQ Probability Layer.

ThinQ produces a single clean win-probability intelligence output from the
already computed ThinQ components. CorQ, Top7, CloQ and Web only read this
output. No adapter logic is used here.
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


def _confidence(base_confidence: float, recent_form: Dict[str, Any], h2h: Dict[str, Any], flags: list[str]) -> float:
    """Data-quality confidence for ThinQ probability.

    This is not a filter. It only shrinks ThinQ probability back toward 50%
    when the underlying data is thin or missing.
    """
    value = clamp(base_confidence, 0.0, 1.0)
    flag_set = set(flags or [])

    if "MISSING_ELO" in flag_set:
        value -= 0.12
    if recent_form.get("status") != "OK":
        value -= 0.12
    elif str(recent_form.get("recent_form_freshness_status") or "").upper().endswith("STALE") or "RECENT_FORM_STALE_LOCAL_HISTORY" in flag_set:
        value -= 0.12
    else:
        form_conf = as_float(recent_form.get("form_confidence"), 0.0) or 0.0
        if form_conf < 0.50:
            value -= 0.06
        elif form_conf < 0.75:
            value -= 0.03

    # No previous H2H matches is not a data failure. H2H just contributes 0.
    h2h_status = str(h2h.get("status") or "").upper()
    h2h_total = int(as_float(h2h.get("total_matches"), 0) or 0)
    if h2h_status not in {"OK", "NO_PREVIOUS_MATCHES"} and h2h_total <= 0:
        value -= 0.02

    if "SURFACE_RECENT_FORM_THIN" in flag_set:
        value -= 0.04

    return round(clamp(value, 0.25, 0.95), 4)


def build_thinq_probability_layer(
    *,
    pick: str,
    opponent: str,
    pick_side: Optional[str],
    opponent_side: Optional[str],
    edges: Dict[str, Any],
    confidence: float,
    elo: Dict[str, Any],
    h2h: Dict[str, Any],
    recent_form: Dict[str, Any],
    match_dynamics: Dict[str, Any],
    flags: list[str] | None = None,
) -> Dict[str, Any]:
    """Build the final ThinQ win probability for the current candidate pick.

    Probability is first calculated for the current candidate pick. The layer
    also returns the ThinQ winner and winner probability, which will later be
    used by CloQ.
    """
    flags = list(flags or [])

    components = {
        "overall_elo_edge": round(clamp(_edge(edges, "overall_elo_edge"), -0.07, 0.07), 4),
        "surface_elo_edge": round(clamp(_edge(edges, "surface_elo_edge"), -0.08, 0.08), 4),
        "h2h_edge": round(clamp(_edge(edges, "h2h_edge"), -0.04, 0.04), 4),
        "recent_form_edge": round(clamp(_edge(edges, "recent_form_edge"), -0.05, 0.05), 4),
        "short_form_edge": round(clamp(_edge(edges, "short_form_edge"), -0.035, 0.035), 4),
        "surface_recent_form_edge": round(clamp(_edge(edges, "surface_recent_form_edge"), -0.05, 0.05), 4),
        "opponent_quality_edge": round(clamp(_edge(edges, "opponent_quality_edge"), -0.03, 0.03), 4),
        "sets_edge": round(clamp(_edge(edges, "sets_edge"), -0.015, 0.015), 4),
        "games_edge": round(clamp(_edge(edges, "games_edge"), -0.015, 0.015), 4),
    }

    # Short form is useful, but too reactive, so it is blended into the form family.
    form_family = clamp(
        components["recent_form_edge"] * 0.65 + components["short_form_edge"] * 0.35,
        -0.05,
        0.05,
    )
    sets_games_family = clamp(components["sets_edge"] + components["games_edge"], -0.02, 0.02)

    raw_edge = round(
        clamp(
            components["overall_elo_edge"]
            + components["surface_elo_edge"]
            + components["h2h_edge"]
            + form_family
            + components["surface_recent_form_edge"]
            + components["opponent_quality_edge"]
            + sets_games_family,
            -0.25,
            0.25,
        ),
        4,
    )

    prob_confidence = _confidence(confidence, recent_form, h2h, flags)
    pick_probability = round(clamp(0.50 + raw_edge * prob_confidence, 0.05, 0.95), 4)
    opponent_probability = round(1.0 - pick_probability, 4)

    pick_is_winner = pick_probability >= opponent_probability
    winner = pick if pick_is_winner else opponent
    winner_side = pick_side if pick_is_winner else opponent_side
    loser = opponent if pick_is_winner else pick
    loser_side = opponent_side if pick_is_winner else pick_side
    winner_probability = max(pick_probability, opponent_probability)

    status = "OK"
    if elo.get("status") != "OK" and recent_form.get("status") != "OK" and abs(raw_edge) < 0.0001:
        status = "LOW_DATA"

    display = {
        "winner": winner,
        "probability": f"{winner_probability * 100:.1f}%",
        "pick_probability": f"{pick_probability * 100:.1f}%",
        "edge": f"{raw_edge * 100:+.1f}%",
        "confidence": f"{prob_confidence * 100:.1f}%",
    }

    return {
        "status": status,
        "model_version": "THINQ_PROBABILITY_V1",
        "pick": pick,
        "pick_side": pick_side,
        "opponent": opponent,
        "opponent_side": opponent_side,
        "pick_probability": pick_probability,
        "pick_probability_pct": round(pick_probability * 100.0, 2),
        "opponent_probability": opponent_probability,
        "opponent_probability_pct": round(opponent_probability * 100.0, 2),
        "winner": winner,
        "winner_side": winner_side,
        "winner_probability": round(winner_probability, 4),
        "winner_probability_pct": round(winner_probability * 100.0, 2),
        "loser": loser,
        "loser_side": loser_side,
        "edge": raw_edge,
        "winner_edge": round(abs(winner_probability - 0.50), 4),
        "confidence": prob_confidence,
        "components": components,
        "form_family_edge": round(form_family, 4),
        "sets_games_edge": round(sets_games_family, 4),
        "display": display,
        "flags": sorted(set(flags)),
    }
