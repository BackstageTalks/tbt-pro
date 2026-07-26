
"""UI value formatting helpers for CorQ web render.

This helper prevents the common bug where every negative number is orange.
Values must be colored by their meaning for the displayed pick, not by the
literal sign alone.
"""

from __future__ import annotations

from typing import Any, Optional


def to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def support_class(value: Any, *, perspective: str = "pick") -> str:
    """Return CSS class for a numeric edge.

    perspective="pick": positive supports pick, negative goes against pick.
    perspective="opp": negative supports pick, positive goes against pick.
    """
    val = to_float(value)
    if val is None or abs(val) < 1e-9:
        return "val-neutral"
    if perspective == "opp":
        return "val-good" if val < 0 else "val-against"
    return "val-good" if val > 0 else "val-against"


def h2h_record_class(pick_wins: Any, opp_wins: Any) -> str:
    pw = to_float(pick_wins) or 0.0
    ow = to_float(opp_wins) or 0.0
    if pw > ow:
        return "val-good"
    if pw < ow:
        return "val-against"
    return "val-neutral"


def format_edge_support(value: Any) -> str:
    """Format pick-perspective edge as '+x.x% / Support' or '-x.x% / Against'."""
    val = to_float(value)
    if val is None:
        return "— / Neutral"
    pct = val * 100 if abs(val) <= 1 else val
    if pct > 0.0001:
        return f"+{pct:.1f}% / Support"
    if pct < -0.0001:
        return f"{pct:.1f}% / Against"
    return "0.0% / Neutral"


def format_pct_signed(value: Any) -> str:
    val = to_float(value)
    if val is None:
        return "—"
    pct = val * 100 if abs(val) <= 1 else val
    return f"{pct:+.1f}%"


def progress_bar(percent_value: Any, width: int = 10) -> str:
    val = to_float(percent_value)
    if val is None:
        return "[░░░░░░░░░░]"
    pct = val * 100 if val <= 1 else val
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
