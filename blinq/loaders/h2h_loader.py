"""BlinQ H2H context from verified API PRO previous-match cache only."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CACHE_DIR = Path("blinq/data/form/previous_matches")
EXCLUDED_STATUS_TOKENS = ("retired", "walkover", "cancelled", "canceled", "postponed", "abandoned")


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _surface(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def _timestamp(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            return number / 1000.0 if number > 10_000_000_000 else number
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OSError):
        return None


def _team_id(team: Any) -> Any:
    if not isinstance(team, dict):
        return None
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return team.get("id") or info.get("id")


def _team_name(team: Any) -> str:
    return str(team.get("name") or team.get("shortName") or "") if isinstance(team, dict) else ""


def _event_surface(event: Dict[str, Any]) -> str:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    return _surface(event.get("groundType") or tournament.get("groundType") or unique.get("groundType"))


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


def _events(player_id: Any) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    seen: set[str] = set()
    paths: List[str] = []
    invalid_files: List[str] = []
    for path in _cache_paths(player_id):
        paths.append(str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
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
    return {"events": events, "cache_paths": paths, "invalid_cache_files": invalid_files}


def _empty(status: str, reason: str, requested: str, **extra: Any) -> Dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "source": "BLINQ_VERIFIED_API_PRO_MATCH_CACHE",
        "total_matches": 0,
        "pick_wins": None,
        "opponent_wins": None,
        "same_surface_matches": 0,
        "same_surface_pick_wins": None,
        "same_surface_opponent_wins": None,
        "requested_surface": requested,
        "data_depth": 0.0,
        "surface_data_depth": 0.0,
        **extra,
    }


def build_h2h_context(
    player1: str,
    player2: str,
    player1_id: Any,
    player2_id: Any,
    surface: Optional[str] = None,
    match_start: Any = None,
) -> Dict[str, Any]:
    requested = _surface(surface)
    if player1_id in (None, "") or player2_id in (None, ""):
        return _empty("NO_PLAYER_ID", "Verified player ID is missing.", requested)

    loaded = _events(player1_id)
    if not loaded["cache_paths"]:
        return _empty("NO_VERIFIED_CACHE", "Verified previous-match cache is missing.", requested)

    cutoff = _timestamp(match_start)
    p1_key, p2_key = _compact(player1), _compact(player2)
    matches: List[Dict[str, Any]] = []
    excluded_after_cutoff = 0
    excluded_unusable = 0

    for event in loaded["events"]:
        if not _usable_finished_singles(event):
            excluded_unusable += 1
            continue
        event_time = _timestamp(event.get("startTimestamp"))
        if cutoff is not None and (event_time is None or event_time >= cutoff):
            excluded_after_cutoff += 1
            continue
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}
        ids = {str(_team_id(home)), str(_team_id(away))}
        names = {_compact(_team_name(home)), _compact(_team_name(away))}
        ids_match = {str(player1_id), str(player2_id)} <= ids
        names_match = bool(p1_key and p2_key and {p1_key, p2_key} <= names)
        if not (ids_match or names_match):
            continue
        winner_code = int(event["winnerCode"])
        p1_home = str(_team_id(home)) == str(player1_id)
        if not p1_home and str(_team_id(away)) != str(player1_id):
            p1_home = _compact(_team_name(home)) == p1_key
        p1_won = (p1_home and winner_code == 1) or (not p1_home and winner_code == 2)
        matches.append({"p1_won": p1_won, "surface": _event_surface(event), "timestamp": event_time})

    matches.sort(key=lambda item: float(item.get("timestamp") or 0), reverse=True)
    if not matches:
        return _empty(
            "NO_PREVIOUS_MATCHES",
            "No verified completed singles H2H matches were found before the cutoff.",
            requested,
            cache_paths=loaded["cache_paths"],
            invalid_cache_files=loaded["invalid_cache_files"],
            excluded_after_cutoff=excluded_after_cutoff,
            excluded_unusable=excluded_unusable,
        )

    total = len(matches)
    p1_wins = sum(1 for item in matches if item["p1_won"])
    same = [item for item in matches if requested != "Unknown" and item["surface"] == requested]
    same_p1 = sum(1 for item in same if item["p1_won"])
    return {
        "status": "OK",
        "source": "BLINQ_VERIFIED_API_PRO_MATCH_CACHE",
        "total_matches": total,
        "pick_wins": p1_wins,
        "opponent_wins": total - p1_wins,
        "same_surface_matches": len(same),
        "same_surface_pick_wins": same_p1 if same else None,
        "same_surface_opponent_wins": len(same) - same_p1 if same else None,
        "requested_surface": requested,
        "match_start_cutoff": match_start,
        "excluded_after_cutoff": excluded_after_cutoff,
        "excluded_unusable": excluded_unusable,
        "cache_paths": loaded["cache_paths"],
        "invalid_cache_files": loaded["invalid_cache_files"],
        "data_depth": round(min(total / 5.0, 1.0) * 100.0, 1),
        "surface_data_depth": round(min(len(same) / 3.0, 1.0) * 100.0, 1),
    }
