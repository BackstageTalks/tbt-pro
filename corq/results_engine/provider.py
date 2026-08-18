from __future__ import annotations
import http.client
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

RAPIDAPI_HOST = "tennisapi1.p.rapidapi.com"


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _first_value(obj: Any, *keys: str) -> Any:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        cur: Any = obj
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur.get(part)
            else:
                ok = False
                break
        if ok and cur not in (None, "", "—", "-"):
            return cur
    return None


def status_from_obj(status: Any) -> str:
    """Normalize provider event status.

    VOID-like statuses must have priority over generic finished values because
    some providers can expose a winner together with retirement/walkover context.
    """
    candidates: List[Any] = []
    if isinstance(status, dict):
        for key in (
            "type",
            "description",
            "status",
            "statusType",
            "name",
            "code",
            "reason",
            "shortName",
        ):
            value = _first_value(status, key)
            if value not in (None, "", "—", "-"):
                candidates.append(value)
    else:
        candidates.append(status)

    texts = [_norm(value) for value in candidates if _norm(value)]
    text = texts[0] if texts else ""

    finished_values = {
        "100",
        "finished",
        "ended",
        "complete",
        "completed",
        "final",
        "after_extra_time",
        "after_penalties",
        "aet",
        "ft",
    }
    live_values = {
        "6",
        "7",
        "inprogress",
        "in_progress",
        "live",
        "started",
        "playing",
    }
    notstarted_values = {
        "0",
        "notstarted",
        "not_started",
        "scheduled",
        "open",
        "prematch",
        "upcoming",
    }
    void_values = {
        "60",
        "70",
        "cancelled",
        "canceled",
        "postponed",
        "retired",
        "retirement",
        "walkover",
        "wo",
        "w_o",
        "interrupted",
        "abandoned",
        "defaulted",
        "void",
    }

    # Check all status fields for explicit void-like context before classifying
    # the event as finished/live/not-started.
    for item in texts:
        if item in void_values:
            return item

    if text in finished_values:
        return "finished"
    if text in live_values:
        return "live"
    if text in notstarted_values:
        return "notstarted"
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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "winner", "won"}


def _winner_code_value(event: Dict[str, Any]) -> Any:
    return _first_value(
        event,
        "winnerCode",
        "winner_code",
        "winner.code",
        "winnerCode.value",
        "result.winnerCode",
        "status.winnerCode",
    )


def winner_from_event(event: Dict[str, Any]) -> str:
    if not isinstance(event, dict):
        return ""

    winner_code = _winner_code_value(event)
    winner_code_text = str(winner_code or "").strip().lower()

    if winner_code_text in {"1", "home", "home_team", "player1", "team1", "a"}:
        return name_from_team(event.get("homeTeam"))
    if winner_code_text in {"2", "away", "away_team", "player2", "team2", "b"}:
        return name_from_team(event.get("awayTeam"))

    home_team = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
    away_team = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}

    if _truthy(event.get("homeWinner")) or _truthy(home_team.get("winner")) or _truthy(home_team.get("isWinner")):
        return name_from_team(home_team)
    if _truthy(event.get("awayWinner")) or _truthy(away_team.get("winner")) or _truthy(away_team.get("isWinner")):
        return name_from_team(away_team)

    winner = event.get("winner")
    if isinstance(winner, dict):
        return name_from_team(winner) or str(winner.get("name") or winner.get("shortName") or "").strip()

    return str(event.get("winner") or event.get("winnerName") or event.get("winner_name") or "").strip()


def _as_int(value: Any) -> Optional[int]:
    if value in (None, "", "—", "-"):
        return None
    if isinstance(value, dict):
        value = _first_value(value, "current", "display", "value", "score", "games", "periodScore")
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def period_scores(score_obj: Any) -> List[Optional[int]]:
    if not isinstance(score_obj, dict):
        return []

    out: List[Optional[int]] = []
    for i in range(1, 6):
        value = None
        for key in (f"period{i}", f"set{i}", f"s{i}"):
            if key in score_obj:
                value = score_obj.get(key)
                break
        parsed = _as_int(value)
        if parsed is not None:
            out.append(parsed)
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
