"""BlinQ recent-form context from verified API PRO previous-match cache only."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CACHE_DIR = Path("blinq/data/form/previous_matches")
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
MAX_CACHE_AGE_SECONDS = 60 * 60 * 24 * 90
EXCLUDED_STATUS_TOKENS = ("retired", "walkover", "cancelled", "canceled", "postponed", "abandoned")


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def normalize_surface(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def _parse_date(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _team_id(team: Any) -> Any:
    if not isinstance(team, dict):
        return None
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return team.get("id") or info.get("id")


def _team_name(team: Any) -> str:
    return str(team.get("name") or team.get("shortName") or "") if isinstance(team, dict) else ""


def _surface(event: Dict[str, Any]) -> str:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    return normalize_surface(event.get("groundType") or tournament.get("groundType") or unique.get("groundType"))


def _usable_finished_singles(event: Any) -> bool:
    if not isinstance(event, dict):
        return False
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    if str(status.get("type") or "").lower() != "finished":
        return False
    description = str(status.get("description") or "").lower()
    if any(token in description for token in EXCLUDED_STATUS_TOKENS):
        return False
    filters = event.get("eventFilters") if isinstance(event.get("eventFilters"), dict) else {}
    categories = {str(item).lower() for item in (filters.get("category") or [])}
    if categories and "singles" not in categories:
        return False
    return event.get("winnerCode") in (1, 2, "1", "2")


def _cache_paths(player_id: Any) -> Iterable[Path]:
    direct = CACHE_DIR / f"{player_id}.json"
    if direct.exists():
        yield direct
    yield from sorted(CACHE_DIR.glob(f"{player_id}_*.json"))


def _read_events(player_id: Any) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    seen: set[str] = set()
    paths: List[str] = []
    invalid_files: List[str] = []
    ages: List[int] = []
    for path in _cache_paths(player_id):
        paths.append(str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("cache root is not an object")
            saved_at = float(payload.get("saved_at") or path.stat().st_mtime)
            age = int(max(time.time() - saved_at, 0))
            if age > MAX_CACHE_AGE_SECONDS:
                continue
            ages.append(age)
            data = payload.get("data", payload)
            rows = data.get("events", []) if isinstance(data, dict) else []
            if not isinstance(rows, list):
                raise ValueError("events is not a list")
        except (OSError, ValueError, json.JSONDecodeError):
            invalid_files.append(str(path))
            continue
        for event in rows:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or event.get("customId") or "")
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            events.append(event)
    freshness = "NO_CACHE"
    if ages:
        freshness = "FRESH" if max(ages) <= CACHE_TTL_SECONDS else "STALE_VERIFIED_CACHE"
    return {
        "events": events,
        "cache_paths": paths,
        "invalid_cache_files": invalid_files,
        "cache_freshness": freshness,
        "max_cache_age_seconds": max(ages) if ages else None,
    }


def _history(player_id: Any, player_name: str, surface: Any, event_id: Any, cutoff_value: Any) -> Dict[str, Any]:
    if player_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "matches": [], "reason": "Verified player ID is missing."}
    loaded = _read_events(player_id)
    if not loaded["cache_paths"]:
        return {"status": "NO_VERIFIED_CACHE", "matches": [], "reason": "Verified previous-match cache is missing.", **loaded}

    player_key = normalize_name(player_name)
    cutoff = _parse_date(cutoff_value)
    matches: List[Dict[str, Any]] = []
    excluded_unusable = 0
    excluded_after_cutoff = 0
    for event in loaded["events"]:
        if not _usable_finished_singles(event):
            excluded_unusable += 1
            continue
        current_key = str(event.get("id") or event.get("customId") or "")
        if event_id is not None and current_key == str(event_id):
            continue
        event_dt = _parse_date(event.get("startTimestamp"))
        if cutoff is not None and (event_dt is None or event_dt >= cutoff):
            excluded_after_cutoff += 1
            continue
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}
        is_home = str(_team_id(home)) == str(player_id)
        is_away = str(_team_id(away)) == str(player_id)
        if not is_home and not is_away:
            is_home = normalize_name(_team_name(home)) == player_key
            is_away = normalize_name(_team_name(away)) == player_key
        if not is_home and not is_away:
            continue
        winner_code = int(event["winnerCode"])
        matches.append({
            "event_id": current_key,
            "date": event_dt.date().isoformat() if event_dt else None,
            "timestamp": event_dt.timestamp() if event_dt else 0,
            "surface": _surface(event),
            "won": (is_home and winner_code == 1) or (is_away and winner_code == 2),
            "opponent": _team_name(away if is_home else home),
        })
    matches.sort(key=lambda item: float(item.get("timestamp") or 0), reverse=True)
    return {
        "status": "OK" if matches else "NO_USABLE_MATCHES",
        "reason": None if matches else "No verified completed singles matches were found before the cutoff.",
        "matches": matches,
        "raw_event_count": len(loaded["events"]),
        "usable_match_count": len(matches),
        "excluded_unusable": excluded_unusable,
        "excluded_after_cutoff": excluded_after_cutoff,
        **loaded,
    }


def _summary(sample: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(sample)
    wins = sum(1 for item in sample if item.get("won") is True)
    return {
        "available": total > 0,
        "count": total,
        "wins": wins if total else None,
        "losses": total - wins if total else None,
        "record": f"{wins}-{total - wins}" if total else "NO DATA",
        "win_pct": round(wins / total, 4) if total else None,
        "last_match_date": sample[0].get("date") if sample else None,
    }


def _windows(player: str, surface: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    matches = context.get("matches") if isinstance(context.get("matches"), list) else []
    requested = normalize_surface(surface)
    surface_matches = [item for item in matches if requested != "Unknown" and normalize_surface(item.get("surface")) == requested]
    return {
        "player": player,
        "normalized_player": normalize_name(player),
        "total_history_matches": len(matches),
        "last5": _summary(matches[:5]),
        "last10": _summary(matches[:10]),
        "surface": requested,
        "surface_last10": _summary(surface_matches[:10]),
        "cache_status": context.get("status"),
        "cache_freshness": context.get("cache_freshness"),
        "cache_paths": context.get("cache_paths", []),
    }


def _difference(first: Optional[float], second: Optional[float]) -> Optional[float]:
    return round(float(first) - float(second), 4) if first is not None and second is not None else None


def _edge(diff: Optional[float], weight: float, cap: float) -> Optional[float]:
    return round(max(min(diff * weight, cap), -cap), 4) if diff is not None else None


def _limited_response(pick: str, opponent: str, surface: Any, pick_history: Dict[str, Any], opponent_history: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "LIMITED_DATA",
        "source": "BLINQ_VERIFIED_API_PRO_MATCH_CACHE",
        "reason": "Verified previous-match data is unavailable for one or both players.",
        "surface": normalize_surface(surface),
        "pick": _windows(pick, surface, pick_history),
        "opponent": _windows(opponent, surface, opponent_history),
        "recent_form_edge": None,
        "short_form_edge": None,
        "surface_recent_form_edge": None,
        "form_confidence": None,
        "form_data_depth": 0.0,
        "pick_api_status": pick_history.get("status"),
        "opponent_api_status": opponent_history.get("status"),
        "flags": ["RECENT_FORM_LIMITED_DATA"],
    }


def build_recent_form_context(
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    level: Optional[str] = None,
    *_args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    del level
    pick_id = kwargs.get("pick_player_id") or kwargs.get("pick_team_id")
    opponent_id = kwargs.get("opponent_player_id") or kwargs.get("opponent_team_id")
    event_id = kwargs.get("event_id")
    cutoff = kwargs.get("match_start") or kwargs.get("start_time") or kwargs.get("as_of_date")
    pick_history = _history(pick_id, pick, surface, event_id, cutoff)
    opponent_history = _history(opponent_id, opponent, surface, event_id, cutoff)
    if not pick_history.get("matches") or not opponent_history.get("matches"):
        return _limited_response(pick, opponent, surface, pick_history, opponent_history)

    pick_stats = _windows(pick, surface, pick_history)
    opponent_stats = _windows(opponent, surface, opponent_history)
    last10_diff = _difference(pick_stats["last10"]["win_pct"], opponent_stats["last10"]["win_pct"])
    last5_diff = _difference(pick_stats["last5"]["win_pct"], opponent_stats["last5"]["win_pct"])
    surface_diff = _difference(pick_stats["surface_last10"]["win_pct"], opponent_stats["surface_last10"]["win_pct"])
    recent_edge = _edge(last10_diff, 0.08, 0.05)
    short_edge = _edge(last5_diff, 0.05, 0.035)
    surface_edge = _edge(surface_diff, 0.07, 0.05)

    p_total, o_total = pick_stats["last10"]["count"], opponent_stats["last10"]["count"]
    p_surface, o_surface = pick_stats["surface_last10"]["count"], opponent_stats["surface_last10"]["count"]
    form_depth = min(p_total, o_total) / 10.0
    surface_depth = min(p_surface, o_surface) / 5.0 if normalize_surface(surface) != "Unknown" else 0.0
    confidence = round(min(form_depth * 0.7 + min(surface_depth, 1.0) * 0.3, 1.0), 4)

    flags: List[str] = []
    if min(p_total, o_total) < 5:
        flags.append("RECENT_FORM_THIN_SAMPLE")
    if normalize_surface(surface) != "Unknown" and min(p_surface, o_surface) < 3:
        flags.append("SURFACE_FORM_THIN_SAMPLE")

    return {
        "status": "OK",
        "source": "BLINQ_VERIFIED_API_PRO_MATCH_CACHE",
        "surface": normalize_surface(surface),
        "pick": pick_stats,
        "opponent": opponent_stats,
        "recent_form_edge": recent_edge,
        "short_form_edge": short_edge,
        "surface_recent_form_edge": surface_edge,
        "effective_recent_form_edge": recent_edge,
        "effective_short_form_edge": short_edge,
        "effective_surface_recent_form_edge": surface_edge,
        "opponent_quality_edge": None,
        "effective_opponent_quality_edge": None,
        "form_confidence": confidence,
        "form_data_depth": round(confidence * 100.0, 1),
        "pick_api_status": pick_history.get("status"),
        "opponent_api_status": opponent_history.get("status"),
        "pick_api_usable_match_count": pick_history.get("usable_match_count"),
        "opponent_api_usable_match_count": opponent_history.get("usable_match_count"),
        "recent_form_sample_audit": {
            "pick_last10_count": p_total,
            "opponent_last10_count": o_total,
            "pick_surface_count": p_surface,
            "opponent_surface_count": o_surface,
            "cutoff": cutoff,
        },
        "flags": flags,
    }
