from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

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
        return "N/A"
    return f"{wins}-{total - wins}"


def _win_pct(wins: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(wins / total, 4)




API_PRO_HOST = "tennisapi1.p.rapidapi.com"
API_PRO_BASE_URL = "https://tennisapi1.p.rapidapi.com"
API_PRO_TIMEOUT = 20
API_RECENT_FORM_CACHE_DIR = Path("data/api_pro/team_last_matches")
API_RECENT_FORM_CACHE_TTL_SECONDS = 60 * 60 * 6
STALE_FORM_DAYS = 30
AGING_FORM_DAYS = 21


def _api_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "").strip()


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": API_PRO_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _cache_path(team_id: Any, page: int = 0) -> Path:
    API_RECENT_FORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return API_RECENT_FORM_CACHE_DIR / f"{team_id}_last_{page}.json"


def _read_cache(path: Path) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(payload.get("saved_at", 0)) > API_RECENT_FORM_CACHE_TTL_SECONDS:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_cache(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _parse_date(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            # API timestamps are seconds.
            v = float(value)
            if v > 10_000_000_000:
                v = v / 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _date_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.date().isoformat() if dt else None


def _days_old(last_date: Optional[str], match_date: Optional[Any]) -> Optional[int]:
    if not last_date:
        return None
    left = _parse_date(last_date)
    right = _parse_date(match_date) or datetime.now(timezone.utc)
    if not left:
        try:
            left = datetime.fromisoformat(str(last_date)).replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return max((right.date() - left.date()).days, 0)


def _freshness_status(days: Optional[int]) -> str:
    if days is None:
        return "UNKNOWN"
    if days <= AGING_FORM_DAYS:
        return "FRESH"
    if days <= STALE_FORM_DAYS:
        return "AGING"
    return "STALE"


def _iter_events(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        if isinstance(obj.get("homeTeam"), dict) and isinstance(obj.get("awayTeam"), dict):
            out.append(obj)
        for value in obj.values():
            out.extend(_iter_events(value))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_iter_events(item))
    return out


def _fetch_team_last_matches(team_id: Any, page: int = 0, force_refresh: bool = False) -> Dict[str, Any]:
    if team_id in (None, ""):
        return {"status": "NO_TEAM_ID", "events": []}
    path = _cache_path(team_id, page)
    if not force_refresh:
        cached = _read_cache(path)
        if isinstance(cached, dict):
            cached.setdefault("from_cache", True)
            cached.setdefault("cache_path", str(path))
            return cached
    if not _api_key():
        return {"status": "NO_API_KEY", "events": [], "cache_path": str(path)}

    # RapidAPI TennisApi endpoint confirmed in the playground as:
    # Players -> getPreviousPlayerMatches, params: id, page.
    # The exact generated path can vary between API wrapper releases, so we try
    # the player/previous variants first and keep the older Sofascore-style
    # team/last paths as fallbacks. A response with real events wins.
    urls = [
        f"{API_PRO_BASE_URL}/api/tennis/player/{team_id}/matches/previous/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/player/{team_id}/events/previous/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/player/{team_id}/previous-matches/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/player/{team_id}/matches/last/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/player/{team_id}/events/last/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/team/{team_id}/matches/previous/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/team/{team_id}/events/previous/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/team/{team_id}/events/last/{page}",
        f"{API_PRO_BASE_URL}/api/tennis/team/{team_id}/matches/last/{page}",
    ]
    last_error = None
    best_result = None
    attempts = []
    for url in urls:
        try:
            response = requests.get(url, headers=_headers(), timeout=API_PRO_TIMEOUT)
            status = response.status_code
            attempts.append({"endpoint": url, "status_code": status})
            if status == 429:
                return {
                    "status": "RATE_LIMITED",
                    "events": [],
                    "api_status_code": status,
                    "cache_path": str(path),
                    "endpoint": url,
                    "endpoint_attempts": attempts,
                }
            if status == 404:
                last_error = f"HTTP 404: {url}"
                continue
            response.raise_for_status()
            payload = response.json()
            events = _iter_events(payload)
            result = {
                "status": "OK",
                "endpoint": url,
                "api_status_code": status,
                "payload": payload,
                "events": events,
                "event_count": len(events),
                "from_cache": False,
                "cache_path": str(path),
                "endpoint_attempts": attempts,
            }
            if len(events) > 0:
                _write_cache(path, result)
                return result
            # Keep an OK zero-event payload as a last resort, but continue
            # probing because some paths return metadata without matches.
            if best_result is None:
                best_result = result
        except Exception as exc:
            last_error = str(exc)
            attempts.append({"endpoint": url, "error": last_error})
            continue
    if best_result is not None:
        _write_cache(path, best_result)
        return best_result
    return {
        "status": "FETCH_FAILED",
        "events": [],
        "error": last_error,
        "cache_path": str(path),
        "endpoint_attempts": attempts,
    }


def _event_surface(event: Dict[str, Any]) -> Optional[str]:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    return event.get("groundType") or tournament.get("groundType") or unique.get("groundType") or event.get("surface")


def _event_dt(event: Dict[str, Any]) -> Optional[datetime]:
    return _parse_date(event.get("startTimestamp") or event.get("startTime") or event.get("match_start"))


def _is_finished(event: Dict[str, Any]) -> bool:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    stype = str(status.get("type") or event.get("status_type") or "").lower()
    code = status.get("code", event.get("status_code"))
    desc = str(status.get("description") or "").lower()
    return stype in {"finished", "ended"} or code == 100 or "finished" in desc


def _team_id(team: Any) -> Optional[Any]:
    if not isinstance(team, dict):
        return None
    return team.get("id") or (team.get("playerTeamInfo") or {}).get("id")


def _team_name(team: Any) -> str:
    if not isinstance(team, dict):
        return ""
    return str(team.get("name") or team.get("shortName") or "")


def _winner_side(event: Dict[str, Any]) -> Optional[str]:
    code = event.get("winnerCode") or event.get("winner_code")
    try:
        code = int(code)
        if code == 1:
            return "HOME"
        if code == 2:
            return "AWAY"
    except Exception:
        pass
    home_score = event.get("homeScore") if isinstance(event.get("homeScore"), dict) else {}
    away_score = event.get("awayScore") if isinstance(event.get("awayScore"), dict) else {}
    try:
        h = int(home_score.get("current"))
        a = int(away_score.get("current"))
        if h > a:
            return "HOME"
        if a > h:
            return "AWAY"
    except Exception:
        return None
    return None


def _api_history_matches(team_id: Any, player_name: str, surface: Optional[str], current_event_id: Any = None, current_match_start: Any = None, force_refresh: bool = False) -> Dict[str, Any]:
    result = _fetch_team_last_matches(team_id, page=0, force_refresh=force_refresh)
    events = result.get("events") or []
    current_dt = _parse_date(current_match_start)
    surface_norm = normalize_surface(surface)
    normalized_player = normalize_name(player_name)
    matches: List[Dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("id")
        if current_event_id is not None and str(event_id) == str(current_event_id):
            continue
        if not _is_finished(event):
            continue
        dt = _event_dt(event)
        if current_dt and dt and dt >= current_dt:
            continue
        home = event.get("homeTeam") or {}
        away = event.get("awayTeam") or {}
        home_id = _team_id(home)
        away_id = _team_id(away)
        home_name = _team_name(home)
        away_name = _team_name(away)
        is_home = str(home_id) == str(team_id) or normalize_name(home_name) == normalized_player
        is_away = str(away_id) == str(team_id) or normalize_name(away_name) == normalized_player
        if not is_home and not is_away:
            continue
        winner = _winner_side(event)
        won = (winner == "HOME" and is_home) or (winner == "AWAY" and is_away)
        opp_name = away_name if is_home else home_name
        matches.append({
            "date": _date_str(dt),
            "timestamp": dt.timestamp() if dt else 0,
            "surface": normalize_surface(_event_surface(event)),
            "won": bool(won),
            "opponent": opp_name,
            "opponent_rank": None,
            "event_id": event_id,
        })
    matches.sort(key=lambda item: item.get("timestamp") or 0, reverse=True)
    return {
        "status": result.get("status"),
        "source": "rapidapi_team_last_matches",
        "team_id": team_id,
        "api_event_count": len(events),
        "usable_match_count": len(matches),
        "endpoint": result.get("endpoint"),
        "cache_path": result.get("cache_path"),
        "matches": matches,
        "surface": surface_norm,
        "error": result.get("error"),
    }


def _summarize_api_sample(sample: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = sum(1 for item in sample if item.get("won") is True)
    total = len(sample)
    return {
        "count": total,
        "wins": wins,
        "losses": max(total - wins, 0),
        "record": _fmt_record(wins, total),
        "win_pct": _win_pct(wins, total),
        "avg_opponent_rank": None,
        "last_match_date": sample[0].get("date") if sample else None,
    }


def _api_player_windows(player: str, surface: Optional[str], api_ctx: Dict[str, Any], level: Optional[str] = None) -> Dict[str, Any]:
    matches = api_ctx.get("matches") or []
    surface_norm = normalize_surface(surface)
    last5 = matches[:5]
    last10 = matches[:10]
    surface_matches = [m for m in matches if normalize_surface(m.get("surface")) == surface_norm][:10]
    empty = _empty_player_stats(player, surface, level)
    return {
        **empty,
        "total_history_matches": len(matches),
        "last5": _summarize_api_sample(last5),
        "last10": _summarize_api_sample(last10),
        "surface_last10": _summarize_api_sample(surface_matches),
        "api_status": api_ctx.get("status"),
        "api_event_count": api_ctx.get("api_event_count"),
        "api_usable_match_count": api_ctx.get("usable_match_count"),
        "api_endpoint": api_ctx.get("endpoint"),
        "api_cache_path": api_ctx.get("cache_path"),
    }

def _empty_player_stats(player: str, surface: Optional[str], level: Optional[str] = None) -> Dict[str, Any]:
    surface_norm = normalize_surface(surface)
    key = normalize_name(player)
    empty_window = {
        "count": 0,
        "wins": 0,
        "losses": 0,
        "record": "N/A",
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

    Priority:
    1. RapidAPI team last matches when pick/opponent team IDs are available.
    2. Local history only when it exists and is not stale.
    3. Neutral/no-data response when neither source is usable.
    """
    history_status = history_data_status()
    empty_pick_stats = _empty_player_stats(pick, surface, level)
    empty_opp_stats = _empty_player_stats(opponent, surface, level)

    has_local_history = bool(history_status.get("match_count"))
    pick_stats_local = _player_windows(pick, surface, level) if has_local_history else empty_pick_stats
    opp_stats_local = _player_windows(opponent, surface, level) if has_local_history else empty_opp_stats

    pick_team_id = _kwargs.get("pick_player_id") or _kwargs.get("pick_team_id")
    opp_team_id = _kwargs.get("opponent_player_id") or _kwargs.get("opponent_team_id")
    current_event_id = _kwargs.get("event_id")
    current_match_start = _kwargs.get("match_start") or _kwargs.get("start_time") or _kwargs.get("as_of_date")
    force_api_refresh = bool(_kwargs.get("force_refresh_api_recent_form", False))

    pick_api = _api_history_matches(
        pick_team_id,
        pick,
        surface,
        current_event_id=current_event_id,
        current_match_start=current_match_start,
        force_refresh=force_api_refresh,
    ) if pick_team_id else {"status": "NO_TEAM_ID", "matches": [], "usable_match_count": 0}
    opp_api = _api_history_matches(
        opp_team_id,
        opponent,
        surface,
        current_event_id=current_event_id,
        current_match_start=current_match_start,
        force_refresh=force_api_refresh,
    ) if opp_team_id else {"status": "NO_TEAM_ID", "matches": [], "usable_match_count": 0}

    pick_stats_api = _api_player_windows(pick, surface, pick_api, level) if int(pick_api.get("usable_match_count") or 0) > 0 else None
    opp_stats_api = _api_player_windows(opponent, surface, opp_api, level) if int(opp_api.get("usable_match_count") or 0) > 0 else None

    local_pick_days = _days_old(pick_stats_local.get("last10", {}).get("last_match_date"), current_match_start)
    local_opp_days = _days_old(opp_stats_local.get("last10", {}).get("last_match_date"), current_match_start)
    local_pick_freshness = _freshness_status(local_pick_days)
    local_opp_freshness = _freshness_status(local_opp_days)
    local_stale = local_pick_freshness == "STALE" or local_opp_freshness == "STALE"
    api_available = bool(pick_stats_api and opp_stats_api)

    if api_available:
        pick_stats = pick_stats_api
        opp_stats = opp_stats_api
        form_source = "rapidapi_team_last_matches"
        form_freshness = "API_CURRENT"
    elif has_local_history and (pick_stats_local["last10"]["count"] > 0 or opp_stats_local["last10"]["count"] > 0):
        pick_stats = pick_stats_local
        opp_stats = opp_stats_local
        form_source = "local_history"
        form_freshness = "LOCAL_STALE" if local_stale else "LOCAL_FRESH"
    else:
        reason = "No usable API or local recent-form matches found"
        return {
            "status": "NO_DATA",
            "source": None,
            "surface": normalize_surface(surface),
            "level": level,
            "reason": reason,
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "effective_recent_form_edge": 0.0,
            "effective_short_form_edge": 0.0,
            "effective_surface_recent_form_edge": 0.0,
            "effective_opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
            "form_data_depth": 0.0,
            "recent_form_freshness_status": "NO_USABLE_SOURCE",
            "pick": empty_pick_stats,
            "opponent": empty_opp_stats,
            "pick_last10_record": None,
            "opponent_last10_record": None,
            "pick_surface_record": None,
            "opponent_surface_record": None,
            "pick_local_last_match_date": pick_stats_local.get("last10", {}).get("last_match_date"),
            "opponent_local_last_match_date": opp_stats_local.get("last10", {}).get("last_match_date"),
            "pick_local_days_old": local_pick_days,
            "opponent_local_days_old": local_opp_days,
            "pick_api_last10_record": pick_stats_api.get("last10", {}).get("record") if pick_stats_api else None,
            "opponent_api_last10_record": opp_stats_api.get("last10", {}).get("record") if opp_stats_api else None,
            "pick_api_surface_record": pick_stats_api.get("surface_last10", {}).get("record") if pick_stats_api else None,
            "opponent_api_surface_record": opp_stats_api.get("surface_last10", {}).get("record") if opp_stats_api else None,
            "pick_api_last_match_date": pick_stats_api.get("last10", {}).get("last_match_date") if pick_stats_api else None,
            "opponent_api_last_match_date": opp_stats_api.get("last10", {}).get("last_match_date") if opp_stats_api else None,
            "pick_api_status": pick_api.get("status"),
            "opponent_api_status": opp_api.get("status"),
            "pick_api_event_count": pick_api.get("api_event_count"),
            "opponent_api_event_count": opp_api.get("api_event_count"),
            "pick_api_usable_match_count": pick_api.get("usable_match_count"),
            "opponent_api_usable_match_count": opp_api.get("usable_match_count"),
            "recent_form_sample_audit": _sample_audit(empty_pick_stats, empty_opp_stats, "NO_DATA", reason),
            "flags": ["RECENT_FORM_NO_DATA"],
            "history_status": history_status,
        }

    last10_diff = _diff_pct(pick_stats["last10"].get("win_pct"), opp_stats["last10"].get("win_pct"))
    last5_diff = _diff_pct(pick_stats["last5"].get("win_pct"), opp_stats["last5"].get("win_pct"))
    surface_diff = _diff_pct(pick_stats["surface_last10"].get("win_pct"), opp_stats["surface_last10"].get("win_pct"))

    raw_recent_form_edge = round(clamp(last10_diff * 0.08, -0.05, 0.05), 4)
    raw_short_form_edge = round(clamp(last5_diff * 0.05, -0.035, 0.035), 4)
    raw_surface_recent_form_edge = round(clamp(surface_diff * 0.07, -0.05, 0.05), 4)
    raw_opponent_quality_edge = _quality_edge(pick_stats, opp_stats)
    form_confidence = _confidence(pick_stats, opp_stats)

    flags: List[str] = []
    if form_source == "local_history" and local_stale:
        recent_form_edge = 0.0
        short_form_edge = 0.0
        surface_recent_form_edge = 0.0
        opponent_quality_edge = 0.0
        form_confidence = min(form_confidence, 0.35)
        flags.append("RECENT_FORM_STALE_LOCAL_HISTORY")
    else:
        recent_form_edge = raw_recent_form_edge
        short_form_edge = raw_short_form_edge
        surface_recent_form_edge = raw_surface_recent_form_edge
        opponent_quality_edge = raw_opponent_quality_edge

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
        "source": form_source,
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
        "raw_recent_form_edge": raw_recent_form_edge,
        "raw_short_form_edge": raw_short_form_edge,
        "raw_surface_recent_form_edge": raw_surface_recent_form_edge,
        "raw_opponent_quality_edge": raw_opponent_quality_edge,
        "recent_form_edge": recent_form_edge,
        "short_form_edge": short_form_edge,
        "surface_recent_form_edge": surface_recent_form_edge,
        "opponent_quality_edge": opponent_quality_edge,
        "effective_recent_form_edge": recent_form_edge,
        "effective_short_form_edge": short_form_edge,
        "effective_surface_recent_form_edge": surface_recent_form_edge,
        "effective_opponent_quality_edge": opponent_quality_edge,
        "form_confidence": round(form_confidence, 4),
        "form_data_depth": round(form_confidence, 4),
        "recent_form_freshness_status": form_freshness,
        "pick_local_last_match_date": pick_stats_local.get("last10", {}).get("last_match_date"),
        "opponent_local_last_match_date": opp_stats_local.get("last10", {}).get("last_match_date"),
        "pick_local_days_old": local_pick_days,
        "opponent_local_days_old": local_opp_days,
        "pick_api_last10_record": pick_stats_api.get("last10", {}).get("record") if pick_stats_api else None,
        "opponent_api_last10_record": opp_stats_api.get("last10", {}).get("record") if opp_stats_api else None,
        "pick_api_surface_record": pick_stats_api.get("surface_last10", {}).get("record") if pick_stats_api else None,
        "opponent_api_surface_record": opp_stats_api.get("surface_last10", {}).get("record") if opp_stats_api else None,
        "pick_api_last_match_date": pick_stats_api.get("last10", {}).get("last_match_date") if pick_stats_api else None,
        "opponent_api_last_match_date": opp_stats_api.get("last10", {}).get("last_match_date") if opp_stats_api else None,
        "pick_api_status": pick_api.get("status"),
        "opponent_api_status": opp_api.get("status"),
        "pick_api_event_count": pick_api.get("api_event_count"),
        "opponent_api_event_count": opp_api.get("api_event_count"),
        "pick_api_usable_match_count": pick_api.get("usable_match_count"),
        "opponent_api_usable_match_count": opp_api.get("usable_match_count"),
        "recent_form_sample_audit": sample_audit,
        "flags": sorted(set(flags)),
        "history_status": history_status,
    }
