"""BlinQ-only H2H loader from independent cached previous-match JSON files."""
from __future__ import annotations
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_DIR = Path("blinq/data/form/previous_matches")


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _surface(value: Any) -> str:
    text = str(value or "").lower()
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
        return parsed.timestamp()
    except Exception:
        return None

def _team_id(team: Any) -> Any:
    if not isinstance(team, dict):
        return None
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return team.get("id") or info.get("id")


def _events(player_id: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(CACHE_DIR.glob(f"{player_id}_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            data = payload.get("data", payload)
            events = data.get("events", []) if isinstance(data, dict) else []
        except Exception:
            continue
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict):
                continue
            key = str(event.get("id") or event.get("customId") or "")
            if key and key not in seen:
                rows.append(event)
                seen.add(key)
    return rows


def build_h2h_context(player1: str, player2: str, player1_id: Any, player2_id: Any,
                      surface: Optional[str] = None, match_start: Any = None) -> Dict[str, Any]:
    if player1_id in (None, "") or player2_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "source": "BLINQ_H2H_CACHE", "total_matches": 0, "same_surface_matches": 0}
    requested = _surface(surface)
    cutoff = _timestamp(match_start)
    p1_key, p2_key = _compact(player1), _compact(player2)
    matches: List[Dict[str, Any]] = []
    excluded_after_cutoff = 0
    for event in _events(player1_id):
        event_time = _timestamp(event.get("startTimestamp"))
        if cutoff is not None and event_time is not None and event_time >= cutoff:
            excluded_after_cutoff += 1
            continue
        status = event.get("status") if isinstance(event.get("status"), dict) else {}
        if str(status.get("type") or "").lower() != "finished":
            continue
        description = str(status.get("description") or "").lower()
        if any(x in description for x in ("retired", "walkover", "cancelled", "canceled", "abandoned")):
            continue
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}
        ids = {str(_team_id(home)), str(_team_id(away))}
        names = {_compact(home.get("name") or home.get("shortName")), _compact(away.get("name") or away.get("shortName"))}
        if not ({str(player1_id), str(player2_id)} <= ids or {p1_key, p2_key} <= names):
            continue
        try:
            winner_code = int(event.get("winnerCode"))
        except Exception:
            continue
        p1_home = str(_team_id(home)) == str(player1_id) or _compact(home.get("name")) == p1_key
        p1_won = (p1_home and winner_code == 1) or ((not p1_home) and winner_code == 2)
        tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
        unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
        matches.append({"p1_won": p1_won, "surface": _surface(event.get("groundType") or tournament.get("groundType") or unique.get("groundType"))})
    total = len(matches)
    p1_wins = sum(1 for item in matches if item["p1_won"])
    same = [item for item in matches if requested != "Unknown" and item["surface"] == requested]
    same_p1 = sum(1 for item in same if item["p1_won"])
    return {
        "status": "OK" if total else "NO_PREVIOUS_MATCHES",
        "source": "BLINQ_INDEPENDENT_H2H_CACHE",
        "total_matches": total,
        "pick_wins": p1_wins,
        "opponent_wins": total - p1_wins,
        "same_surface_matches": len(same),
        "same_surface_pick_wins": same_p1,
        "same_surface_opponent_wins": len(same) - same_p1,
        "requested_surface": requested,
        "match_start_cutoff": match_start,
        "excluded_after_cutoff": excluded_after_cutoff,
        "data_depth": round(min(total / 5.0, 1.0) * 100.0, 1),
        "surface_data_depth": round(min(len(same) / 3.0, 1.0) * 100.0, 1),
    }
