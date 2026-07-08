from __future__ import annotations

from typing import Any, Dict


def classify_marq_for_torq(item: Dict[str, Any]) -> Dict[str, Any]:
    signal = str(item.get("marq_ai_signal") or item.get("marq_ai_direction") or "NO_DATA").upper()
    status = "NO_MARKET_DATA"
    bonus = 0.0
    reason = "No stable Marq market signal available"
    if signal in {"ALIGN", "CONFIRM", "CONFIRMED", "CONSENSUS"}:
        status, bonus, reason = "ALIGN", 0.06, "Market movement confirms Torq side"
    elif signal in {"DISAGREE", "AGAINST"}:
        status, bonus, reason = "DISAGREE", -0.08, "Market movement disagrees with Torq side"
    elif signal in {"THIN", "OUTLIER"}:
        status, bonus, reason = signal, -0.14, "Market quality is weak for TOP selection"
    elif signal in {"MIXED", "NEUTRAL"}:
        status, bonus, reason = "MIXED", -0.02, "Market movement is mixed"
    return {
        "torq_market_status": status,
        "torq_market_bonus": bonus,
        "torq_market_reason": reason,
        "torq_market_strength": item.get("marq_ai_strength"),
        "torq_market_move_pct": item.get("marq_market_move_pct"),
        "torq_market_probability_change_pp": item.get("marq_probability_change_pp"),
    }


def attach_torq_market(item: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(item)
    updated.update(classify_marq_for_torq(item))
    return updated
