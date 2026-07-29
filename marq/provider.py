from __future__ import annotations

import json
import os
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import requests

TENNISAPI_HOST = "tennisapi1.p.rapidapi.com"
TENNISAPI_BASE_URL = "https://tennisapi1.p.rapidapi.com"
CACHE_DIR = Path("data/marq_ai")
CACHE_TTL_SECONDS = 60 * 60 * 12

# TennisApi provider ids verified from the provider list in RapidAPI Playground.
# Keep it moderate for a smooth run. We can extend later.
DEFAULT_PROVIDER_IDS = [1]

_RUN_EVENTS_ODDS_CACHE: Dict[str, Dict[str, Any]] = {}
_RUN_DETAILS_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_RUN_PROVIDER_ODDS_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_RUN_FAILED_DATES: set[str] = set()
_RATE_LIMITED = False


def _debug(message: str) -> None:
    print(f"MARQ TENNISAPI DEBUG: {message}")


def _api_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "").strip()


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": TENNISAPI_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _read_cache(path: Path, ttl_seconds: int = CACHE_TTL_SECONDS) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        saved_at = float(payload.get("saved_at", 0))
        if time.time() - saved_at > ttl_seconds:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_cache(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        _debug(f"cache write failed path={path} error={exc}")


def _get_json(path: str, cache_name: Optional[str] = None, force_refresh: bool = False) -> Optional[Any]:
    global _RATE_LIMITED

    if _RATE_LIMITED:
        _debug(f"skip request because rate_limit flag active path={path}")
        return None

    if not _api_key():
        _debug("RAPIDAPI_KEY missing")
        return None

    cache_file = _cache_path(cache_name) if cache_name else None
    if cache_file and not force_refresh:
        cached = _read_cache(cache_file)
        if cached is not None:
            return cached

    url = f"{TENNISAPI_BASE_URL}{path}"

    try:
        response = requests.get(url, headers=_headers(), timeout=25)
        status = response.status_code
        content_type = response.headers.get("content-type", "")
        text_preview = (response.text or "")[:350].replace("\n", " ")
        _debug(f"http status={status} path={path} content_type={content_type} body_preview={text_preview}")

        if status == 204:
            return None
        if status == 429:
            _RATE_LIMITED = True
            _debug(f"rate limited path={path}")
            return None
        if status >= 400:
            return None
        if not response.text or not response.text.strip():
            return None

        try:
            data = response.json()
        except Exception as exc:
            _debug(f"json parse failed path={path} error={exc} body_preview={text_preview}")
            return None

        if cache_file:
            _write_cache(cache_file, data)
        return data

    except Exception as exc:
        _debug(f"request failed path={path} error={exc}")
        return None


def _parse_date(date_only: str) -> Tuple[int, int, int]:
    dt = datetime.strptime(str(date_only)[:10], "%Y-%m-%d").date()
    return dt.day, dt.month, dt.year


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for ch in [".", ",", "'", "`", "’", "-", "_", "(", ")", "[", "]"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def _tokens(value: Any) -> set[str]:
    return set(_normalize_name(value).split())


def _name_score(a: str, b: str) -> float:
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    ta = _tokens(na)
    tb = _tokens(nb)
    if not ta or not tb:
        return 0.0
    score = len(ta & tb) / len(ta | tb)
    if ta and tb:
        # Surname-only / abbreviated-name support. Token order is not reliable after set(),
        # so this just gives a small boost when any last-looking token overlaps.
        ta_sorted = sorted(ta)
        tb_sorted = sorted(tb)
        if ta_sorted[-1] in tb or tb_sorted[-1] in ta:
            score = max(score, 0.60)
    return score


def _team_name(team: Any) -> str:
    if isinstance(team, dict):
        for key in ("name", "shortName", "fullName", "displayName", "slug"):
            value = team.get(key)
            if value:
                return str(value)
    return str(team or "")


def _extract_event(payload: Any) -> Optional[Dict[str, Any]]:
    if isinstance(payload, dict):
        event = payload.get("event")
        if isinstance(event, dict):
            return event
        data = payload.get("data")
        if isinstance(data, dict):
            event = data.get("event")
            if isinstance(event, dict):
                return event
            if data.get("homeTeam") or data.get("awayTeam"):
                return data
        if payload.get("homeTeam") or payload.get("awayTeam"):
            return payload
    return None


def _event_home_away(event: Dict[str, Any]) -> Tuple[str, str]:
    home = _team_name(event.get("homeTeam") or event.get("home") or event.get("participant1"))
    away = _team_name(event.get("awayTeam") or event.get("away") or event.get("participant2"))
    return home, away


def _fractional_to_decimal(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 1 else None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            numerator = float(left.strip())
            denominator = float(right.strip())
            if denominator == 0:
                return None
            return round(1.0 + numerator / denominator, 5)
        except Exception:
            return None
    try:
        number = float(text)
        return number if number > 1 else None
    except Exception:
        return None


def _extract_markets(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        markets = payload.get("markets")
        if isinstance(markets, list):
            return [m for m in markets if isinstance(m, dict)]
        odds = payload.get("odds")
        if isinstance(odds, list):
            return [m for m in odds if isinstance(m, dict)]
        data = payload.get("data")
        if isinstance(data, dict):
            markets = data.get("markets")
            if isinstance(markets, list):
                return [m for m in markets if isinstance(m, dict)]
        if isinstance(data, list):
            return [m for m in data if isinstance(m, dict)]
    if isinstance(payload, list):
        return [m for m in payload if isinstance(m, dict)]
    return []


def _select_full_time_market(markets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for market in markets:
        market_name = str(market.get("marketName") or market.get("name") or "").strip().lower()
        market_group = str(market.get("marketGroup") or "").strip().lower()
        market_period = str(market.get("marketPeriod") or "").strip().lower()
        if market_name == "full time" and ("home" in market_group or market_group == "home/away") and market_period in ("match", ""):
            return market
    for market in markets:
        market_name = str(market.get("marketName") or market.get("name") or "").strip().lower()
        if market_name in ("full time", "match winner", "winner", "to win"):
            return market
    return None


def _choice_side(choice: Dict[str, Any]) -> Optional[str]:
    name = str(choice.get("name") or choice.get("choice") or choice.get("label") or "").strip()
    lowered = name.lower()

    if name in ("1", "2"):
        return name
    if lowered in ("home", "player1", "player 1", "team1", "team 1"):
        return "1"
    if lowered in ("away", "player2", "player 2", "team2", "team 2"):
        return "2"
    return None


def _choice_current_decimal(choice: Dict[str, Any]) -> Optional[float]:
    return _fractional_to_decimal(
        choice.get("fractionalValue")
        or choice.get("decimalValue")
        or choice.get("value")
        or choice.get("odds")
        or choice.get("price")
    )


def _choice_initial_decimal(choice: Dict[str, Any]) -> Optional[float]:
    return _fractional_to_decimal(
        choice.get("initialFractionalValue")
        or choice.get("initialDecimalValue")
        or choice.get("openingFractionalValue")
        or choice.get("openingDecimalValue")
    )


def _safe_numeric(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _extract_choice_markets(market: Dict[str, Any]) -> Dict[str, Any]:
    choices = market.get("choices") or market.get("outcomes") or []
    output: Dict[str, Any] = {
        "odds_1": None,
        "odds_2": None,
        "initial_1": None,
        "initial_2": None,
        "change_1": None,
        "change_2": None,
        "choice_source_id_1": None,
        "choice_source_id_2": None,
    }

    if not isinstance(choices, list):
        return output

    for choice in choices:
        if not isinstance(choice, dict):
            continue

        side = _choice_side(choice)
        if side not in ("1", "2"):
            continue

        current = _choice_current_decimal(choice)
        initial = _choice_initial_decimal(choice)
        change = _safe_numeric(choice.get("change"))
        source_id = choice.get("sourceId")

        if side == "1":
            output["odds_1"] = current
            output["initial_1"] = initial
            output["change_1"] = change
            output["choice_source_id_1"] = source_id
        else:
            output["odds_2"] = current
            output["initial_2"] = initial
            output["change_2"] = change
            output["choice_source_id_2"] = source_id

    return output


def _extract_choice_odds(market: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    extracted = _extract_choice_markets(market)
    return extracted.get("odds_1"), extracted.get("odds_2")


def fetch_events_odds_by_date(date_only: str, force_refresh: bool = False) -> Dict[str, Any]:
    if date_only in _RUN_EVENTS_ODDS_CACHE and not force_refresh:
        return _RUN_EVENTS_ODDS_CACHE[date_only]
    if date_only in _RUN_FAILED_DATES and not force_refresh:
        return {}

    day, month, year = _parse_date(date_only)
    path = f"/api/tennis/events/odds/{day}/{month}/{year}"
    cache_name = f"tennisapi_events_odds_{year:04d}_{month:02d}_{day:02d}.json"
    payload = _get_json(path, cache_name=cache_name, force_refresh=force_refresh)

    result: Dict[str, Any] = {}
    if isinstance(payload, dict):
        odds = payload.get("odds")
        if isinstance(odds, dict):
            result = odds
        elif isinstance(odds, list):
            for item in odds:
                if isinstance(item, dict):
                    event_id = item.get("id") or item.get("eventId") or item.get("event_id")
                    if event_id:
                        result[str(event_id)] = item
        elif isinstance(payload.get("results"), dict):
            result = payload["results"]

    if not result:
        _RUN_FAILED_DATES.add(date_only)

    _RUN_EVENTS_ODDS_CACHE[date_only] = result
    _debug(f"events odds date={date_only} count={len(result)}")
    return result


def fetch_match_details(event_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    if event_id in _RUN_DETAILS_CACHE and not force_refresh:
        return _RUN_DETAILS_CACHE[event_id]

    # Confirmed by RapidAPI snippet: /api/tennis/event/{id}
    path = f"/api/tennis/event/{event_id}"
    cache_name = f"tennisapi_match_details_{event_id}.json"
    payload = _get_json(path, cache_name=cache_name, force_refresh=force_refresh)
    event = _extract_event(payload)

    if event:
        _RUN_DETAILS_CACHE[event_id] = event
        home, away = _event_home_away(event)
        _debug(f"match details ok event_id={event_id} path={path} home={home} away={away}")
        return event

    _RUN_DETAILS_CACHE[event_id] = None
    _debug(f"match details missing event_id={event_id}")
    return None


def find_tennisapi_event_for_match(player1: str, player2: str, date_only: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    odds_by_event = fetch_events_odds_by_date(date_only, force_refresh=force_refresh)
    if not odds_by_event:
        return None

    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    # Limit detail lookups to keep workflow smooth.
    for event_id in list(odds_by_event.keys())[:250]:
        event = fetch_match_details(str(event_id), force_refresh=force_refresh)
        if not event:
            continue
        home, away = _event_home_away(event)
        if not home or not away:
            continue

        direct = (_name_score(player1, home) + _name_score(player2, away)) / 2.0
        reverse = (_name_score(player1, away) + _name_score(player2, home)) / 2.0
        score = max(direct, reverse)

        if score > best_score:
            best_score = score
            best = {
                "event_id": str(event_id),
                "event": event,
                "home_name": home,
                "away_name": away,
                "match_direction": "direct" if direct >= reverse else "reverse",
                "match_score": round(score, 4),
                "bulk_odds": odds_by_event.get(str(event_id)),
            }

        if best_score >= 0.98:
            break

    if not best or best_score < 0.58:
        _debug(f"event not matched from odds feed player1={player1} player2={player2} date={date_only} best_score={best_score:.3f}")
        return None

    _debug(
        "event matched from odds feed "
        f"player1={player1} player2={player2} event_id={best['event_id']} "
        f"home={best['home_name']} away={best['away_name']} direction={best['match_direction']} score={best['match_score']}"
    )
    return best


def fetch_provider_odds(event_id: str, provider_id: int, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    key = f"{event_id}:{provider_id}"
    if key in _RUN_PROVIDER_ODDS_CACHE and not force_refresh:
        return _RUN_PROVIDER_ODDS_CACHE[key]

    # Main PRO market endpoint. It gives Full time, First set winner, Total games,
    # Tie break in match, plus initialFractionalValue/fractionalValue/change.
    candidates = [
        f"/api/tennis/event/{event_id}/odds/{provider_id}/all",
        # Fallbacks. Winning odds is useful only for Crowd, not for Move.
        f"/api/tennis/event/{event_id}/odds",
        f"/api/tennis/event/{event_id}/provider/{provider_id}/winning-odds",
        f"/api/tennis/event/{event_id}/provider/{provider_id}/odds",
    ]

    best_payload: Optional[Dict[str, Any]] = None
    best_market_count = 0

    for idx, path in enumerate(candidates):
        cache_name = f"tennisapi_provider_odds_{event_id}_{provider_id}_{idx}.json"
        payload = _get_json(path, cache_name=cache_name, force_refresh=force_refresh)
        markets = _extract_markets(payload)
        if markets:
            market_count = len(markets)
            if market_count > best_market_count:
                best_payload = payload
                best_market_count = market_count
            _debug(
                f"provider odds candidate ok event_id={event_id} "
                f"provider_id={provider_id} path={path} markets={len(markets)}"
            )
            # First candidate is the richest endpoint in current tests, use it immediately.
            if idx == 0:
                _RUN_PROVIDER_ODDS_CACHE[key] = payload
                return payload

    if best_payload is not None:
        _RUN_PROVIDER_ODDS_CACHE[key] = best_payload
        return best_payload

    _RUN_PROVIDER_ODDS_CACHE[key] = None
    _debug(f"provider odds missing event_id={event_id} provider_id={provider_id}")
    return None


def _quote_from_payload(payload: Any, event_id: str, provider_id: Optional[int], provider_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    markets = _extract_markets(payload)
    market = _select_full_time_market(markets)
    if not market:
        return None

    extracted = _extract_choice_markets(market)
    odds_1 = extracted.get("odds_1")
    odds_2 = extracted.get("odds_2")
    if odds_1 is None or odds_2 is None:
        return None

    initial_1 = extracted.get("initial_1")
    initial_2 = extracted.get("initial_2")

    return {
        "event_id": str(event_id),
        "provider_id": provider_id,
        "provider_name": provider_name or (f"provider_{provider_id}" if provider_id is not None else "bulk"),
        "source": "TennisApiPRO",
        "bookmaker": provider_name or (f"provider_{provider_id}" if provider_id is not None else "bulk"),
        "market_name": market.get("marketName") or market.get("name") or "Full time",
        "market_group": market.get("marketGroup"),
        "market_period": market.get("marketPeriod"),
        "market_id": market.get("marketId"),
        "source_id": market.get("sourceId"),
        "odds_1": odds_1,
        "odds_2": odds_2,
        "initial_1": initial_1,
        "initial_2": initial_2,
        "opening_1": initial_1,
        "opening_2": initial_2,
        "change_1": extracted.get("change_1"),
        "change_2": extracted.get("change_2"),
        "choice_source_id_1": extracted.get("choice_source_id_1"),
        "choice_source_id_2": extracted.get("choice_source_id_2"),
    }


def collect_market_quotes(event_id: str, bulk_odds: Any = None, provider_ids: Optional[List[int]] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
    provider_ids = provider_ids or DEFAULT_PROVIDER_IDS
    quotes: List[Dict[str, Any]] = []

    bulk_quote = _quote_from_payload(bulk_odds, event_id=event_id, provider_id=None, provider_name="bulk")
    if bulk_quote:
        quotes.append(bulk_quote)

    for provider_id in provider_ids:
        payload = fetch_provider_odds(event_id, provider_id, force_refresh=force_refresh)
        quote = _quote_from_payload(payload, event_id=event_id, provider_id=provider_id)
        if quote:
            signature = (round(quote["odds_1"], 4), round(quote["odds_2"], 4), quote.get("provider_id"))
            existing = {
                (round(q["odds_1"], 4), round(q["odds_2"], 4), q.get("provider_id"))
                for q in quotes
            }
            if signature not in existing:
                quotes.append(quote)

    _debug(f"market quotes event_id={event_id} count={len(quotes)}")
    return quotes


def _resolve_pick_outcome_key(player1: str, player2: str, pick: Optional[str]) -> str:
    if not pick:
        return "od1"
    p1 = _normalize_name(player1)
    p2 = _normalize_name(player2)
    pk = _normalize_name(pick)
    if pk == p1 or pk in p1 or p1 in pk or (_tokens(pk) & _tokens(p1)):
        return "od1"
    if pk == p2 or pk in p2 or p2 in pk or (_tokens(pk) & _tokens(p2)):
        return "od2"
    return "od1"


def _fallback_existing_odds(player1: str, player2: str, pick: Optional[str], odds_player1: Optional[float], odds_player2: Optional[float]) -> Optional[Dict[str, Any]]:
    try:
        od1 = float(odds_player1) if odds_player1 is not None else None
        od2 = float(odds_player2) if odds_player2 is not None else None
    except Exception:
        return None

    if od1 is None or od2 is None or od1 <= 1 or od2 <= 1:
        return None

    return {
        "source": "fallback_existing_odds_thin_market",
        "event_id": None,
        "player1": player1,
        "player2": player2,
        "home_name": player1,
        "away_name": player2,
        "match_direction": "direct",
        "pick_outcome_key": _resolve_pick_outcome_key(player1, player2, pick),
        "market_quotes": [
            {
                "event_id": None,
                "provider_id": None,
                "provider_name": "existing_odds",
                "market_name": "match_winner",
                "odds_1": od1,
                "odds_2": od2,
                "initial_1": od1,
                "initial_2": od2,
                "opening_1": od1,
                "opening_2": od2,
                "change_1": 0,
                "change_2": 0,
            }
        ],
        "odds": {
            "od1": {"opening": od1, "latest": od1, "current": od1, "change": 0},
            "od2": {"opening": od2, "latest": od2, "current": od2, "change": 0},
        },
    }



# ----------------------------------------------------------------------
# Bet365 Prematch MARQ source
# ----------------------------------------------------------------------

BET365_HOST = "bet365-api-inplay.p.rapidapi.com"
BET365_BASE_URL = "https://bet365-api-inplay.p.rapidapi.com"
BET365_EVENTS_CACHE_SECONDS = 60 * 60 * 12
BET365_MARKETS_CACHE_SECONDS = 60 * 20

TENNIS_LIVE_HOST = "tennis-live-api.p.rapidapi.com"
TENNIS_LIVE_BASE_URL = "https://tennis-live-api.p.rapidapi.com"
TENNIS_LIVE_MOVEMENTS_CACHE_SECONDS = 60 * 20

_RUN_BET365_EVENTS_CACHE: Optional[List[Dict[str, Any]]] = None
_RUN_BET365_MARKETS_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}


def _bet365_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": BET365_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _bet365_get_json(path: str, cache_name: Optional[str] = None, ttl_seconds: int = BET365_MARKETS_CACHE_SECONDS, force_refresh: bool = False) -> Optional[Any]:
    if not _api_key():
        _debug("Bet365 RAPIDAPI_KEY missing")
        return None

    cache_file = _cache_path(cache_name) if cache_name else None
    if cache_file and not force_refresh:
        cached = _read_cache(cache_file, ttl_seconds=ttl_seconds)
        if cached is not None:
            return cached

    url = f"{BET365_BASE_URL}{path}"
    try:
        response = requests.get(url, headers=_bet365_headers(), timeout=25)
        status = response.status_code
        preview = (response.text or "")[:350].replace("\n", " ")
        _debug(f"Bet365 http status={status} path={path} body_preview={preview}")
        if status == 204 or status >= 400 or not response.text.strip():
            return None
        try:
            data = response.json()
        except Exception as exc:
            _debug(f"Bet365 JSON parse failed path={path} error={exc}")
            return None
        if cache_file:
            _write_cache(cache_file, data)
        return data
    except Exception as exc:
        _debug(f"Bet365 request failed path={path} error={exc}")
        return None


def _extract_bet365_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("result", "data", "events", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = _extract_bet365_items(value)
                if nested:
                    return nested
    return []


def fetch_bet365_prematch_events(force_refresh: bool = False) -> List[Dict[str, Any]]:
    global _RUN_BET365_EVENTS_CACHE
    if _RUN_BET365_EVENTS_CACHE is not None and not force_refresh:
        return _RUN_BET365_EVENTS_CACHE
    payload = _bet365_get_json(
        "/bet365/get_prematch_sport_events/tennis",
        cache_name="bet365_prematch_events_tennis.json",
        ttl_seconds=BET365_EVENTS_CACHE_SECONDS,
        force_refresh=force_refresh,
    )
    items = _extract_bet365_items(payload)
    # Keep singles only for MARQ. Doubles can stay in ALL/debug elsewhere, but not in MARQ source.
    singles = []
    for item in items:
        team1 = str(item.get("team1") or "")
        team2 = str(item.get("team2") or "")
        if "/" in team1 or "/" in team2:
            continue
        if item.get("eventId") and team1 and team2:
            singles.append(item)
    _RUN_BET365_EVENTS_CACHE = singles
    _debug(f"Bet365 prematch events tennis count={len(singles)}")
    return singles


def find_bet365_event_for_match(player1: str, player2: str, date_only: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    events = fetch_bet365_prematch_events(force_refresh=force_refresh)
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for event in events:
        team1 = str(event.get("team1") or "")
        team2 = str(event.get("team2") or "")
        direct = (_name_score(player1, team1) + _name_score(player2, team2)) / 2.0
        reverse = (_name_score(player1, team2) + _name_score(player2, team1)) / 2.0
        score = max(direct, reverse)
        if score > best_score:
            best_score = score
            best = {
                "event_id": str(event.get("eventId")),
                "event": event,
                "team1": team1,
                "team2": team2,
                "match_direction": "direct" if direct >= reverse else "reverse",
                "match_score": round(score, 4),
            }
        if best_score >= 0.98:
            break
    if not best or best_score < 0.62:
        _debug(f"Bet365 event not matched player1={player1} player2={player2} best_score={best_score:.3f}")
        return None
    _debug(
        f"Bet365 event matched player1={player1} player2={player2} event_id={best['event_id']} "
        f"team1={best['team1']} team2={best['team2']} direction={best['match_direction']} score={best['match_score']}"
    )
    return best


def fetch_bet365_event_markets(event_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    if event_id in _RUN_BET365_MARKETS_CACHE and not force_refresh:
        return _RUN_BET365_MARKETS_CACHE[event_id]
    payload = _bet365_get_json(
        f"/bet365/get_prematch_event_with_markets/{event_id}",
        cache_name=f"bet365_prematch_event_markets_{event_id}.json",
        ttl_seconds=BET365_MARKETS_CACHE_SECONDS,
        force_refresh=force_refresh,
    )
    if isinstance(payload, dict):
        _RUN_BET365_MARKETS_CACHE[event_id] = payload
        return payload
    _RUN_BET365_MARKETS_CACHE[event_id] = None
    return None


def _extract_bet365_match_winner_odds(payload: Any, team1: str, team2: str) -> Tuple[Optional[float], Optional[float]]:
    markets = _extract_markets(payload)
    odds1 = None
    odds2 = None
    for market in markets:
        group = str(market.get("group") or "").strip().lower()
        if group != "to win match":
            continue
        coef = _safe_numeric(market.get("coef")) or _fractional_to_decimal(market.get("od"))
        if coef is None or coef <= 1:
            continue
        name = str(market.get("na") or market.get("designation") or "").strip()
        designation = str(market.get("designation") or "").strip()
        if name == "1" or _name_score(designation, team1) >= 0.80:
            odds1 = float(coef)
        elif name == "2" or _name_score(designation, team2) >= 0.80:
            odds2 = float(coef)
    return odds1, odds2



def _tennis_live_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": TENNIS_LIVE_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _tennis_live_get_json(path: str, cache_name: Optional[str] = None, ttl_seconds: int = TENNIS_LIVE_MOVEMENTS_CACHE_SECONDS, force_refresh: bool = False) -> Optional[Any]:
    if not _api_key():
        _debug("Tennis Live RAPIDAPI_KEY missing")
        return None

    cache_file = _cache_path(cache_name) if cache_name else None
    if cache_file and not force_refresh:
        cached = _read_cache(cache_file, ttl_seconds=ttl_seconds)
        if cached is not None:
            return cached

    url = f"{TENNIS_LIVE_BASE_URL}{path}"
    try:
        response = requests.get(url, headers=_tennis_live_headers(), timeout=25)
        status = response.status_code
        preview = (response.text or "")[:350].replace("\n", " ")
        _debug(f"Tennis Live movement http status={status} path={path} body_preview={preview}")
        if status == 204 or status >= 400 or not response.text.strip():
            return None
        try:
            data = response.json()
        except Exception as exc:
            _debug(f"Tennis Live movement JSON parse failed path={path} error={exc}")
            return None
        if cache_file:
            _write_cache(cache_file, data)
        return data
    except Exception as exc:
        _debug(f"Tennis Live movement request failed path={path} error={exc}")
        return None


def fetch_tennis_live_last10_movements(event_id: str, force_refresh: bool = False) -> Optional[Any]:
    # Endpoint confirmed from RapidAPI snippet:
    # /tennis/v2/extend/api/odds/summary/movements/last-10/{event_id}
    return _tennis_live_get_json(
        f"/tennis/v2/extend/api/odds/summary/movements/last-10/{event_id}",
        cache_name=f"tennis_live_last10_movements_{event_id}.json",
        ttl_seconds=TENNIS_LIVE_MOVEMENTS_CACHE_SECONDS,
        force_refresh=force_refresh,
    )


def _extract_bet365_full_time_movement_points(payload: Any) -> List[Dict[str, Any]]:
    """Return Bet365 Full Time Result movement points sorted by sourceAddTime.

    Expected RapidAPI shape observed in tests:
        result -> Bet365 -> Full Time Result -> [ {od1, od2, sourceAddTime, ...}, ... ]
    The helper is defensive because some responses use market/bookmaker casing variations.
    """
    if not isinstance(payload, dict):
        return []

    root = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    if not isinstance(root, dict):
        return []

    bookmaker_payload = None
    for book_name, book_value in root.items():
        if str(book_name).strip().lower() == "bet365" and isinstance(book_value, dict):
            bookmaker_payload = book_value
            break
    if bookmaker_payload is None:
        # Fall back to the first bookmaker-like dict.
        for book_value in root.values():
            if isinstance(book_value, dict):
                bookmaker_payload = book_value
                break
    if not isinstance(bookmaker_payload, dict):
        return []

    market_payload = None
    preferred_names = {"full time result", "full time", "match winner", "to win match"}
    for market_name, market_value in bookmaker_payload.items():
        if str(market_name).strip().lower() in preferred_names and isinstance(market_value, list):
            market_payload = market_value
            break
    if market_payload is None:
        for market_value in bookmaker_payload.values():
            if isinstance(market_value, list):
                market_payload = market_value
                break
    if not isinstance(market_payload, list):
        return []

    points: List[Dict[str, Any]] = []
    for item in market_payload:
        if not isinstance(item, dict):
            continue
        od1 = _safe_numeric(item.get("od1")) or _fractional_to_decimal(item.get("od1"))
        od2 = _safe_numeric(item.get("od2")) or _fractional_to_decimal(item.get("od2"))
        ts = _safe_numeric(item.get("sourceAddTime") or item.get("timestamp") or item.get("time"))
        if od1 is None or od2 is None or od1 <= 1 or od2 <= 1:
            continue
        # Guard against obvious live/final extremes. We want pre-snapshot trend, not final/live 1.001/101 data.
        if od1 < 1.03 or od2 < 1.03 or od1 > 50 or od2 > 50:
            continue
        points.append({"timestamp": int(ts or 0), "odds1": float(od1), "odds2": float(od2)})

    points.sort(key=lambda row: row.get("timestamp") or 0)
    return points


def _build_presnapshot_movement_from_points(points: List[Dict[str, Any]], current_odds1: float, current_odds2: float, pick_outcome_key: str) -> Dict[str, Any]:
    """Build movement where latest odds are the current snapshot odds.

    The earliest value is the oldest valid pre-snapshot movement point. The latest
    value is the current Bet365 prematch market odds captured by our snapshot.
    """
    if not points:
        return {
            "move_signal": "Pending",
            "move_pct": None,
            "move_range": None,
            "move_earliest_odds": None,
            "move_latest_odds": None,
            "opening_1": current_odds1,
            "opening_2": current_odds2,
            "movement_available": False,
            "movement_points_count": 0,
        }

    earliest_point = points[0]
    opening1 = float(earliest_point["odds1"])
    opening2 = float(earliest_point["odds2"])

    if pick_outcome_key == "od1":
        earliest = opening1
        latest = float(current_odds1)
    else:
        earliest = opening2
        latest = float(current_odds2)

    if earliest <= 1 or latest <= 1:
        return {
            "move_signal": "Pending",
            "move_pct": None,
            "move_range": None,
            "move_earliest_odds": earliest,
            "move_latest_odds": latest,
            "opening_1": opening1,
            "opening_2": opening2,
            "movement_available": False,
            "movement_points_count": len(points),
        }

    move_pct = round(abs((latest - earliest) / earliest) * 100.0, 1)
    if latest < earliest:
        direction = "Toward"
    elif latest > earliest:
        direction = "Against"
    else:
        direction = "Stable"

    label = _movement_label(move_pct, direction if direction != "Stable" else "Toward")
    if move_pct < 2.0:
        label = "Stable"
        direction = "Stable"

    return {
        "move_signal": label,
        "move_direction": direction,
        "move_pct": move_pct,
        # Range is useful even when movement is below the Stable threshold.
        # Example: 1.57 -> 1.55 should be visible, while missing movement data stays Pending.
        "move_range": f"{earliest:.2f} -> {latest:.2f}",
        "move_earliest_odds": round(earliest, 4),
        "move_latest_odds": round(latest, 4),
        "opening_1": opening1,
        "opening_2": opening2,
        "movement_available": True,
        "movement_points_count": len(points),
    }

def _bet365_snapshot_path(event_id: str) -> Path:
    path = CACHE_DIR / "bet365_snapshots" / f"{event_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_bet365_snapshots(event_id: str) -> List[Dict[str, Any]]:
    path = _bet365_snapshot_path(event_id)
    try:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshots = payload.get("snapshots") if isinstance(payload, dict) else None
        if isinstance(snapshots, list):
            return [s for s in snapshots if isinstance(s, dict)]
    except Exception:
        return []
    return []


def _save_bet365_snapshot(event_id: str, odds1: float, odds2: float) -> List[Dict[str, Any]]:
    snapshots = _load_bet365_snapshots(event_id)
    now = int(time.time())
    current = {"timestamp": now, "odds1": round(float(odds1), 5), "odds2": round(float(odds2), 5)}
    if not snapshots or snapshots[-1].get("odds1") != current["odds1"] or snapshots[-1].get("odds2") != current["odds2"]:
        snapshots.append(current)
    # Keep last 20 points only. Enough for morning trend and avoids unbounded cache growth.
    snapshots = snapshots[-20:]
    try:
        _bet365_snapshot_path(event_id).write_text(json.dumps({"snapshots": snapshots}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        _debug(f"Bet365 snapshot write failed event_id={event_id} error={exc}")
    return snapshots


def _movement_label(move_pct: Optional[float], direction: str) -> str:
    if move_pct is None:
        return "Pending"
    if move_pct < 2.0:
        return "Stable"
    if move_pct < 6.0:
        strength = "Slight"
    elif move_pct < 12.0:
        strength = "Medium"
    else:
        strength = "Strong"
    return f"{strength} {direction}"


def _build_bet365_movement(snapshots: List[Dict[str, Any]], pick_outcome_key: str) -> Dict[str, Any]:
    if len(snapshots) < 2:
        return {
            "move_signal": "Pending",
            "move_pct": None,
            "move_range": None,
            "move_earliest_odds": None,
            "move_latest_odds": None,
        }
    key = "odds1" if pick_outcome_key == "od1" else "odds2"
    earliest = _safe_numeric(snapshots[0].get(key))
    latest = _safe_numeric(snapshots[-1].get(key))
    if earliest is None or latest is None or earliest <= 1 or latest <= 1:
        return {
            "move_signal": "Pending",
            "move_pct": None,
            "move_range": None,
            "move_earliest_odds": earliest,
            "move_latest_odds": latest,
        }
    move_pct = round(abs((latest - earliest) / earliest) * 100.0, 1)
    if latest < earliest:
        direction = "Toward"
    elif latest > earliest:
        direction = "Against"
    else:
        direction = "Toward"
    label = _movement_label(move_pct, direction)
    if label == "Stable":
        direction = "Stable"
    return {
        "move_signal": label,
        "move_direction": direction,
        "move_pct": move_pct,
        "move_range": f"{earliest:.2f} -> {latest:.2f}",
        "move_earliest_odds": round(earliest, 4),
        "move_latest_odds": round(latest, 4),
    }


def _build_bet365_marq_market_data(player1: str, player2: str, date_only: str, pick: Optional[str], force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    event_match = find_bet365_event_for_match(player1, player2, date_only, force_refresh=force_refresh)
    if not event_match:
        return None
    event_id = str(event_match["event_id"])
    payload = fetch_bet365_event_markets(event_id, force_refresh=force_refresh)
    if not payload:
        return None
    odds_team1, odds_team2 = _extract_bet365_match_winner_odds(payload, event_match["team1"], event_match["team2"])
    if odds_team1 is None or odds_team2 is None:
        _debug(f"Bet365 To Win Match odds missing event_id={event_id}")
        return None

    # Convert Bet365 team order into project player1/player2 order.
    if event_match["match_direction"] == "direct":
        od1, od2 = odds_team1, odds_team2
    else:
        od1, od2 = odds_team2, odds_team1

    pick_outcome_key = _resolve_pick_outcome_key(player1, player2, pick)

    # Movement must represent the market trend before our snapshot. Therefore,
    # use Tennis Live Last 10 Odds Movement for the earliest points and treat the
    # current Bet365 prematch To Win Match odds as the latest snapshot odds.
    movement_payload = fetch_tennis_live_last10_movements(event_id, force_refresh=force_refresh)
    movement_points = _extract_bet365_full_time_movement_points(movement_payload)
    movement = _build_presnapshot_movement_from_points(movement_points, od1, od2, pick_outcome_key)

    # Still store our own snapshot for audit/debug, but do not use it as the main
    # movement source. The main movement source is pre-snapshot movement above.
    _save_bet365_snapshot(event_id, od1, od2)

    opening1 = movement.get("opening_1") or od1
    opening2 = movement.get("opening_2") or od2

    result = {
        "source": "bet365_prematch_marq",
        "event_id": event_id,
        "bet365_event_id": event_id,
        "player1": player1,
        "player2": player2,
        "home_name": event_match["team1"],
        "away_name": event_match["team2"],
        "match_direction": event_match["match_direction"],
        "match_score": event_match["match_score"],
        "pick_outcome_key": pick_outcome_key,
        "bookmaker": "Bet365",
        "market_quotes": [
            {
                "event_id": event_id,
                "provider_id": "bet365",
                "provider_name": "Bet365",
                "source": "Bet365PrematchAPI",
                "bookmaker": "Bet365",
                "market_name": "To Win Match",
                "odds_1": od1,
                "odds_2": od2,
                "initial_1": opening1,
                "initial_2": opening2,
                "opening_1": opening1,
                "opening_2": opening2,
                "change_1": None,
                "change_2": None,
            }
        ],
        "odds": {
            "od1": {"opening": opening1, "latest": od1, "current": od1, "change": None},
            "od2": {"opening": opening2, "latest": od2, "current": od2, "change": None},
        },
        "movement": movement,
        "marq_move_signal": movement.get("move_signal"),
        "marq_move_pct": movement.get("move_pct"),
        "marq_move_range": movement.get("move_range"),
        "marq_display_move_signal": movement.get("move_signal"),
        "marq_market_move_pct": movement.get("move_pct"),
        "marq_movement_available": movement.get("movement_available"),
        "bet365_movement_points_count": movement.get("movement_points_count"),
        "bet365_team1": event_match["team1"],
        "bet365_team2": event_match["team2"],
        "bet365_odds_team1": odds_team1,
        "bet365_odds_team2": odds_team2,
    }
    _debug(f"Bet365 MARQ data ok event_id={event_id} od1={od1} od2={od2} move={movement.get('move_signal')}")
    return result

def fetch_marq_market_data(
    player1: str,
    player2: str,
    date_only: str,
    pick: Optional[str] = None,
    odds_player1: Optional[float] = None,
    odds_player2: Optional[float] = None,
    force_refresh: bool = False,
    **_: Any,
) -> Optional[Dict[str, Any]]:
    bet365_market = _build_bet365_marq_market_data(
        player1=player1,
        player2=player2,
        date_only=date_only,
        pick=pick,
        force_refresh=force_refresh,
    )
    if bet365_market:
        return bet365_market

    event_match = find_tennisapi_event_for_match(player1, player2, date_only, force_refresh=force_refresh)

    if event_match:
        event_id = str(event_match["event_id"])
        quotes = collect_market_quotes(event_id, bulk_odds=event_match.get("bulk_odds"), force_refresh=force_refresh)
        if quotes:
            if event_match["match_direction"] == "direct":
                od1_quotes = [q["odds_1"] for q in quotes if q.get("odds_1")]
                od2_quotes = [q["odds_2"] for q in quotes if q.get("odds_2")]
            else:
                od1_quotes = [q["odds_2"] for q in quotes if q.get("odds_2")]
                od2_quotes = [q["odds_1"] for q in quotes if q.get("odds_1")]

            od1 = float(median(od1_quotes)) if od1_quotes else None
            od2 = float(median(od2_quotes)) if od2_quotes else None

            if event_match["match_direction"] == "direct":
                initial1_quotes = [q.get("initial_1") for q in quotes if q.get("initial_1")]
                initial2_quotes = [q.get("initial_2") for q in quotes if q.get("initial_2")]
                change1_quotes = [q.get("change_1") for q in quotes if q.get("change_1") is not None]
                change2_quotes = [q.get("change_2") for q in quotes if q.get("change_2") is not None]
            else:
                initial1_quotes = [q.get("initial_2") for q in quotes if q.get("initial_2")]
                initial2_quotes = [q.get("initial_1") for q in quotes if q.get("initial_1")]
                change1_quotes = [q.get("change_2") for q in quotes if q.get("change_2") is not None]
                change2_quotes = [q.get("change_1") for q in quotes if q.get("change_1") is not None]

            initial1 = float(median(initial1_quotes)) if initial1_quotes else od1
            initial2 = float(median(initial2_quotes)) if initial2_quotes else od2
            change1 = float(median(change1_quotes)) if change1_quotes else 0
            change2 = float(median(change2_quotes)) if change2_quotes else 0

            result = {
                "source": "tennisapi_market_quality",
                "event_id": event_id,
                "player1": player1,
                "player2": player2,
                "home_name": event_match["home_name"],
                "away_name": event_match["away_name"],
                "match_direction": event_match["match_direction"],
                "match_score": event_match["match_score"],
                "pick_outcome_key": _resolve_pick_outcome_key(player1, player2, pick),
                "market_quotes": quotes,
                "odds": {
                    "od1": {"opening": initial1, "latest": od1, "current": od1, "change": change1},
                    "od2": {"opening": initial2, "latest": od2, "current": od2, "change": change2},
                },
            }
            _debug(f"market quality data ok event_id={event_id} quotes={len(quotes)} od1={od1} od2={od2}")
            return result

        _debug(f"event matched but no provider quotes event_id={event_id}")

    fallback = _fallback_existing_odds(player1, player2, pick, odds_player1, odds_player2)
    if fallback:
        _debug(f"using fallback thin market player1={player1} player2={player2} odds1={odds_player1} odds2={odds_player2}")
        return fallback

    return None
