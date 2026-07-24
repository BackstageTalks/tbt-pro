"""THINQ Match Dynamics / Sets-Games layer.

This module produces ready intelligence output for match shape, projected
sets/games and conservative Sets/Games edges. It does not create final CORQ
probability and does not require adapter logic.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def surface_bucket(surface: Optional[str]) -> str:
    text = str(surface or "").strip().lower()
    if "grass" in text:
        return "Grass"
    if "clay" in text:
        return "Clay"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def build_match_dynamics_context(
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    best_of: int = 3,
    elo: Optional[Dict[str, Any]] = None,
    h2h: Optional[Dict[str, Any]] = None,
    recent_form: Optional[Dict[str, Any]] = None,
    edges: Optional[Dict[str, Any]] = None,
    odds_player1: Any = None,
    odds_player2: Any = None,
    pick_odds: Any = None,
    opponent_odds: Any = None,
) -> Dict[str, Any]:
    elo = elo if isinstance(elo, dict) else {}
    h2h = h2h if isinstance(h2h, dict) else {}
    recent_form = recent_form if isinstance(recent_form, dict) else {}
    edges = edges if isinstance(edges, dict) else {}

    try:
        best_of_int = int(best_of or 3)
    except Exception:
        best_of_int = 3
    if best_of_int not in (3, 5):
        best_of_int = 3

    surface_name = surface_bucket(surface)

    elo_edge = as_float(elo.get("elo_edge"))
    if elo_edge is None:
        elo_edge = as_float(edges.get("elo_edge")) or 0.0

    h2h_edge = as_float(h2h.get("edge"))
    if h2h_edge is None:
        h2h_edge = as_float(h2h.get("h2h_edge"))
    if h2h_edge is None:
        h2h_edge = as_float(edges.get("h2h_edge")) or 0.0

    recent_edge = as_float(recent_form.get("recent_form_edge"))
    if recent_edge is None:
        recent_edge = as_float(edges.get("recent_form_edge")) or 0.0

    surface_form_edge = as_float(recent_form.get("surface_recent_form_edge"))
    if surface_form_edge is None:
        surface_form_edge = as_float(edges.get("surface_form_edge"))
    if surface_form_edge is None:
        surface_form_edge = as_float(edges.get("surface_recent_form_edge")) or 0.0

    composite_edge = (
        0.55 * elo_edge
        + 0.20 * h2h_edge
        + 0.15 * recent_edge
        + 0.10 * surface_form_edge
    )
    composite_edge = clamp(composite_edge, -0.12, 0.12)
    closeness = 1.0 - clamp(abs(composite_edge) / 0.12, 0.0, 1.0)

    p_pick_odds = as_float(pick_odds)
    p_opp_odds = as_float(opponent_odds)
    if p_pick_odds and p_opp_odds and p_pick_odds > 1.0 and p_opp_odds > 1.0:
        odds_gap_pct = abs(p_pick_odds - p_opp_odds) / max(min(p_pick_odds, p_opp_odds), 1.01)
        market_closeness = 1.0 - clamp(odds_gap_pct / 0.75, 0.0, 1.0)
        closeness = round((0.70 * closeness) + (0.30 * market_closeness), 4)
    else:
        odds_gap_pct = None

    if surface_name == "Grass":
        tiebreak_base = 0.34
        games_base = 22.2 if best_of_int == 3 else 37.0
    elif surface_name == "Hard":
        tiebreak_base = 0.28
        games_base = 21.8 if best_of_int == 3 else 36.0
    elif surface_name == "Clay":
        tiebreak_base = 0.20
        games_base = 21.0 if best_of_int == 3 else 35.0
    else:
        tiebreak_base = 0.24
        games_base = 21.4 if best_of_int == 3 else 35.5

    if best_of_int == 3:
        decider_probability = clamp(0.22 + 0.36 * closeness, 0.18, 0.62)
        straight_sets_probability = clamp(1.0 - decider_probability, 0.38, 0.82)
        projected_sets = 2.0 + decider_probability
        projected_games = games_base + 5.2 * decider_probability + 1.6 * closeness
    else:
        decider_probability = clamp(0.14 + 0.26 * closeness, 0.10, 0.48)
        straight_sets_probability = clamp(0.34 - 0.16 * closeness, 0.16, 0.42)
        projected_sets = 3.0 + 1.05 * closeness + 0.70 * decider_probability
        projected_games = games_base + 8.0 * closeness + 5.0 * decider_probability

    tiebreak_probability = clamp(tiebreak_base + 0.18 * closeness, 0.12, 0.58)

    dominance = clamp(abs(composite_edge) / 0.12, 0.0, 1.0)
    direction = 1.0 if composite_edge >= 0 else -1.0
    sets_edge = direction * clamp((straight_sets_probability - 0.50) * dominance * 0.08, -0.025, 0.025)
    games_edge = direction * clamp((1.0 - closeness) * dominance * 0.025, 0.0, 0.025)
    tiebreak_edge = direction * clamp((tiebreak_probability - tiebreak_base) * dominance * 0.05, -0.015, 0.015)
    decider_edge = direction * clamp((decider_probability - 0.40) * dominance * 0.05, -0.015, 0.015)

    if closeness >= 0.70:
        match_shape = "CLOSE_DECIDER_LEAN"
    elif straight_sets_probability >= 0.66:
        match_shape = "STRAIGHT_SETS_LEAN"
    else:
        match_shape = "BALANCED_STANDARD"

    confidence = 0.25
    if elo.get("status") == "OK" or edges.get("elo_edge") is not None:
        confidence += 0.30
    if h2h.get("status") == "OK" or edges.get("h2h_edge") is not None:
        confidence += 0.12
    if recent_form.get("status") == "OK" or edges.get("recent_form_edge") is not None:
        confidence += 0.10
    if surface_name != "Unknown":
        confidence += 0.08
    if p_pick_odds and p_opp_odds:
        confidence += 0.05
    confidence = clamp(confidence, 0.0, 0.78)

    flags = []
    if not (h2h.get("status") == "OK" or edges.get("h2h_edge") is not None):
        flags.append("MATCH_DYNAMICS_H2H_NEUTRAL")
    if not (recent_form.get("status") == "OK" or edges.get("recent_form_edge") is not None):
        flags.append("MATCH_DYNAMICS_RECENT_FORM_NEUTRAL")
    if surface_name == "Unknown":
        flags.append("MATCH_DYNAMICS_SURFACE_UNKNOWN")

    return {
        "status": "OK",
        "source": "thinq_match_dynamics_v1",
        "pick": pick,
        "opponent": opponent,
        "surface": surface_name,
        "best_of": best_of_int,
        "composite_edge": round(composite_edge, 4),
        "closeness_index": round(closeness, 4),
        "match_shape": match_shape,
        "projected_sets": round(projected_sets, 2),
        "projected_games": round(projected_games, 1),
        "tiebreak_probability": round(tiebreak_probability, 4),
        "decider_probability": round(decider_probability, 4),
        "straight_sets_probability": round(straight_sets_probability, 4),
        "sets_edge": round(sets_edge, 4),
        "games_edge": round(games_edge, 4),
        "tiebreak_edge": round(tiebreak_edge, 4),
        "decider_edge": round(decider_edge, 4),
        "confidence": round(confidence, 4),
        "odds_gap_pct": round(odds_gap_pct, 4) if odds_gap_pct is not None else None,
        "flags": flags,
    }


# Compatibility wrapper for older THINQ service imports that expect
# build_match_dynamics(raw, edges, surface, best_of).
def build_match_dynamics(raw: Dict[str, Any], edges: Dict[str, Any], surface: Optional[str] = None, best_of: int = 3) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    p1 = raw.get("player1") if isinstance(raw.get("player1"), dict) else {}
    p2 = raw.get("player2") if isinstance(raw.get("player2"), dict) else {}
    pick = raw.get("pick") or p1.get("name") or raw.get("player1_name") or "player1"
    opponent = raw.get("opponent") or p2.get("name") or raw.get("player2_name") or "player2"
    return build_match_dynamics_context(
        pick=pick,
        opponent=opponent,
        surface=surface or raw.get("surface"),
        best_of=best_of,
        edges=edges,
    )
