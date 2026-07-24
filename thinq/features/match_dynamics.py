"""
THINQ Match Dynamics

Purpose:
- Provide set, games and tiebreak intelligence for CORQ.
- This is not a standalone prediction model.
- Positive edge values favor player1, negative edge values favor player2.

Outputs:
- projected_sets
- straight_sets_probability
- decider_probability
- projected_games
- tiebreak_probability
- sets_edge
- games_edge
- tiebreak_edge
- decider_edge
- confidence

Design:
- Uses currently available THINQ inputs first: History, ELO, H2H and optional Style.
- If Style / Match Charting is not connected yet, formulas degrade safely.
- CORQ remains responsible for final prediction, ranking and TOP outputs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(min(value, high), low)


def _history(raw: Dict[str, Any], side: str) -> Dict[str, Any]:
    player = raw.get(side, {}) if isinstance(raw.get(side), dict) else {}
    if not isinstance(player, dict):
        return {}
    # Backward-compatible with temporary older names if old cache exists.
    return player.get("history", player.get("historyq", {})) if isinstance(player, dict) else {}


def _elo(raw: Dict[str, Any], side: str) -> Dict[str, Any]:
    player = raw.get(side, {}) if isinstance(raw.get(side), dict) else {}
    if not isinstance(player, dict):
        return {}
    return player.get("elo", player.get("eloq", {})) if isinstance(player, dict) else {}


def _style(raw: Dict[str, Any], side: str) -> Dict[str, Any]:
    player = raw.get(side, {}) if isinstance(raw.get(side), dict) else {}
    if not isinstance(player, dict):
        return {}
    return player.get("style", {}) if isinstance(player, dict) else {}


def _surface_elo_key(surface: Optional[str]) -> Optional[str]:
    if not surface:
        return None
    value = str(surface).strip().lower()
    mapping = {
        "hard": "hard_elo",
        "clay": "clay_elo",
        "grass": "grass_elo",
        "indoor": "indoor_elo",
        "indoor hard": "indoor_elo",
        "i.hard": "indoor_elo",
    }
    return mapping.get(value)


def _elo_values(raw: Dict[str, Any], surface: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    p1_elo = _elo(raw, "player1")
    p2_elo = _elo(raw, "player2")
    surface_key = _surface_elo_key(surface)

    p1 = p2 = None
    if surface_key:
        p1 = _float(p1_elo.get(surface_key))
        p2 = _float(p2_elo.get(surface_key))

    if p1 is None or p2 is None:
        p1 = _float(p1_elo.get("elo"))
        p2 = _float(p2_elo.get("elo"))

    return p1, p2


def _close_match_index(raw: Dict[str, Any], edges: Dict[str, Any], surface: Optional[str]) -> float:
    """
    0.0 = not close, 1.0 = very close.
    Uses ELO diff first, then available THINQ edges.
    """
    p1_elo, p2_elo = _elo_values(raw, surface)
    if p1_elo is not None and p2_elo is not None:
        diff = abs(p1_elo - p2_elo)
        return round(_clamp(1.0 - (diff / 300.0), 0.0, 1.0), 4)

    usable = []
    for key in ["surface_form_edge", "recent_form_edge", "elo_edge", "h2h_edge", "ta_edge"]:
        value = _float(edges.get(key))
        if value is not None:
            usable.append(abs(value))
    if not usable:
        return 0.5

    avg_edge = sum(usable) / len(usable)
    return round(_clamp(1.0 - (avg_edge / 0.12), 0.0, 1.0), 4)


def _favorite_strength(raw: Dict[str, Any], edges: Dict[str, Any], surface: Optional[str]) -> float:
    """
    0.0 = no clear favorite, 1.0 = very strong favorite.
    Direction is not needed for sets/games/tiebreak risk.
    """
    return round(1.0 - _close_match_index(raw, edges, surface), 4)


def _surface_tb_base(surface: Optional[str]) -> float:
    value = str(surface or "").strip().lower()
    if value in ["grass", "indoor", "indoor hard", "i.hard"]:
        return 0.34
    if value == "hard":
        return 0.29
    if value == "clay":
        return 0.22
    return 0.27


def _serve_return_tb_adjustment(raw: Dict[str, Any]) -> Tuple[float, float]:
    """
    Uses future Style fields when available.
    Returns adjustment and style confidence contribution.
    """
    p1_style = _style(raw, "player1")
    p2_style = _style(raw, "player2")

    p1_serve = _float(p1_style.get("serve_strength"))
    p2_serve = _float(p2_style.get("serve_strength"))
    p1_return = _float(p1_style.get("return_strength"))
    p2_return = _float(p2_style.get("return_strength"))
    p1_conf = _float(p1_style.get("style_confidence"), 0.0) or 0.0
    p2_conf = _float(p2_style.get("style_confidence"), 0.0) or 0.0

    values = [v for v in [p1_serve, p2_serve, p1_return, p2_return] if v is not None]
    if len(values) < 4:
        return 0.0, 0.0

    # Higher serve and lower return profiles increase tiebreak risk.
    serve_avg = (p1_serve + p2_serve) / 2.0
    return_avg = (p1_return + p2_return) / 2.0
    adjustment = _clamp((serve_avg - return_avg) * 0.08, -0.05, 0.05)
    confidence = _clamp((p1_conf + p2_conf) / 2.0, 0.0, 1.0)
    return round(adjustment, 4), round(confidence, 4)


def _h2h_dynamics(raw: Dict[str, Any]) -> Dict[str, Any]:
    h2h = raw.get("h2h", {}) if isinstance(raw.get("h2h"), dict) else {}
    total = _float(h2h.get("h2h_total_matches"), 0.0) or 0.0
    confidence = _float(h2h.get("h2h_confidence"), 0.0) or 0.0

    return {
        "h2h_sample": int(total),
        "h2h_confidence": confidence,
    }


def build_match_dynamics(
    raw: Dict[str, Any],
    edges: Dict[str, Any],
    surface: Optional[str] = None,
    best_of: int = 3,
) -> Dict[str, Any]:
    """
    Build sets/games/tiebreak context.

    The values are intentionally conservative until Style and richer score history are connected.
    """
    close_index = _close_match_index(raw, edges, surface)
    favorite_strength = _favorite_strength(raw, edges, surface)
    h2h_ctx = _h2h_dynamics(raw)
    style_tb_adjustment, style_confidence = _serve_return_tb_adjustment(raw)

    # Decider probability: close match => higher decider probability.
    if best_of == 5:
        # Decider in BO5 means fifth set; naturally lower than BO3 third-set probability.
        decider_probability = 0.16 + (0.18 * close_index) - (0.06 * favorite_strength)
        projected_sets = 3.20 + (0.95 * close_index) - (0.35 * favorite_strength)
    else:
        decider_probability = 0.24 + (0.28 * close_index) - (0.10 * favorite_strength)
        projected_sets = 2.00 + decider_probability

    decider_probability = round(_clamp(decider_probability, 0.10, 0.58), 4)
    projected_sets = round(_clamp(projected_sets, 2.0 if best_of == 3 else 3.0, float(best_of)), 4)

    straight_sets_probability = None
    if best_of == 3:
        straight_sets_probability = round(_clamp(1.0 - decider_probability, 0.42, 0.90), 4)

    # Tiebreak probability: surface + closeness + Style adjustment.
    tb_base = _surface_tb_base(surface)
    tiebreak_probability = tb_base + (0.12 * close_index) + style_tb_adjustment
    tiebreak_probability = round(_clamp(tiebreak_probability, 0.12, 0.55), 4)

    # Games projection: BO3 baseline around 21.5, close/TB push it higher.
    if best_of == 5:
        projected_games = 34.0 + (7.0 * close_index) + (3.5 * tiebreak_probability) - (3.0 * favorite_strength)
    else:
        projected_games = 20.0 + (3.2 * close_index) + (2.2 * tiebreak_probability) - (1.4 * favorite_strength)
    projected_games = round(_clamp(projected_games, 16.0 if best_of == 3 else 26.0, 30.0 if best_of == 3 else 60.0), 2)

    # Edge outputs are context edges for CORQ, not betting picks.
    # Positive values mean "more match volatility / longer match risk" from player1-neutral context.
    games_edge = round(_clamp((projected_games - (21.5 if best_of == 3 else 38.5)) / 100.0, -0.05, 0.05), 4)
    tiebreak_edge = round(_clamp((tiebreak_probability - tb_base) * 0.35, -0.04, 0.04), 4)
    decider_edge = round(_clamp((decider_probability - (0.36 if best_of == 3 else 0.24)) * 0.25, -0.04, 0.04), 4)
    sets_edge = round(_clamp(decider_edge + (favorite_strength * -0.01), -0.04, 0.04), 4)

    # Confidence: strong when ELO/edges are present, Style improves TB part, H2H adds small support.
    available_core = sum(1 for key in ["elo_edge", "surface_form_edge", "recent_form_edge", "h2h_edge"] if edges.get(key) is not None)
    core_confidence = available_core / 4.0
    confidence = (0.65 * core_confidence) + (0.20 * style_confidence) + (0.15 * h2h_ctx["h2h_confidence"])
    confidence = round(_clamp(confidence, 0.0, 1.0), 4)

    flags = []
    if close_index >= 0.75:
        flags.append("MATCH_DYNAMICS_CLOSE_MATCH")
    if decider_probability >= 0.45 and best_of == 3:
        flags.append("MATCH_DYNAMICS_HIGH_DECIDER_RISK")
    if tiebreak_probability >= 0.38:
        flags.append("MATCH_DYNAMICS_HIGH_TIEBREAK_RISK")
    if projected_games >= (23.5 if best_of == 3 else 43.5):
        flags.append("MATCH_DYNAMICS_HIGH_GAMES_PROJECTION")
    if confidence < 0.35:
        flags.append("MATCH_DYNAMICS_LOW_CONFIDENCE")

    return {
        "projected_sets": projected_sets,
        "straight_sets_probability": straight_sets_probability,
        "decider_probability": decider_probability,
        "projected_games": projected_games,
        "tiebreak_probability": tiebreak_probability,
        "sets_edge": sets_edge,
        "games_edge": games_edge,
        "tiebreak_edge": tiebreak_edge,
        "decider_edge": decider_edge,
        "close_match_index": close_index,
        "favorite_strength_index": favorite_strength,
        "style_confidence_used": style_confidence,
        "h2h_sample_used": h2h_ctx["h2h_sample"],
        "confidence": confidence,
        "flags": flags,
    }
