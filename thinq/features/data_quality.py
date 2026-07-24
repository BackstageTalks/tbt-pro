"""
THINQ Data Quality / Confidence

Creates quality flags for CORQ so weak samples do not look as strong as reliable data.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _history(raw: Dict[str, Any], side: str) -> Dict[str, Any]:
    player = raw.get(side, {}) if isinstance(raw.get(side), dict) else {}
    return player.get("history", player.get("history", {})) if isinstance(player, dict) else {}


def build_data_quality(raw: Dict[str, Any], edges: Dict[str, Any]) -> Dict[str, Any]:
    p1_hist = _history(raw, "player1")
    p2_hist = _history(raw, "player2")
    h2h = raw.get("h2h", {}) if isinstance(raw.get("h2h"), dict) else {}

    p1_total = _num(p1_hist.get("sample_size_matches"))
    p2_total = _num(p2_hist.get("sample_size_matches"))
    p1_surface = _num(p1_hist.get("surface_sample_size_52w"))
    p2_surface = _num(p2_hist.get("surface_sample_size_52w"))
    h2h_total = _num(h2h.get("h2h_total_matches"))

    available_edges = sum(1 for value in edges.values() if value is not None)
    total_edges = max(len(edges), 1)
    edge_coverage = available_edges / total_edges

    history_score = min(min(p1_total, p2_total) / 30, 1.0)
    surface_score = min(min(p1_surface, p2_surface) / 10, 1.0)
    h2h_score = min(h2h_total / 5, 1.0) if h2h_total else 0.0

    score = (0.45 * history_score) + (0.25 * surface_score) + (0.15 * h2h_score) + (0.15 * edge_coverage)
    score = round(max(min(score, 1.0), 0.0), 4)

    flags: List[str] = []
    if min(p1_total, p2_total) < 10:
        flags.append("THIN_HISTORY_SAMPLE")
    if min(p1_surface, p2_surface) < 5:
        flags.append("THIN_SURFACE_SAMPLE")
    if h2h_total == 0:
        flags.append("NO_H2H_DATA")
    if edge_coverage < 0.4:
        flags.append("THINQ_LOW_FEATURE_COVERAGE")

    if score >= 0.75:
        quality = "STRONG"
    elif score >= 0.50:
        quality = "OK"
    elif score >= 0.30:
        quality = "THIN"
    else:
        quality = "WEAK"

    return {
        "data_quality": quality,
        "data_quality_score": score,
        "history_min_sample": int(min(p1_total, p2_total)),
        "surface_min_sample": int(min(p1_surface, p2_surface)),
        "h2h_sample": int(h2h_total),
        "edge_coverage": round(edge_coverage, 4),
        "flags": flags,
    }
