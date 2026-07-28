from __future__ import annotations

import http.client
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

RAPIDAPI_HOST = "tennisapi1.p.rapidapi.com"


def status_from_obj(status: Any) -> str:
    if isinstance(status, dict):
        raw = status.get("type") or status.get("description") or status.get("status") or status.get("code")
    else:
        raw = status
    text = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in {"100", "finished", "ended", "complete", "completed"}:
        return "finished"
    if text in {"inprogress", "in_progress", "live"}:
        return "live"
    if text in {"notstarted", "not_started", "scheduled", "open", "prematch", "upcoming"}:
        return "notstarted"
    if text in {"cancelled", "canceled", "postponed", "retired", "walkover", "interrupted", "abandoned"}:
        return text
    return text or "unknown"


def event_id(row: Dict[str, Any]) -> Optional[int]:
    for key in ("event_id", "match_id", "id"):
        value = row.get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except Exception:
                pass
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    value = raw.get("id")
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def fetch_event_detail(eid: int, cache: Dict[int, Dict[str, Any]], sleep_s: float = 0.05) -> Tuple[Optional[Dict[str, Any]], str]:
    if eid in cache:
        return cache[eid], "CACHE"
    api_key = os.getenv("RAPIDAPI_KEY", "").strip() or os.getenv("TENNISAPI_RAPIDAPI_KEY", "").strip()
    if not api_key:
        return None, "NO_API_KEY"
    path = f"/api/tennis/event/{eid}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=30)
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8", errors="replace")
        conn.close()
        if sleep_s:
            time.sleep(sleep_s)
        if res.status == 204 or not raw:
            return None, f"HTTP_{res.status}_EMPTY"
        if res.status >= 400:
            return None, f"HTTP_{res.status}"
        data = json.loads(raw)
        event = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), dict) else data
        if isinstance(event, dict):
            cache[eid] = event
            return event, "OK"
        return None, "NO_EVENT_OBJECT"
    except Exception as exc:
        return None, f"ERROR_{type(exc).__name__}"


def name_from_team(team: Any) -> str:
    if isinstance(team, dict):
        return str(team.get("name") or team.get("fullName") or team.get("shortName") or "").strip()
    return ""


def winner_from_event(event: Dict[str, Any]) -> str:
    winner_code = event.get("winnerCode")
    if winner_code == 1:
        return name_from_team(event.get("homeTeam"))
    if winner_code == 2:
        return name_from_team(event.get("awayTeam"))
    return str(event.get("winner") or event.get("winnerName") or "").strip()


def period_scores(score_obj: Any) -> List[Optional[int]]:
    if not isinstance(score_obj, dict):
        return []
    out: List[Optional[int]] = []
    for i in range(1, 6):
        value = score_obj.get(f"period{i}")
        if value is None:
            continue
        try:
            out.append(int(value))
        except Exception:
            out.append(None)
    return out


def score_from_event(event: Dict[str, Any]) -> Tuple[str, Optional[int], Optional[int], bool]:
    home_scores = period_scores(event.get("homeScore"))
    away_scores = period_scores(event.get("awayScore"))
    max_len = max(len(home_scores), len(away_scores))
    if not max_len:
        return "", None, None, False
    sets_home = 0
    sets_away = 0
    games_total = 0
    tiebreak = False
    parts: List[str] = []
    for i in range(max_len):
        h = home_scores[i] if i < len(home_scores) else None
        a = away_scores[i] if i < len(away_scores) else None
        if h is None or a is None:
            continue
        parts.append(f"{h}-{a}")
        games_total += h + a
        if h > a:
            sets_home += 1
        elif a > h:
            sets_away += 1
        if {h, a} in ({7, 6}, {6, 7}):
            tiebreak = True
    actual_sets = sets_home + sets_away if (sets_home or sets_away) else None
    return " ".join(parts), actual_sets, games_total if games_total else None, tiebreak
