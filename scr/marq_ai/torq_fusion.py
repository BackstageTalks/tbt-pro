from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


TORQ_MIN_PROBABILITY = env_float("TORQ_MIN_PROBABILITY", 0.60)
TORQ_MIN_AI_MATCH = env_float("TORQ_MIN_AI_MATCH", 70.0)
TORQ_TOP_MIN_ODDS = env_float("TORQ_TOP_MIN_ODDS", 1.50)
TORQ_TOP_MAX_ODDS = env_float("TORQ_TOP_MAX_ODDS", 3.50)
B_HAND_MIN_SELECTED_ODDS = env_float("B_HAND_MIN_SELECTED_ODDS", 1.75)
B_HAND_MAX_SELECTED_ODDS = env_float("B_HAND_MAX_SELECTED_ODDS", 2.50)
B_HAND_MAX_MARKET_GAP_PP = env_float("B_HAND_MAX_MARKET_GAP_PP", 12.0)
B_HAND_MIN_EDGE_PP = env_float("B_HAND_MIN_EDGE_PP", 4.0)
B_HAND_MIN_AI_MATCH = env_float("B_HAND_MIN_AI_MATCH", 65.0)


def ai_match_from_probabilities(long_probability: Optional[float], short_probability: Optional[float]) -> Tuple[Optional[float], Optional[float], str]:
    if long_probability is None or short_probability is None:
        return None, None, "NO_SHORT_DATA"
    gap = abs(long_probability - short_probability)
    ai_match = clamp(100.0 - gap * 200.0, 0.0, 100.0)
    if gap <= 0.04:
        status = "STRONG_ALIGN"
    elif gap <= 0.08:
        status = "ALIGN"
    elif gap <= 0.14:
        status = "MIXED"
    else:
        status = "DISAGREE"
    return round(ai_match, 1), round(gap, 4), status


def implied_probability(odds: Any) -> Optional[float]:
    decimal = safe_float(odds)
    if decimal is None or decimal <= 1.0:
        return None
    return 1.0 / decimal


def no_vig_market_probability(odds_a: Any, odds_b: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    raw_a = implied_probability(odds_a)
    raw_b = implied_probability(odds_b)
    if raw_a is None or raw_b is None:
        return None, None, None
    total = raw_a + raw_b
    if total <= 0:
        return None, None, None
    p_a = raw_a / total
    p_b = raw_b / total
    return p_a, p_b, abs(p_a - p_b) * 100.0


def build_torq_prediction(item: Dict[str, Any]) -> Dict[str, Any]:
    corq = safe_float(item.get("corq_ai_probability"))
    if corq is None:
        corq = safe_float(item.get("base_probability"))
    if corq is None:
        corq = safe_float(item.get("probability"), 0.5)
    bst = safe_float(item.get("bst_ai_probability"))
    form_adj = clamp(safe_float(item.get("form_adjustment"), 0.0) or 0.0, -0.05, 0.05)
    form_component = clamp(0.5 + form_adj, 0.35, 0.65)
    if bst is not None:
        torq = 0.55 * corq + 0.30 * bst + 0.10 * form_component + 0.05 * 0.5
    else:
        torq = 0.80 * corq + 0.15 * form_component + 0.05 * 0.5
    torq = clamp(torq, 0.15, 0.85)
    ai_match, ai_gap, alignment = ai_match_from_probabilities(corq, bst)
    existing_ai_match = safe_float(item.get("ai_match"))
    if existing_ai_match is not None:
        ai_match = existing_ai_match * 100.0 if existing_ai_match <= 1.0 else existing_ai_match
        ai_match = round(clamp(ai_match, 0.0, 100.0), 1)
    odds = safe_float(item.get("odds"))
    odds_quality = 1.0 if odds is not None and TORQ_TOP_MIN_ODDS <= odds <= TORQ_TOP_MAX_ODDS else 0.0
    data_points = sum([
        corq is not None,
        bst is not None,
        odds is not None,
        bool(item.get("player1") and item.get("player2")),
        bool(item.get("surface")),
    ])
    data_quality_score = data_points / 5.0
    data_quality = "GOOD" if data_quality_score >= 0.80 else "OK" if data_quality_score >= 0.60 else "THIN"
    market = str(item.get("torq_market_status") or item.get("marq_ai_signal") or "NO_DATA").upper()
    market_bonus = 0.06 if market in {"ALIGN", "CONFIRM", "CONFIRMED", "CONSENSUS"} else -0.08 if market in {"DISAGREE", "AGAINST"} else -0.14 if market in {"THIN", "OUTLIER"} else 0.0
    confidence = clamp(torq * 0.45 + ((ai_match or 50.0) / 100.0) * 0.20 + data_quality_score * 0.15 + odds_quality * 0.10 + 0.10 + market_bonus, 0.0, 1.0)
    reasons = []
    if bst is None:
        reasons.append("NO_SHORT_XML_ELO")
    if alignment in {"STRONG_ALIGN", "ALIGN"}:
        reasons.append("LONG_SHORT_ALIGN")
    elif alignment == "DISAGREE":
        reasons.append("LONG_SHORT_DISAGREE")
    if odds is None:
        reasons.append("NO_ODDS")
    out = dict(item)
    out.update({
        "model": "Torq AI",
        "torq_probability": round(torq, 3),
        "probability": round(torq, 3),
        "torq_confidence": round(confidence, 3),
        "confidence_score": round(confidence, 3),
        "torq_ai_match": ai_match,
        "ai_match": ai_match,
        "torq_ai_gap": ai_gap,
        "torq_alignment": alignment,
        "torq_data_quality_score": round(data_quality_score, 3),
        "torq_data_quality": data_quality,
        "torq_reason": ", ".join(reasons) if reasons else "TORQ_OK",
    })
    return out


def is_torq_top_candidate(item: Dict[str, Any]) -> bool:
    probability = safe_float(item.get("torq_probability") or item.get("probability"))
    confidence = safe_float(item.get("torq_confidence") or item.get("confidence_score"), 0.0) or 0.0
    ai_match = safe_float(item.get("torq_ai_match") or item.get("ai_match"), 0.0) or 0.0
    odds = safe_float(item.get("odds"))
    alignment = str(item.get("torq_alignment") or "").upper()
    quality = str(item.get("torq_data_quality") or "").upper()
    market = str(item.get("torq_market_status") or item.get("marq_ai_signal") or "").upper()
    return (
        probability is not None and probability >= TORQ_MIN_PROBABILITY
        and odds is not None and TORQ_TOP_MIN_ODDS <= odds <= TORQ_TOP_MAX_ODDS
        and ai_match >= TORQ_MIN_AI_MATCH
        and alignment != "DISAGREE"
        and quality in {"GOOD", "OK"}
        and market not in {"THIN", "OUTLIER"}
        and confidence >= 0.62
    )


def build_b_hand_candidate(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    odds1 = safe_float(item.get("odds_player1"))
    odds2 = safe_float(item.get("odds_player2"))
    if odds1 is None or odds2 is None:
        return None
    market_p1, market_p2, market_gap_pp = no_vig_market_probability(odds1, odds2)
    if market_p1 is None or market_p2 is None or market_gap_pp is None or market_gap_pp > B_HAND_MAX_MARKET_GAP_PP:
        return None
    pick, p1, p2 = str(item.get("pick") or ""), str(item.get("player1") or ""), str(item.get("player2") or "")
    selected_probability = safe_float(item.get("torq_probability") or item.get("probability"))
    if selected_probability is None:
        return None
    if pick == p1:
        torq_p1, torq_p2 = selected_probability, 1.0 - selected_probability
    elif pick == p2:
        torq_p2, torq_p1 = selected_probability, 1.0 - selected_probability
    else:
        return None
    edge1, edge2 = torq_p1 - market_p1, torq_p2 - market_p2
    if edge1 >= edge2:
        selected, selected_odds, selected_torq, selected_market, selected_edge = p1, odds1, torq_p1, market_p1, edge1
    else:
        selected, selected_odds, selected_torq, selected_market, selected_edge = p2, odds2, torq_p2, market_p2, edge2
    ai_match = safe_float(item.get("torq_ai_match") or item.get("ai_match"), 0.0) or 0.0
    if not (B_HAND_MIN_SELECTED_ODDS <= selected_odds <= B_HAND_MAX_SELECTED_ODDS):
        return None
    if selected_edge * 100.0 < B_HAND_MIN_EDGE_PP or ai_match < B_HAND_MIN_AI_MATCH:
        return None
    out = dict(item)
    out.update({
        "model": "Torq B-Hand",
        "pick": selected,
        "odds": round(selected_odds, 3),
        "b_hand": True,
        "b_hand_market_gap_pp": round(market_gap_pp, 2),
        "b_hand_market_probability": round(selected_market, 3),
        "b_hand_torq_probability": round(selected_torq, 3),
        "b_hand_edge": round(selected_edge, 4),
        "b_hand_edge_pp": round(selected_edge * 100.0, 2),
        "b_hand_reason": "Balanced market value edge selected by Torq AI",
        "torq_probability": round(selected_torq, 3),
        "probability": round(selected_torq, 3),
    })
    return out
