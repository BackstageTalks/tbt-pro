"""RapidAPI PRO client for CORQ runtime.

This patch keeps the simple robust name matcher, but adds a pragmatic rule for
RapidAPI odds payloads where outcome labels are numeric:
- label "1" means home/player1
- label "2" means away/player2

Therefore those odds are considered confirmed as DIRECT_BY_NUMERIC_OUTCOME.
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from corq.name_match import name_match_score, normalize_name
except Exception:
    from difflib import SequenceMatcher
    def normalize_name(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())
    def name_match_score(a: Any, b: Any) -> float:
        a_norm = normalize_name(a)
        b_norm = normalize_name(b)
        if not a_norm or not b_norm:
            return 0.0
        if a_norm == b_norm:
            return 1.0
        a_parts = a_norm.split()
        b_parts = b_norm.split()
        if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
            return 0.82
        return SequenceMatcher(None, a_norm, b_norm).ratio()

LOCAL_TZ = ZoneInfo("Europe/Bratislava")


class RapidApiError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("events", "data", "items", "categories", "results"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _team_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("name", "fullName", "full_name", "displayName", "display_name", "shortName", "short_name", "slug"):
            if value.get(key):
                return str(value.get(key)).strip()
        return None
    text = str(value).strip()
    return text or None


def parse_category_ids() -> List[int]:
    raw = os.getenv("TENNISAPI_CATEGORY_IDS", "3,6,871")
    ids: List[int] = []
    for part in raw.split(","):
        try:
            ids.append(int(part.strip()))
        except Exception:
            pass
    return ids or [3, 6, 871]


def target_betting_day(now: Optional[datetime] = None) -> datetime:
    current = now or datetime.now(LOCAL_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=LOCAL_TZ)
    current = current.astimezone(LOCAL_TZ)
    if current.hour < 6:
        current = current - timedelta(days=1)
    return current


def unix_to_datetime(timestamp: Any) -> Optional[datetime]:
    if timestamp in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except Exception:
        return None


def unix_to_iso(timestamp: Any) -> Optional[str]:
    dt = unix_to_datetime(timestamp)
    return dt.isoformat() if dt else None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return unix_to_datetime(value)
    if isinstance(value, str):
        try:
            text = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def normalize_surface(value: Any) -> Tuple[str, Optional[str]]:
    raw = str(value or "").strip()
    text = raw.lower()
    if "clay" in text:
        return "Clay", raw or None
    if "grass" in text:
        return "Grass", raw or None
    if "carpet" in text:
        return "Hard", raw or None
    if "hard" in text or "indoor" in text:
        return "Hard", raw or None
    return "Unknown", raw or None


def deep_find_first(obj: Any, keys: Iterable[str]) -> Any:
    wanted = set(keys)
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) in wanted and value not in (None, ""):
                return value
        for value in obj.values():
            found = deep_find_first(value, wanted)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = deep_find_first(item, wanted)
            if found not in (None, ""):
                return found
    return None


def event_status_type(event: Dict[str, Any]) -> str:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    return str(status.get("type") or status.get("description") or "unknown").strip().lower()


def event_status_code(event: Dict[str, Any]) -> Optional[int]:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    try:
        return int(status.get("code"))
    except Exception:
        return None


def is_event_notstarted_future(event: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    status_type = event_status_type(event)
    status_code = event_status_code(event)
    if status_type not in {"notstarted", "not started", "scheduled", "unknown"}:
        return False, f"status_type={status_type}"
    if status_code not in (None, 0):
        return False, f"status_code={status_code}"
    start_raw = event.get("startTimestamp") or event.get("start_timestamp") or deep_find_first(event, {"startTimestamp", "start_time"})
    start_dt = parse_datetime(start_raw)
    if start_dt is None:
        return False, "missing_start_time"
    min_minutes = _env_int("TENNISAPI_MIN_MINUTES_BEFORE_START", 10)
    if start_dt <= current + timedelta(minutes=max(min_minutes, 0)):
        return False, f"start_time_too_close_or_past={start_dt.isoformat()}"
    return True, None


@dataclass
class RapidApiClient:
    api_key: Optional[str] = None
    host: Optional[str] = None
    timeout: int = 30
    sleep_seconds: float = 0.15

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("RAPIDAPI_KEY")
        self.host = self.host or os.getenv("TENNISAPI_RAPIDAPI_HOST") or os.getenv("RAPIDAPI_HOST") or "tennisapi1.p.rapidapi.com"
        if requests is None:
            raise RapidApiError("requests package is not installed")
        if not self.api_key:
            raise RapidApiError("RAPIDAPI_KEY is missing")

    @property
    def headers(self) -> Dict[str, str]:
        return {"x-rapidapi-key": str(self.api_key), "x-rapidapi-host": str(self.host)}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"https://{self.host}{path}"
        try:
            response = requests.get(url, headers=self.headers, params=params or {}, timeout=self.timeout)
            if response.status_code in (204, 404):
                return None
            response.raise_for_status()
            if not response.text:
                return None
            return response.json()
        except Exception:
            return None
        finally:
            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)

    def discover_categories(self, target_date: datetime) -> List[int]:
        day, month, year = target_date.day, target_date.month, target_date.year
        for path in (f"/api/tennis/calendar/{day}/{month}/{year}/categories", f"/api/tennis/categories/{day}/{month}/{year}"):
            payload = self.get(path)
            found: List[int] = []
            for item in _as_list(payload):
                if not isinstance(item, dict):
                    continue
                value = item.get("id") or item.get("categoryId") or item.get("category_id")
                try:
                    found.append(int(value))
                except Exception:
                    pass
            if found:
                return sorted(set(found))
        return parse_category_ids()

    def get_events_for_category(self, category_id: int, target_date: datetime) -> List[Dict[str, Any]]:
        day, month, year = target_date.day, target_date.month, target_date.year
        paths = (
            f"/api/tennis/category/{category_id}/events/{day}/{month}/{year}",
            f"/api/tennis/categories/{category_id}/events/{day}/{month}/{year}",
        )
        for path in paths:
            payload = self.get(path)
            events = [item for item in _as_list(payload) if isinstance(item, dict)]
            if events:
                return events
        return []

    def get_events_for_date(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        day = target_betting_day(target_date)
        events: List[Dict[str, Any]] = []
        for category_id in self.discover_categories(day):
            events.extend(self.get_events_for_category(category_id, day))
        return dedupe_events(events)

    def get_event_odds(self, event_id: Any) -> Optional[Dict[str, Any]]:
        if event_id in (None, ""):
            return None
        provider = _env_int("TENNISAPI_PROVIDER_ID", 1)
        event_id_text = str(event_id)
        attempts = [
            (f"/api/tennis/event/{event_id_text}/odds", None),
            (f"/api/tennis/event/{event_id_text}/winning-odds", None),
            (f"/api/tennis/event/{event_id_text}/provider/{provider}/winning-odds", None),
            (f"/api/tennis/event/{event_id_text}/provider/{provider}/odds", None),
            (f"/api/tennis/event/{event_id_text}/odds/{provider}", None),
            ("/api/tennis/getMatchWinningOdds", {"matchId": event_id_text, "providerId": provider}),
            ("/api/tennis/getMatchBettingOdds", {"matchId": event_id_text, "providerId": provider}),
            ("/api/tennis/getAllOddsForEvent", {"eventId": event_id_text}),
            ("/api/tennis/getMatchFeaturedOdds", {"matchId": event_id_text}),
        ]
        for path, params in attempts:
            payload = self.get(path, params=params)
            normalized = normalize_winner_odds_payload(payload)
            if normalized:
                normalized["odds_endpoint"] = path
                return normalized
        return None


def dedupe_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for event in events:
        event_id = event.get("id") or event.get("event_id") or event.get("match_id")
        home, away = event_players(event)
        key = event_id or f"{normalize_name(home)}::{normalize_name(away)}::{event.get('startTimestamp') or event.get('start_time')}"
        if key in seen:
            continue
        seen.add(key)
        output.append(event)
    return output


def event_players(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    home = event.get("homeTeam") or event.get("home_team") or event.get("home") or event.get("player1") or event.get("participant1")
    away = event.get("awayTeam") or event.get("away_team") or event.get("away") or event.get("player2") or event.get("participant2")
    return _team_name(home), _team_name(away)


def is_doubles_name(name: Any) -> bool:
    text = str(name or "")
    return "/" in text or " & " in text or " + " in text


def _category_name(event: Dict[str, Any]) -> Optional[str]:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    category = tournament.get("category") if isinstance(tournament.get("category"), dict) else {}
    if category.get("name"):
        return str(category.get("name"))
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    unique_category = unique.get("category") if isinstance(unique.get("category"), dict) else {}
    if unique_category.get("name"):
        return str(unique_category.get("name"))
    return None


def normalize_event_for_corq(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ok, _reason = is_event_notstarted_future(event)
    if not ok:
        return None
    player1, player2 = event_players(event)
    if not player1 or not player2:
        return None
    event_id = event.get("id") or event.get("event_id") or event.get("match_id")
    start_ts = event.get("startTimestamp") or event.get("start_timestamp") or deep_find_first(event, {"startTimestamp", "start_time"})
    raw_surface = event.get("surfaceType") or event.get("surface") or event.get("groundType") or deep_find_first(event, {"surfaceType", "surface", "courtSurface", "groundType"})
    surface, surface_raw = normalize_surface(raw_surface)
    tournament_obj = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament_obj.get("uniqueTournament") if isinstance(tournament_obj.get("uniqueTournament"), dict) else {}
    tournament = _team_name(tournament_obj) or _team_name(unique)
    category_name = _category_name(event)
    event_filters = event.get("eventFilters") if isinstance(event.get("eventFilters"), dict) else {}
    gender_values = event_filters.get("gender")
    gender = gender_values[0] if isinstance(gender_values, list) and gender_values else category_name
    start_iso = unix_to_iso(start_ts) or event.get("start_time") or event.get("match_start")
    return {
        "match_id": event_id,
        "event_id": event_id,
        "id": event_id,
        "player1": player1,
        "player2": player2,
        "surface": surface,
        "surface_raw": surface_raw,
        "tournament": tournament,
        "category": category_name,
        "level": category_name,
        "gender": gender,
        "best_of": 5 if "grand slam" in normalize_name(tournament) else 3,
        "match_start": start_iso,
        "start_time": start_iso,
        "status_type": event_status_type(event),
        "status_code": event_status_code(event),
        "is_doubles": is_doubles_name(player1) or is_doubles_name(player2),
        "source": "RapidAPI PRO",
        "raw": event,
    }


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def fractional_to_decimal(value: Any) -> Optional[float]:
    if not isinstance(value, str) or "/" not in value:
        return _to_float(value)
    try:
        left, right = value.split("/", 1)
        return round((float(left) / float(right)) + 1.0, 4)
    except Exception:
        return None


def extract_markets(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    markets: List[Dict[str, Any]] = []
    for key in ("markets", "odds", "eventOdds", "winningOdds", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            markets.extend([item for item in value if isinstance(item, dict)])
        elif isinstance(value, dict):
            markets.extend(extract_markets(value))
    if not markets and any(k in payload for k in ("choices", "outcomes", "participants", "selections")):
        markets.append(payload)
    return markets


def market_choices(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("choices", "outcomes", "participants", "selections"):
        value = market.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def choice_name(choice: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("name", "label", "choiceName", "participantName", "sourceName", "marketName"):
        if choice.get(key):
            parts.append(str(choice.get(key)))
    return " ".join(parts).strip()


def choice_price(choice: Dict[str, Any]) -> Optional[float]:
    for key in ("decimalValue", "decimal", "decimalOdds", "price", "odds", "value", "fractionalValue"):
        converted = fractional_to_decimal(choice.get(key))
        if converted is not None:
            return converted
    return None


def normalize_winner_odds_payload(payload: Any) -> Optional[Dict[str, Any]]:
    for market in extract_markets(payload):
        market_name = normalize_name(" ".join(str(market.get(k) or "") for k in ("name", "marketName", "market_name", "label", "type")))
        choices = market_choices(market)
        if len(choices) < 2:
            continue
        if market_name and not any(token in market_name for token in ("winner", "match", "to win", "full time", "moneyline")):
            continue
        prices = [(choice_name(choice), choice_price(choice)) for choice in choices]
        prices = [(label, price) for label, price in prices if price is not None]
        if len(prices) >= 2:
            return {
                "player1_label": prices[0][0],
                "player2_label": prices[1][0],
                "odds_player1": prices[0][1],
                "odds_player2": prices[1][1],
                "p1_odds": prices[0][1],
                "p2_odds": prices[1][1],
                "home_odds": prices[0][1],
                "away_odds": prices[1][1],
                "odds1": prices[0][1],
                "odds2": prices[1][1],
                "bookmaker": None,
                "odds_source": "RapidAPI PRO event odds",
                "raw": payload,
            }
    return None


def _numeric_outcome_direction(label1: Any, label2: Any) -> Optional[str]:
    l1 = normalize_name(label1)
    l2 = normalize_name(label2)
    if l1 in {"1", "home", "home team", "player 1", "player1"} and l2 in {"2", "away", "away team", "player 2", "player2"}:
        return "DIRECT_BY_NUMERIC_OUTCOME"
    if l1 in {"2", "away", "away team", "player 2", "player2"} and l2 in {"1", "home", "home team", "player 1", "player1"}:
        return "REVERSED_BY_NUMERIC_OUTCOME"
    return None


def orient_odds_to_match(match: Dict[str, Any], odds: Dict[str, Any]) -> Tuple[Any, Any, str, float, float]:
    p1 = odds.get("odds_player1")
    p2 = odds.get("odds_player2")
    label1 = odds.get("player1_label")
    label2 = odds.get("player2_label")
    player1 = match.get("player1")
    player2 = match.get("player2")

    numeric_direction = _numeric_outcome_direction(label1, label2)
    if numeric_direction == "DIRECT_BY_NUMERIC_OUTCOME":
        return p1, p2, numeric_direction, 1.0, 0.0
    if numeric_direction == "REVERSED_BY_NUMERIC_OUTCOME":
        return p2, p1, numeric_direction, 0.0, 1.0

    direct_score = min(name_match_score(player1, label1), name_match_score(player2, label2)) if label1 and label2 else 0.0
    reverse_score = min(name_match_score(player1, label2), name_match_score(player2, label1)) if label1 and label2 else 0.0

    if direct_score >= 0.78 and direct_score >= reverse_score:
        return p1, p2, "DIRECT_TO_MATCH_PLAYERS", round(direct_score, 4), round(reverse_score, 4)
    if reverse_score >= 0.78 and reverse_score > direct_score:
        return p2, p1, "REVERSED_TO_MATCH_PLAYERS", round(direct_score, 4), round(reverse_score, 4)
    return p1, p2, "DIRECT_OR_LABEL_UNKNOWN", round(direct_score, 4), round(reverse_score, 4)


def fetch_daily_matches_with_odds(target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    client = RapidApiClient()
    raw_events = client.get_events_for_date(target_date)
    matches = [item for item in (normalize_event_for_corq(event) for event in raw_events) if isinstance(item, dict)]
    output: List[Dict[str, Any]] = []

    for match in matches:
        if match.get("is_doubles"):
            continue
        odds = client.get_event_odds(match.get("event_id"))
        row = dict(match)
        if odds:
            p1, p2, direction, direct_score, reverse_score = orient_odds_to_match(match, odds)
            row.update({
                "odds_matching_direction": direction,
                "odds_label_1": odds.get("player1_label"),
                "odds_label_2": odds.get("player2_label"),
                "odds_direct_match_score": direct_score,
                "odds_reverse_match_score": reverse_score,
                "odds_player1": p1,
                "odds_player2": p2,
                "p1_odds": p1,
                "p2_odds": p2,
                "home_odds": p1,
                "away_odds": p2,
                "odds1": p1,
                "odds2": p2,
                "price1": p1,
                "price2": p2,
                "odds_source": odds.get("odds_source"),
                "odds_endpoint": odds.get("odds_endpoint"),
                "odds_pair_available": p1 is not None and p2 is not None,
                "odds_labels_confirmed": direction in {
                    "DIRECT_TO_MATCH_PLAYERS",
                    "REVERSED_TO_MATCH_PLAYERS",
                    "DIRECT_BY_NUMERIC_OUTCOME",
                    "REVERSED_BY_NUMERIC_OUTCOME",
                },
            })
            if p1 is not None and p2 is not None:
                gap = abs(float(p1) - float(p2))
                row["odds_gap_abs"] = round(gap, 4)
                row["odds_gap_pct"] = round(gap / max(min(float(p1), float(p2)), 0.0001), 4)
        else:
            row.update({
                "odds_pair_available": False,
                "odds_labels_confirmed": False,
                "odds_matching_direction": "NO_ODDS",
                "no_odds_reason": "NO_RAPIDAPI_PRO_ODDS",
            })
        output.append(row)
    return output
