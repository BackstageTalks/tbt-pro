from __future__ import annotations

from typing import Any, Dict, List, Optional

from thinq.loaders.history_loader import (
    HistoryMatch,
    get_player_matches,
    history_data_status,
    normalize_name,
    normalize_surface,
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fmt_record(wins: int, total: int) -> str:
    if total <= 0:
        return "0-0"
    return f"{wins}-{total - wins}"


def _win_pct(wins: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(wins / total, 4)


def _empty_player_stats(player: str, surface: Optional[str], level: Optional[str] = None) -> Dict[str, Any]:
    surface_norm = normalize_surface(surface)
    key = normalize_name(player)
    empty_window = {
        "count": 0,
        "wins": 0,
        "losses": 0,
        "record": "0-0",
        "win_pct": None,
        "avg_opponent_rank": None,
        "last_match_date": None,
    }
    return {
        "player": player,
        "normalized_player": key,
        "total_history_matches": 0,
        "last5": dict(empty_window),
        "last10": dict(empty_window),
        "surface": surface_norm,
        "surface_last10": dict(empty_window),
        "level": level or None,
        "level_last10": dict(empty_window),
    }


def _player_windows(player: str, surface: Optional[str], level: Optional[str] = None) -> Dict[str, Any]:
    key = normalize_name(player)
    matches = get_player_matches(player)
    surface_norm = normalize_surface(surface)
    level_norm = str(level or "").strip().lower()

    def summarize(sample: List[HistoryMatch]) -> Dict[str, Any]:
        wins = sum(1 for m in sample if m.player_won(key) is True)
        total = len(sample)
        opp_ranks = [m.opponent_rank_for(key) for m in sample if m.opponent_rank_for(key) is not None]
        return {
            "count": total,
            "wins": wins,
            "losses": max(total - wins, 0),
            "record": _fmt_record(wins, total),
            "win_pct": _win_pct(wins, total),
            "avg_opponent_rank": round(sum(opp_ranks) / len(opp_ranks), 1) if opp_ranks else None,
            "last_match_date": sample[0].date if sample else None,
        }

    last5 = matches[:5]
    last10 = matches[:10]
    surface_matches = [m for m in matches if normalize_surface(m.surface) == surface_norm][:10]
    level_matches = [m for m in matches if level_norm and str(m.level or "").strip().lower() == level_norm][:10]

    return {
        "player": player,
        "normalized_player": key,
        "total_history_matches": len(matches),
        "last5": summarize(last5),
        "last10": summarize(last10),
        "surface": surface_norm,
        "surface_last10": summarize(surface_matches),
        "level": level or None,
        "level_last10": summarize(level_matches),
    }


def _diff_pct(a: Optional[float], b: Optional[float]) -> float:
    if a is None or b is None:
        return 0.0
    return float(a) - float(b)


def _quality_edge(pick_stats: Dict[str, Any], opp_stats: Dict[str, Any]) -> float:
    p_rank = pick_stats.get("last10", {}).get("avg_opponent_rank")
    o_rank = opp_stats.get("last10", {}).get("avg_opponent_rank")
    if p_rank is None or o_rank is None:
        return 0.0
    diff = float(o_rank) - float(p_rank)
    return round(clamp(diff / 10000.0, -0.03, 0.03), 4)


def _confidence(pick_stats: Dict[str, Any], opp_stats: Dict[str, Any]) -> float:
    p_total = pick_stats.get("last10", {}).get("count") or 0
    o_total = opp_stats.get("last10", {}).get("count") or 0
    p_surface = pick_stats.get("surface_last10", {}).get("count") or 0
    o_surface = opp_stats.get("surface_last10", {}).get("count") or 0

    base = min((p_total + o_total) / 20.0, 1.0) * 0.55
    surface_score = min((p_surface + o_surface) / 12.0, 1.0) * 0.30
    quality = 0.15 if (
        pick_stats.get("last10", {}).get("avg_opponent_rank") is not None
        and opp_stats.get("last10", {}).get("avg_opponent_rank") is not None
    ) else 0.0

    return round(clamp(base + surface_score + quality, 0.0, 0.95), 4)


def _sample_audit(pick_stats: Dict[str, Any], opp_stats: Dict[str, Any], status: str, reason: str = "") -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "pick_last10_count": pick_stats.get("last10", {}).get("count", 0),
        "opponent_last10_count": opp_stats.get("last10", {}).get("count", 0),
        "pick_surface_count": pick_stats.get("surface_last10", {}).get("count", 0),
        "opponent_surface_count": opp_stats.get("surface_last10", {}).get("count", 0),
        "pick_total_history_matches": pick_stats.get("total_history_matches", 0),
        "opponent_total_history_matches": opp_stats.get("total_history_matches", 0),
    }


def build_recent_form_context(
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    level: Optional[str] = None,
    *_args: Any,
    **_kwargs: Any,
) -> Dict[str, Any]:
    """Build a side-safe recent-form context for ThinQ.

    Important implementation note:
    - The opponent stats variable is consistently named `opp_stats`.
    - The function avoids the previous undefined-opponent-stats runtime crash.
    """
    status = history_data_status()
    empty_pick_stats = _empty_player_stats(pick, surface, level)
    empty_opp_stats = _empty_player_stats(opponent, surface, level)

    if not status.get("match_count"):
        reason = "No local history files found"
        return {
            "status": "NO_DATA",
            "source": None,
            "reason": reason,
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
            "form_data_depth": 0.0,
            "recent_form_sample_audit": _sample_audit(empty_pick_stats, empty_opp_stats, "NO_DATA", reason),
            "flags": ["RECENT_FORM_NO_DATA"],
            "pick": empty_pick_stats,
            "opponent": empty_opp_stats,
            "history_status": status,
        }

    pick_stats = _player_windows(pick, surface, level)
    opp_stats = _player_windows(opponent, surface, level)

    if pick_stats["last10"]["count"] == 0 and opp_stats["last10"]["count"] == 0:
        reason = "No completed historical matches found for either player"
        return {
            "status": "NO_DATA",
            "source": "local_history",
            "reason": reason,
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
            "form_data_depth": 0.0,
            "recent_form_sample_audit": _sample_audit(pick_stats, opp_stats, "NO_DATA", reason),
            "flags": ["RECENT_FORM_NO_PLAYER_MATCHES"],
            "pick": pick_stats,
            "opponent": opp_stats,
            "history_status": status,
        }

    last10_diff = _diff_pct(pick_stats["last10"].get("win_pct"), opp_stats["last10"].get("win_pct"))
    last5_diff = _diff_pct(pick_stats["last5"].get("win_pct"), opp_stats["last5"].get("win_pct"))
    surface_diff = _diff_pct(pick_stats["surface_last10"].get("win_pct"), opp_stats["surface_last10"].get("win_pct"))

    recent_form_edge = round(clamp(last10_diff * 0.08, -0.05, 0.05), 4)
    short_form_edge = round(clamp(last5_diff * 0.05, -0.035, 0.035), 4)
    surface_recent_form_edge = round(clamp(surface_diff * 0.07, -0.05, 0.05), 4)
    opponent_quality_edge = _quality_edge(pick_stats, opp_stats)
    form_confidence = _confidence(pick_stats, opp_stats)

    flags: List[str] = []
    if pick_stats["last10"]["count"] < 3 or opp_stats["last10"]["count"] < 3:
        flags.append("RECENT_FORM_THIN_SAMPLE")
    if pick_stats["surface_last10"]["count"] < 3 or opp_stats["surface_last10"]["count"] < 3:
        flags.append("SURFACE_RECENT_FORM_THIN_SAMPLE")
    if opponent_quality_edge == 0.0:
        flags.append("OPPONENT_QUALITY_THIN_DATA")
    if abs(recent_form_edge) < 0.005 and abs(surface_recent_form_edge) < 0.005:
        flags.append("RECENT_FORM_NEUTRAL")

    sample_audit = _sample_audit(pick_stats, opp_stats, "OK")
    return {
        "status": "OK",
        "source": "local_history",
        "surface": normalize_surface(surface),
        "level": level,
        "pick": pick_stats,
        "opponent": opp_stats,
        "pick_last5_record": pick_stats["last5"]["record"],
        "opponent_last5_record": opp_stats["last5"]["record"],
        "pick_last10_record": pick_stats["last10"]["record"],
        "opponent_last10_record": opp_stats["last10"]["record"],
        "pick_last10_win_pct": pick_stats["last10"].get("win_pct"),
        "opponent_last10_win_pct": opp_stats["last10"].get("win_pct"),
        "pick_surface_record": pick_stats["surface_last10"]["record"],
        "opponent_surface_record": opp_stats["surface_last10"]["record"],
        "pick_surface_last10_win_pct": pick_stats["surface_last10"].get("win_pct"),
        "opponent_surface_last10_win_pct": opp_stats["surface_last10"].get("win_pct"),
        "recent_form_edge": recent_form_edge,
        "short_form_edge": short_form_edge,
        "surface_recent_form_edge": surface_recent_form_edge,
        "opponent_quality_edge": opponent_quality_edge,
        "form_confidence": form_confidence,
        "form_data_depth": form_confidence,
        "recent_form_sample_audit": sample_audit,
        "flags": flags,
        "history_status": status,
    }
