from __future__ import annotations
from typing import Any, Optional

def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def implied_probability(decimal_odds: Any) -> Optional[float]:
    odds = to_float(decimal_odds)
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds
