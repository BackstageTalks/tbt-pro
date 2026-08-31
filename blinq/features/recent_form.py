from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from thinq.loaders.history_loader import normalize_name, normalize_surface
except Exception:
    def normalize_name(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def normalize_surface(value: Any) -> str:
        text = str(value or "").lower()
        if "clay" in text:
            return "Clay"
        if "grass" in text:
            return "Grass"
        if "hard" in text or "indoor" in text or "carpet" in text:
            return "Hard"
        return "Unknown"


API_PRO_HOST = "tennisapi1.p.rapidapi.com"
API_PRO_BASE_URL = "https://tennisapi1.p.rapidapi.com"
API_PRO_TIMEOUT = 20
API_CACHE_DIR = Path("blinq/data/form/previous_matches")
API_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
API_CACHE_STALE_FALLBACK_SECONDS = 60 * 60 * 24 * 90
API_MAX_PAGES = 2
API_MIN_USABLE_MATCHES = 20
API_MIN_SURFACE_MATCHES = 8


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fmt_record(wins: int, total: int) -> str:
    return "N/A" if total <= 0 else f"{wins}-{total - wins}"


def _win_pct(wins: int, total: int) -> Optional[float]:
    return round(wins / total, 4) if total > 0 else None


def _api_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "").strip()


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": API_PRO_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _cache_path(player_id: Any, page: int) -> Path:
    return API_CACHE_DIR / f"{player_id}_{page}.json"


def _read_cache(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("saved_at", 0))
        if age > API_CACHE_STALE_FALLBACK_SECONDS:
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        data = dict(data)
        data["cache_age_seconds"] = int(max(age, 0))
        data["cache_freshness"] = "FRESH" if age <= API_CACHE_TTL_SECONDS else "STALE_FALLBACK"
        return data
    except Exception:
        return None


def _write_cache(path: Path, data: Dict[str, Any]) -> None:
    """Azure prediction runtime is read-only. Cache updates belong to GitHub Actions."""
    return None

def _fetch_page(player_id: Any, page: int, force_refresh: bool = False) -> Dict[str, Any]:
    """Read verified BlinQ cache only. Never call API or write during prediction."""
    if player_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "events": [], "page": page}
    path = _cache_path(player_id, page)
    cached = _read_cache(path)
    if cached is not None:
        cached.setdefault("from_cache", True)
        cached.setdefault("cache_path", str(path))
        return cached
    return {
        "status": "NO_VERIFIED_CACHE",
        "events": [],
        "page": page,
        "cache_path": str(path),
    }

def _parse_date(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _team_id(team: Any) -> Optional[Any]:
    if not isinstance(team, dict):
        return None
    return team.get("id") or (team.get("playerTeamInfo") or {}).get("id")


def _team_name(team: Any) -> str:
    return str(team.get("name") or team.get("shortName") or "") if isinstance(team, dict) else ""


def _surface(event: Dict[str, Any]) -> str:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    return normalize_surface(event.get("groundType") or unique.get("groundType") or tournament.get("groundType"))


def _is_usable_finished_singles(event: Dict[str, Any]) -> bool:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    if str(status.get("type") or "").lower() != "finished":
        return False
    description = str(status.get("description") or "").lower()
    if any(x in description for x in ("retired", "walkover", "canceled", "cancelled", "postponed", "abandoned")):
        return False
    filters = event.get("eventFilters") if isinstance(event.get("eventFilters"), dict) else {}
    categories = [str(x).lower() for x in (filters.get("category") or [])]
    return not categories or "singles" in categories


def _winner_side(event: Dict[str, Any]) -> Optional[str]:
    try:
        code = int(event.get("winnerCode"))
        return "HOME" if code == 1 else "AWAY" if code == 2 else None
    except Exception:
        return None


def _normalize_events(
    events: List[Dict[str, Any]],
    player_id: Any,
    player_name: str,
    current_event_id: Any,
    current_match_start: Any,
) -> List[Dict[str, Any]]:
    player_key = normalize_name(player_name)
    current_dt = _parse_date(current_match_start)
    matches: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, dict) or not _is_usable_finished_singles(event):
            continue
        event_id = event.get("id")
        event_key = str(event_id or event.get("customId") or "")
        if not event_key or event_key in seen or (current_event_id is not None and event_key == str(current_event_id)):
            continue
        dt = _parse_date(event.get("startTimestamp"))
        if current_dt and dt and dt >= current_dt:
            continue
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}
        is_home = str(_team_id(home)) == str(player_id) or normalize_name(_team_name(home)) == player_key
        is_away = str(_team_id(away)) == str(player_id) or normalize_name(_team_name(away)) == player_key
        if not is_home and not is_away:
            continue
        winner = _winner_side(event)
        if winner is None:
            continue
        opponent_team = away if is_home else home
        opponent_rank = opponent_team.get("ranking")
        try:
            opponent_rank = int(opponent_rank) if opponent_rank not in (None, "", 0) else None
        except Exception:
            opponent_rank = None
        matches.append({
            "date": dt.date().isoformat() if dt else None,
            "timestamp": dt.timestamp() if dt else 0,
            "surface": _surface(event),
            "won": (winner == "HOME" and is_home) or (winner == "AWAY" and is_away),
            "opponent": _team_name(opponent_team),
            "opponent_rank": opponent_rank,
            "event_id": event_id,
        })
        seen.add(event_key)
    matches.sort(key=lambda x: float(x.get("timestamp") or 0), reverse=True)
    return matches


def _api_history(
    player_id: Any,
    player_name: str,
    surface: Any,
    current_event_id: Any,
    current_match_start: Any,
    force_refresh: bool,
) -> Dict[str, Any]:
    requested_surface = normalize_surface(surface)
    pages: List[Dict[str, Any]] = []
    raw_events: List[Dict[str, Any]] = []
    first = _fetch_page(player_id, 0, force_refresh=force_refresh)
    pages.append(first)
    raw_events.extend(first.get("events") or [])
    matches = _normalize_events(raw_events, player_id, player_name, current_event_id, current_match_start)
    surface_count = sum(1 for item in matches if normalize_surface(item.get("surface")) == requested_surface)
    needs_page_1 = (
        first.get("status") == "OK"
        and first.get("has_next_page")
        and (len(matches) < API_MIN_USABLE_MATCHES or surface_count < API_MIN_SURFACE_MATCHES)
    )
    if needs_page_1 and API_MAX_PAGES > 1:
        second = _fetch_page(player_id, 1, force_refresh=force_refresh)
        pages.append(second)
        raw_events.extend(second.get("events") or [])
        matches = _normalize_events(raw_events, player_id, player_name, current_event_id, current_match_start)
    statuses = [str(page.get("status") or "") for page in pages]
    status = "OK" if matches else ("RATE_LIMITED" if "RATE_LIMITED" in statuses else statuses[-1] if statuses else "NO_DATA")
    return {
        "status": status,
        "source": "BLINQ_API_PRO_PREVIOUS_MATCHES_CACHE",
        "matches": matches,
        "api_event_count": len(raw_events),
        "usable_match_count": len(matches),
        "pages_fetched": len(pages),
        "page_statuses": statuses,
        "endpoints": [page.get("endpoint") for page in pages if page.get("endpoint")],
        "cache_paths": [page.get("cache_path") for page in pages if page.get("cache_path")],
    }


def _empty_player_stats(player: str, surface: Any, level: Any) -> Dict[str, Any]:
    empty = {"count": 0, "wins": 0, "losses": 0, "record": "N/A", "win_pct": None, "avg_opponent_rank": None, "last_match_date": None}
    return {
        "player": player,
        "normalized_player": normalize_name(player),
        "total_history_matches": 0,
        "last5": dict(empty),
        "last10": dict(empty),
        "surface": normalize_surface(surface),
        "surface_last10": dict(empty),
        "level": level,
        "level_last10": dict(empty),
    }


def _summarize(sample: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = sum(1 for item in sample if item.get("won") is True)
    ranks = [int(item["opponent_rank"]) for item in sample if item.get("opponent_rank") not in (None, "", 0)]
    total = len(sample)
    return {
        "count": total,
        "wins": wins,
        "losses": total - wins,
        "record": _fmt_record(wins, total),
        "win_pct": _win_pct(wins, total),
        "avg_opponent_rank": round(sum(ranks) / len(ranks), 1) if ranks else None,
        "opponent_rank_count": len(ranks),
        "last_match_date": sample[0].get("date") if sample else None,
    }


def _player_windows(player: str, surface: Any, level: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    matches = context.get("matches") or []
    surface_norm = normalize_surface(surface)
    surface_matches = [item for item in matches if normalize_surface(item.get("surface")) == surface_norm]
    return {
        **_empty_player_stats(player, surface, level),
        "total_history_matches": len(matches),
        "last5": _summarize(matches[:5]),
        "last10": _summarize(matches[:10]),
        "surface_last10": _summarize(surface_matches[:10]),
        "api_status": context.get("status"),
        "api_event_count": context.get("api_event_count"),
        "api_usable_match_count": context.get("usable_match_count"),
        "api_pages_fetched": context.get("pages_fetched"),
        "api_endpoints": context.get("endpoints"),
        "api_cache_paths": context.get("cache_paths"),
    }


def _diff(a: Optional[float], b: Optional[float]) -> float:
    return float(a) - float(b) if a is not None and b is not None else 0.0


def _confidence(pick_stats: Dict[str, Any], opponent_stats: Dict[str, Any]) -> float:
    p_total = int(pick_stats.get("last10", {}).get("count") or 0)
    o_total = int(opponent_stats.get("last10", {}).get("count") or 0)
    p_surface = int(pick_stats.get("surface_last10", {}).get("count") or 0)
    o_surface = int(opponent_stats.get("surface_last10", {}).get("count") or 0)
    base = min((p_total + o_total) / 20.0, 1.0) * 0.65
    surface_score = min((p_surface + o_surface) / 16.0, 1.0) * 0.35
    return round(clamp(base + surface_score, 0.0, 0.95), 4)


def _no_data_response(pick: str, opponent: str, surface: Any, level: Any, pick_api: Dict[str, Any], opponent_api: Dict[str, Any]) -> Dict[str, Any]:
    reason = "API PRO previous-player history is unavailable for one or both players"
    return {
        "status": "NO_DATA",
        "source": "BLINQ_API_PRO_PREVIOUS_MATCHES_CACHE",
        "source_policy": "BLINQ_INDEPENDENT_CACHE_API_PRO_SOURCE",
        "surface": normalize_surface(surface),
        "level": level,
        "reason": reason,
        "pick": _empty_player_stats(pick, surface, level),
        "opponent": _empty_player_stats(opponent, surface, level),
        "recent_form_edge": 0.0,
        "short_form_edge": 0.0,
        "surface_recent_form_edge": 0.0,
        "opponent_quality_edge": None,
        "effective_recent_form_edge": 0.0,
        "effective_short_form_edge": 0.0,
        "effective_surface_recent_form_edge": 0.0,
        "effective_opponent_quality_edge": None,
        "form_confidence": 0.0,
        "form_data_depth": 0.0,
        "recent_form_freshness_status": "API_UNAVAILABLE",
        "pick_api_status": pick_api.get("status"),
        "opponent_api_status": opponent_api.get("status"),
        "pick_api_event_count": pick_api.get("api_event_count", 0),
        "opponent_api_event_count": opponent_api.get("api_event_count", 0),
        "pick_api_usable_match_count": pick_api.get("usable_match_count", 0),
        "opponent_api_usable_match_count": opponent_api.get("usable_match_count", 0),
        "flags": ["RECENT_FORM_NO_API_DATA"],
        "history_status": {"status": "BLINQ_CACHE", "source_policy": "BLINQ_INDEPENDENT_CACHE_API_PRO_SOURCE"},
    }


def build_recent_form_context(
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    level: Optional[str] = None,
    *_args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    pick_id = kwargs.get("pick_player_id") or kwargs.get("pick_team_id")
    opponent_id = kwargs.get("opponent_player_id") or kwargs.get("opponent_team_id")
    current_event_id = kwargs.get("event_id")
    current_match_start = kwargs.get("match_start") or kwargs.get("start_time") or kwargs.get("as_of_date")
    force_refresh = False

    pick_api = _api_history(pick_id, pick, surface, current_event_id, current_match_start, force_refresh)
    opponent_api = _api_history(opponent_id, opponent, surface, current_event_id, current_match_start, force_refresh)
    if not pick_api.get("matches") or not opponent_api.get("matches"):
        return _no_data_response(pick, opponent, surface, level, pick_api, opponent_api)

    pick_stats = _player_windows(pick, surface, level, pick_api)
    opponent_stats = _player_windows(opponent, surface, level, opponent_api)
    last10_diff = _diff(pick_stats["last10"].get("win_pct"), opponent_stats["last10"].get("win_pct"))
    last5_diff = _diff(pick_stats["last5"].get("win_pct"), opponent_stats["last5"].get("win_pct"))
    surface_diff = _diff(pick_stats["surface_last10"].get("win_pct"), opponent_stats["surface_last10"].get("win_pct"))
    recent_edge = round(clamp(last10_diff * 0.08, -0.05, 0.05), 4)
    short_edge = round(clamp(last5_diff * 0.05, -0.035, 0.035), 4)
    surface_edge = round(clamp(surface_diff * 0.07, -0.05, 0.05), 4)
    confidence = _confidence(pick_stats, opponent_stats)

    flags: List[str] = []
    if pick_stats["last10"]["count"] < 10 or opponent_stats["last10"]["count"] < 10:
        flags.append("RECENT_FORM_THIN_SAMPLE")
    if pick_stats["surface_last10"]["count"] < 5 or opponent_stats["surface_last10"]["count"] < 5:
        flags.append("SURFACE_RECENT_FORM_THIN_SAMPLE")
    if abs(recent_edge) < 0.005 and abs(surface_edge) < 0.005:
        flags.append("RECENT_FORM_NEUTRAL")

    return {
        "status": "OK",
        "source": "BLINQ_API_PRO_PREVIOUS_MATCHES_CACHE",
        "source_policy": "BLINQ_INDEPENDENT_CACHE_API_PRO_SOURCE",
        "surface": normalize_surface(surface),
        "level": level,
        "pick": pick_stats,
        "opponent": opponent_stats,
        "pick_last5_record": pick_stats["last5"]["record"],
        "opponent_last5_record": opponent_stats["last5"]["record"],
        "pick_last10_record": pick_stats["last10"]["record"],
        "opponent_last10_record": opponent_stats["last10"]["record"],
        "pick_last10_win_pct": pick_stats["last10"].get("win_pct"),
        "opponent_last10_win_pct": opponent_stats["last10"].get("win_pct"),
        "pick_surface_record": pick_stats["surface_last10"]["record"],
        "opponent_surface_record": opponent_stats["surface_last10"]["record"],
        "pick_surface_last10_win_pct": pick_stats["surface_last10"].get("win_pct"),
        "opponent_surface_last10_win_pct": opponent_stats["surface_last10"].get("win_pct"),
        "raw_recent_form_edge": recent_edge,
        "raw_short_form_edge": short_edge,
        "raw_surface_recent_form_edge": surface_edge,
        "raw_opponent_quality_edge": None,
        "recent_form_edge": recent_edge,
        "short_form_edge": short_edge,
        "surface_recent_form_edge": surface_edge,
        "opponent_quality_edge": None,
        "effective_recent_form_edge": recent_edge,
        "effective_short_form_edge": short_edge,
        "effective_surface_recent_form_edge": surface_edge,
        "effective_opponent_quality_edge": None,
        "form_confidence": confidence,
        "form_data_depth": confidence,
        "recent_form_freshness_status": "VERIFIED_CACHE",
        "pick_api_last10_record": pick_stats["last10"]["record"],
        "opponent_api_last10_record": opponent_stats["last10"]["record"],
        "pick_api_surface_record": pick_stats["surface_last10"]["record"],
        "opponent_api_surface_record": opponent_stats["surface_last10"]["record"],
        "pick_api_last_match_date": pick_stats["last10"].get("last_match_date"),
        "opponent_api_last_match_date": opponent_stats["last10"].get("last_match_date"),
        "pick_api_status": pick_api.get("status"),
        "opponent_api_status": opponent_api.get("status"),
        "pick_api_event_count": pick_api.get("api_event_count"),
        "opponent_api_event_count": opponent_api.get("api_event_count"),
        "pick_api_usable_match_count": pick_api.get("usable_match_count"),
        "opponent_api_usable_match_count": opponent_api.get("usable_match_count"),
        "recent_form_sample_audit": {
            "status": "OK",
            "pick_last10_count": pick_stats["last10"]["count"],
            "opponent_last10_count": opponent_stats["last10"]["count"],
            "pick_surface_count": pick_stats["surface_last10"]["count"],
            "opponent_surface_count": opponent_stats["surface_last10"]["count"],
            "pick_total_history_matches": pick_stats["total_history_matches"],
            "opponent_total_history_matches": opponent_stats["total_history_matches"],
            "pick_pages_fetched": pick_api.get("pages_fetched"),
            "opponent_pages_fetched": opponent_api.get("pages_fetched"),
        },
        "flags": sorted(set(flags)),
        "history_status": {"status": "BLINQ_CACHE", "source_policy": "BLINQ_INDEPENDENT_CACHE_API_PRO_SOURCE"},
    }
