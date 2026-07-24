"""THINQ Recent Form feature.

This is a standalone THINQ item intended for display in the THINQ column and
for use as a soft CORQ edge.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from thinq.loaders.history_loader import available_history_sources, player_matches, normalize_surface_label


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def win_rate(matches: List[Dict[str, Any]], player: str) -> Optional[float]:
    if not matches:
        return None
    from thinq.loaders.history_loader import normalize_name
    key = normalize_name(player)
    wins = sum(1 for match in matches if match.get("winner_key") == key)
    return wins / len(matches)


def wins_count(matches: List[Dict[str, Any]], player: str) -> int:
    from thinq.loaders.history_loader import normalize_name
    key = normalize_name(player)
    return sum(1 for match in matches if match.get("winner_key") == key)


def avg_opponent_rank(matches: List[Dict[str, Any]], player: str) -> Optional[float]:
    from thinq.loaders.history_loader import normalize_name
    key = normalize_name(player)
    ranks: List[int] = []
    for match in matches:
        if match.get("winner_key") == key and match.get("loser_rank"):
            ranks.append(int(match.get("loser_rank")))
        elif match.get("loser_key") == key and match.get("winner_rank"):
            ranks.append(int(match.get("winner_rank")))
    if not ranks:
        return None
    return sum(ranks) / len(ranks)


def form_edge(pick_rate: Optional[float], opponent_rate: Optional[float], cap: float) -> float:
    if pick_rate is None or opponent_rate is None:
        return 0.0
    return round(clamp((pick_rate - opponent_rate) * 0.12, -cap, cap), 4)


def ranking_quality_edge(pick_avg_rank: Optional[float], opponent_avg_rank: Optional[float]) -> float:
    if pick_avg_rank is None or opponent_avg_rank is None:
        return 0.0
    # Better opponent quality means lower average rank number.
    diff = opponent_avg_rank - pick_avg_rank
    return round(clamp(diff / 1000.0, -0.03, 0.03), 4)


def build_recent_form_context(pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    sources = available_history_sources()
    if not sources:
        return {
            "status": "NO_DATA",
            "source": None,
            "reason": "No local history files found",
            "flags": ["RECENT_FORM_NO_DATA"],
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
        }

    pick_last10 = player_matches(pick, limit=10)
    opponent_last10 = player_matches(opponent, limit=10)
    pick_last5 = pick_last10[:5]
    opponent_last5 = opponent_last10[:5]

    surface_bucket = normalize_surface_label(surface) if surface else None
    pick_surface10 = player_matches(pick, limit=10, surface=surface_bucket) if surface_bucket else []
    opponent_surface10 = player_matches(opponent, limit=10, surface=surface_bucket) if surface_bucket else []

    pick_last10_rate = win_rate(pick_last10, pick)
    opponent_last10_rate = win_rate(opponent_last10, opponent)
    pick_last5_rate = win_rate(pick_last5, pick)
    opponent_last5_rate = win_rate(opponent_last5, opponent)
    pick_surface_rate = win_rate(pick_surface10, pick)
    opponent_surface_rate = win_rate(opponent_surface10, opponent)

    pick_avg_rank = avg_opponent_rank(pick_last10, pick)
    opponent_avg_rank = avg_opponent_rank(opponent_last10, opponent)

    recent_edge = form_edge(pick_last10_rate, opponent_last10_rate, cap=0.04)
    short_edge = form_edge(pick_last5_rate, opponent_last5_rate, cap=0.03)
    surface_edge = form_edge(pick_surface_rate, opponent_surface_rate, cap=0.04)
    quality_edge = ranking_quality_edge(pick_avg_rank, opponent_avg_rank)

    sample = len(pick_last10) + len(opponent_last10)
    surface_sample = len(pick_surface10) + len(opponent_surface10)
    confidence = min(0.15 + sample * 0.035 + surface_sample * 0.015, 0.75)

    flags: List[str] = []
    if len(pick_last10) < 3:
        flags.append("RECENT_FORM_THIN_PICK")
    if len(opponent_last10) < 3:
        flags.append("RECENT_FORM_THIN_OPPONENT")
    if surface_bucket and (len(pick_surface10) < 2 or len(opponent_surface10) < 2):
        flags.append("SURFACE_RECENT_FORM_THIN")

    return {
        "status": "OK" if sample > 0 else "NO_DATA",
        "source": sources[:5],
        "surface": surface_bucket,
        "pick_last5_wins": wins_count(pick_last5, pick),
        "opponent_last5_wins": wins_count(opponent_last5, opponent),
        "pick_last5_matches": len(pick_last5),
        "opponent_last5_matches": len(opponent_last5),
        "pick_last10_wins": wins_count(pick_last10, pick),
        "opponent_last10_wins": wins_count(opponent_last10, opponent),
        "pick_last10_matches": len(pick_last10),
        "opponent_last10_matches": len(opponent_last10),
        "pick_last10_win_pct": round(pick_last10_rate, 4) if pick_last10_rate is not None else None,
        "opponent_last10_win_pct": round(opponent_last10_rate, 4) if opponent_last10_rate is not None else None,
        "pick_surface_last10_win_pct": round(pick_surface_rate, 4) if pick_surface_rate is not None else None,
        "opponent_surface_last10_win_pct": round(opponent_surface_rate, 4) if opponent_surface_rate is not None else None,
        "pick_avg_opponent_rank_last10": round(pick_avg_rank, 1) if pick_avg_rank is not None else None,
        "opponent_avg_opponent_rank_last10": round(opponent_avg_rank, 1) if opponent_avg_rank is not None else None,
        "recent_form_edge": recent_edge,
        "short_form_edge": short_edge,
        "surface_recent_form_edge": surface_edge,
        "opponent_quality_edge": quality_edge,
        "form_confidence": round(confidence, 4),
        "flags": sorted(set(flags)),
    }
