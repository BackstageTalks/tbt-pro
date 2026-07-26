
"""CORQ odds helpers with TennisApi PRO fallback chain.

Purpose
-------
This module enriches normalized CORQ match records with a complete match-winner
odds pair. It keeps TOP7 strict (no odds means no publishable bet), while it
tries several TennisApi PRO odds endpoints before marking odds as missing.

Public API kept compatible with the existing project:
- get_event_odds(event_id, match=None)
- enrich_match_with_odds(match)

Main fields produced:
- odds_status: OK / MISSING
- odds_attempts: list of endpoint attempts and outcomes
- odds_source / odds_endpoint
- odds_player1 / odds_player2
- p1_odds / p2_odds / home_odds / away_odds / odds1 / odds2 / price1 / price2
- pick_odds / opponent_odds when pick_side is derivable
- odds_pair_available
- odds_labels_confirmed
- odds_matching_direction
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_HOST = "tennisapi1.p.rapidapi.com"
_EVENT_ODDS_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_DAILY_ODDS_CACHE: Dict[str, List[Dict[str, Any]]] = {}

_TRANSLATE = str.maketrans({
    "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D",
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th",
    "ß": "ss",
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "Ae",
    "œ": "oe", "Œ": "Oe",
})

WIN_MARKET_HINTS = (
    "full time",
    "to win",
    "match winner",
    "winner",
    "home/away",
    "1x2",
    "moneyline",
)


def _api_key() -> str:
    return (
        os.getenv("TENNISAPI_RAPIDAPI_KEY", "").strip()
        or os.getenv("RAPIDAPI_KEY", "").strip()
    )


def _provider_id() -> int:
    try:
        return int(os.getenv("TENNISAPI_PROVIDER_ID", "1"))
    except Exception:
        return 1


def _request_json(path: str, *, timeout: int = 30, retries: int = 2) -> Dict[str, Any]:
    key = _api_key()
    if not key:
        raise RuntimeError("Missing RAPIDAPI_KEY / TENNISAPI_RAPIDAPI_KEY")
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": _HOST,
        "Content-Type": "application/json",
    }
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        conn = None
        try:
            conn = http.client.HTTPSConnection(_HOST, timeout=timeout)
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            raw = res.read().decode("utf-8", errors="replace")
            if res.status == 204:
                return {}
            if res.status >= 400:
                raise RuntimeError(f"HTTP {res.status}: {raw[:400]}")
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {"data": data}
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.6)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
    raise RuntimeError(f"TennisApi request failed path={path} error={last_error}")


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _fractional_to_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    try:
        if "/" in text:
            left, right = text.split("/", 1)
            den = float(right)
            if den == 0:
                return None
            return round(1.0 + float(left) / den, 4)
        return round(float(text), 4)
    except Exception:
        return None


def _name_from_obj(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("name", "fullName", "full_name", "displayName", "display_name", "shortName", "short_name", "slug"):
            if value.get(key):
                return str(value.get(key))
        return ""
    return str(value)


def _normalize_name(value: Any) -> str:
    text = _name_from_obj(value).strip().lower().translate(_TRANSLATE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(".", " ").replace("-", " ").replace("_", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_name(value))


def _name_variants(normalized: str) -> set[str]:
    parts = normalized.split()
    keys: set[str] = set()
    compact = _compact_name(normalized)
    if normalized:
        keys.add(normalized)
    if compact:
        keys.add(compact)
    if parts:
        last = parts[-1]
        keys.add(last)
        keys.add(_compact_name(last))
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        last_two = " ".join(parts[-2:])
        keys.add(last_two)
        keys.add(_compact_name(last_two))
        keys.add(f"{first[0]} {last}")
        keys.add(f"{first[0]}{last}")
        keys.add(f"{last} {first[0]}")
        keys.add(f"{last}{first[0]}")
        if len(parts) > 2:
            initials = "".join(part[0] for part in parts[:-1])
            keys.add(f"{initials} {last}")
            keys.add(f"{initials}{last}")
    return {k for k in keys if k}


def _name_match_score(a: Any, b: Any) -> float:
    an = _normalize_name(a)
    bn = _normalize_name(b)
    if not an or not bn:
        return 0.0
    if an == bn:
        return 1.0
    ac = _compact_name(an)
    bc = _compact_name(bn)
    if ac and ac == bc:
        return 1.0
    common = _name_variants(an).intersection(_name_variants(bn))
    if common:
        if any(len(k) >= 4 and " " not in k for k in common):
            return 0.72
        return 0.9
    ap = an.split()
    bp = bn.split()
    if ap and bp and ap[-1] == bp[-1]:
        if ap[0][0] == bp[0][0]:
            return 0.86
        return 0.68
    ratio = SequenceMatcher(None, ac, bc).ratio() if ac and bc else 0.0
    if ratio >= 0.92:
        return 0.84
    if ratio >= 0.86:
        return 0.74
    return 0.0


def _pair_key(a: Any, b: Any) -> str:
    return "|".join(sorted([_compact_name(a), _compact_name(b)]))


def _first_present(item: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return None


def _extract_odds_pair(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    p1 = _first_present(item, (
        "odds_player1", "p1_odds", "home_odds", "odds1", "price1", "home_price",
        "player1_odds", "homeDecimalOdds", "home_decimal_odds",
    ))
    p2 = _first_present(item, (
        "odds_player2", "p2_odds", "away_odds", "odds2", "price2", "away_price",
        "player2_odds", "awayDecimalOdds", "away_decimal_odds",
    ))
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    if p1 is None and raw:
        p1 = _first_present(raw, ("odds_player1", "p1_odds", "home_odds", "odds1", "price1", "home_price"))
    if p2 is None and raw:
        p2 = _first_present(raw, ("odds_player2", "p2_odds", "away_odds", "odds2", "price2", "away_price"))
    return _to_float(p1), _to_float(p2)


def _apply_pair_aliases(item: Dict[str, Any], p1: Any, p2: Any) -> Dict[str, Any]:
    out = dict(item)
    for key in ("odds_player1", "p1_odds", "home_odds", "odds1", "price1"):
        out[key] = p1
    for key in ("odds_player2", "p2_odds", "away_odds", "odds2", "price2"):
        out[key] = p2
    return out


def _home_away_from_eventish(item: Dict[str, Any]) -> Tuple[str, str]:
    def n(*values: Any) -> str:
        for v in values:
            name = _name_from_obj(v)
            if name:
                return name
        return ""
    return (
        n(item.get("player1"), item.get("homeTeam"), item.get("home_team"), item.get("home"), item.get("participant1"), item.get("home_name")),
        n(item.get("player2"), item.get("awayTeam"), item.get("away_team"), item.get("away"), item.get("participant2"), item.get("away_name")),
    )


def _orient_to_requested(odds: Dict[str, Any], player1: Optional[str], player2: Optional[str]) -> Dict[str, Any]:
    if not player1 or not player2:
        odds.setdefault("odds_matching_direction", "DIRECT_OR_LABEL_UNKNOWN")
        return odds
    item_p1, item_p2 = _home_away_from_eventish(odds)
    if not item_p1 or not item_p2:
        odds.setdefault("odds_matching_direction", "DIRECT_OR_LABEL_UNKNOWN")
        return odds
    direct = _name_match_score(player1, item_p1) + _name_match_score(player2, item_p2)
    reverse = _name_match_score(player1, item_p2) + _name_match_score(player2, item_p1)
    p1, p2 = _extract_odds_pair(odds)
    if reverse > direct and p1 is not None and p2 is not None:
        out = _apply_pair_aliases(odds, p2, p1)
        out["player1"] = player1
        out["player2"] = player2
        out["odds_matching_direction"] = "REVERSED_TO_MATCH_PLAYERS"
        out["odds_labels_confirmed"] = True
        return out
    odds["player1"] = player1
    odds["player2"] = player2
    odds.setdefault("odds_matching_direction", "DIRECT_TO_MATCH_PLAYERS" if direct >= 1.2 else "DIRECT_OR_LABEL_UNKNOWN")
    odds["odds_labels_confirmed"] = odds.get("odds_matching_direction") != "DIRECT_OR_LABEL_UNKNOWN"
    return odds


def _normalize_winning_odds(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    data = payload
    if isinstance(data.get("odds"), dict):
        data = data["odds"]
    elif isinstance(data.get("data"), dict):
        data = data["data"]
    home = data.get("home") or {}
    away = data.get("away") or {}
    if not home or not away:
        return None
    home_dec = _fractional_to_decimal(home.get("fractionalValue") or home.get("fractional") or home.get("value"))
    away_dec = _fractional_to_decimal(away.get("fractionalValue") or away.get("fractional") or away.get("value"))
    if home_dec is None or away_dec is None:
        return None
    return {
        "home_odds": home_dec,
        "away_odds": away_dec,
        "odds_player1": home_dec,
        "odds_player2": away_dec,
        "p1_odds": home_dec,
        "p2_odds": away_dec,
        "raw": payload,
    }


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("events", "data", "items", "odds", "markets"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _extract_markets(raw: Any) -> List[Dict[str, Any]]:
    markets: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        for key in ("markets", "odds", "eventOdds", "data", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                markets.extend([x for x in value if isinstance(x, dict)])
            elif isinstance(value, dict):
                markets.extend(_extract_markets(value))
        # Sometimes the object itself is a market.
        if any(k in raw for k in ("choices", "outcomes", "participants")):
            markets.append(raw)
    elif isinstance(raw, list):
        for item in raw:
            markets.extend(_extract_markets(item))
    return markets


def _market_name(market: Dict[str, Any]) -> str:
    parts = []
    for key in ("name", "marketName", "market_name", "label", "type", "marketType"):
        if market.get(key):
            parts.append(str(market.get(key)))
    return _normalize_name(" ".join(parts))


def _market_choices(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    choices = market.get("choices") or market.get("outcomes") or market.get("participants") or market.get("selection")
    return [x for x in choices if isinstance(x, dict)] if isinstance(choices, list) else []


def _choice_to_decimal(choice: Dict[str, Any]) -> Optional[float]:
    for key in ("decimalValue", "decimal", "price", "odds", "value", "fractionalValue"):
        value = choice.get(key)
        if value is None:
            continue
        if isinstance(value, str) and "/" in value:
            out = _fractional_to_decimal(value)
        else:
            out = _to_float(value)
        if out is not None:
            return out
    return None


def _choice_text(choice: Dict[str, Any]) -> str:
    parts = []
    for key in ("name", "label", "choiceName", "participantName", "sourceName", "marketName", "outcomeName"):
        if choice.get(key):
            parts.append(str(choice.get(key)))
    return _normalize_name(" ".join(parts))


def _is_winner_market(name: str) -> bool:
    if not name:
        return False
    return any(hint in name for hint in WIN_MARKET_HINTS)


def _normalize_market_odds(payload: Any, *, player1: Optional[str] = None, player2: Optional[str] = None) -> Optional[Dict[str, Any]]:
    markets = _extract_markets(payload)
    if not markets:
        return None
    selected: Optional[Dict[str, Any]] = None
    for market in markets:
        name = _market_name(market)
        choices = _market_choices(market)
        if len(choices) < 2:
            continue
        if selected is None or _is_winner_market(name):
            selected = market
            if _is_winner_market(name):
                break
    if selected is None:
        return None
    choices = _market_choices(selected)
    if len(choices) < 2:
        return None

    p1_dec: Optional[float] = None
    p2_dec: Optional[float] = None
    # Prefer player name mapping, fallback to first two choices.
    for choice in choices:
        text = _choice_text(choice)
        dec = _choice_to_decimal(choice)
        if dec is None:
            continue
        if player1 and _name_match_score(player1, text) >= 0.68:
            p1_dec = dec
        elif player2 and _name_match_score(player2, text) >= 0.68:
            p2_dec = dec
    if p1_dec is None or p2_dec is None:
        vals = [_choice_to_decimal(c) for c in choices]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            p1_dec = p1_dec if p1_dec is not None else vals[0]
            p2_dec = p2_dec if p2_dec is not None else vals[1]
    if p1_dec is None or p2_dec is None:
        return None
    return {
        "odds_player1": p1_dec,
        "odds_player2": p2_dec,
        "p1_odds": p1_dec,
        "p2_odds": p2_dec,
        "home_odds": p1_dec,
        "away_odds": p2_dec,
        "raw": payload,
    }


def _date_from_match(match: Optional[Dict[str, Any]]) -> Optional[datetime]:
    if not isinstance(match, dict):
        return None
    ts = match.get("start_timestamp") or match.get("startTimestamp")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except Exception:
            pass
    for key in ("match_time_utc", "start_time_utc", "match_start", "start_time"):
        value = match.get(key)
        if not value:
            continue
        try:
            text = str(value).replace("Z", "+00:00")
            return datetime.fromisoformat(text)
        except Exception:
            pass
    return None


def _event_id(match_or_id: Any) -> Optional[str]:
    if isinstance(match_or_id, dict):
        for key in ("event_id", "match_id", "id"):
            val = match_or_id.get(key)
            if val:
                return str(val)
    elif match_or_id is not None:
        return str(match_or_id)
    return None


def _players_from_match(match: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(match, dict):
        return None, None
    p1 = match.get("player1") or match.get("home") or match.get("home_team") or match.get("homeTeam")
    p2 = match.get("player2") or match.get("away") or match.get("away_team") or match.get("awayTeam")
    p1s = _name_from_obj(p1) or None
    p2s = _name_from_obj(p2) or None
    return p1s, p2s


def _normalize_found_odds(found: Dict[str, Any], *, source: str, endpoint: str, event_id: Optional[str], match: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    p1_match, p2_match = _players_from_match(match)
    found = dict(found)
    found["source"] = source
    found["odds_source"] = source
    found["odds_endpoint"] = endpoint
    if event_id:
        found["event_id"] = event_id
        found["match_id"] = event_id
    found = _orient_to_requested(found, p1_match, p2_match)
    p1, p2 = _extract_odds_pair(found)
    if p1 is None or p2 is None:
        return None
    found = _apply_pair_aliases(found, p1, p2)
    found["odds_pair_available"] = True
    found.setdefault("bookmaker", "TennisApi")
    return found


def _find_in_daily_items(items: List[Dict[str, Any]], match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event_id = _event_id(match)
    p1, p2 = _players_from_match(match)
    req_pair = _pair_key(p1 or "", p2 or "")
    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for item in items:
        if not isinstance(item, dict):
            continue
        item_event_id = item.get("event_id") or item.get("match_id") or item.get("id")
        score = 0.0
        if event_id and item_event_id and str(item_event_id) == str(event_id):
            score = 2.0
        item_p1, item_p2 = _home_away_from_eventish(item)
        if item_p1 and item_p2 and p1 and p2:
            direct = _name_match_score(p1, item_p1) + _name_match_score(p2, item_p2)
            reverse = _name_match_score(p1, item_p2) + _name_match_score(p2, item_p1)
            pair = _pair_key(item_p1, item_p2)
            if req_pair and req_pair == pair:
                direct = max(direct, 1.98)
            score = max(score, direct, reverse)
        if score >= 1.4:
            p1o, p2o = _extract_odds_pair(item)
            candidate = item if p1o is not None and p2o is not None else _normalize_market_odds(item, player1=p1, player2=p2)
            if candidate and (best is None or score > best[0]):
                best = (score, candidate)
    return best[1] if best else None


def _fetch_daily_odds_items(match: Dict[str, Any], attempts: List[str]) -> List[Dict[str, Any]]:
    dt = _date_from_match(match) or datetime.now(timezone.utc)
    date_key = dt.strftime("%Y-%m-%d")
    if date_key in _DAILY_ODDS_CACHE:
        attempts.append("events_odds_by_date:CACHE")
        return _DAILY_ODDS_CACHE[date_key]
    path = f"/api/tennis/events/odds/{dt.day}/{dt.month}/{dt.year}"
    try:
        payload = _request_json(path)
        raw_items = _as_list(payload)
        items: List[Dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, dict):
                # keep raw item; market parser can normalize later
                norm = _normalize_market_odds(item)
                if norm:
                    norm.update({k: v for k, v in item.items() if k not in norm})
                    items.append(norm)
                else:
                    items.append(item)
        _DAILY_ODDS_CACHE[date_key] = items
        attempts.append(f"events_odds_by_date:OK:{len(items)}")
        return items
    except Exception as exc:
        attempts.append(f"events_odds_by_date:ERROR:{str(exc)[:80]}")
        _DAILY_ODDS_CACHE[date_key] = []
        return []


def _event_endpoint_attempts(event_id: str) -> List[Tuple[str, str, Callable[[Any], Optional[Dict[str, Any]]]]]:
    provider = _provider_id()
    return [
        ("match_winning_odds", f"/api/tennis/event/{event_id}/provider/{provider}/winning-odds", _normalize_winning_odds),
        ("match_betting_odds", f"/api/tennis/event/{event_id}/odds", _normalize_market_odds),
        ("all_odds_for_event", f"/api/tennis/event/{event_id}/odds/{provider}/all", _normalize_market_odds),
        ("featured_odds_1", f"/api/tennis/event/{event_id}/odds/featured", _normalize_market_odds),
        ("featured_odds_2", f"/api/tennis/event/{event_id}/featured-odds", _normalize_market_odds),
        ("featured_odds_3", f"/api/tennis/event/{event_id}/odds/1/featured", _normalize_market_odds),
    ]


def get_event_odds(event_id: Any, match: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    eid = _event_id(match or event_id)
    if not eid:
        return None
    cache_key = str(eid)
    if cache_key in _EVENT_ODDS_CACHE:
        return _EVENT_ODDS_CACHE[cache_key]

    attempts: List[str] = []

    if isinstance(match, dict):
        daily_items = _fetch_daily_odds_items(match, attempts)
        daily = _find_in_daily_items(daily_items, match)
        if daily:
            normalized = _normalize_found_odds(daily, source="TennisApi events odds by date", endpoint="events_odds_by_date", event_id=eid, match=match)
            if normalized:
                normalized["odds_attempts"] = attempts + ["events_odds_by_date:MATCH"]
                _EVENT_ODDS_CACHE[cache_key] = normalized
                return normalized
        attempts.append("events_odds_by_date:NO_MATCH")

    for name, path, normalizer in _event_endpoint_attempts(eid):
        try:
            payload = _request_json(path)
            normalized = normalizer(payload)
            if normalized:
                found = _normalize_found_odds(normalized, source=f"TennisApi {name}", endpoint=path, event_id=eid, match=match)
                if found:
                    found["odds_attempts"] = attempts + [f"{name}:OK"]
                    _EVENT_ODDS_CACHE[cache_key] = found
                    return found
            attempts.append(f"{name}:NO_MARKET")
        except Exception as exc:
            attempts.append(f"{name}:ERROR:{str(exc)[:80]}")

    missing = {
        "odds_status": "MISSING",
        "odds_attempts": attempts,
        "odds_pair_available": False,
        "event_id": eid,
    }
    _EVENT_ODDS_CACHE[cache_key] = missing
    return missing


def _pick_side(match: Dict[str, Any]) -> Optional[str]:
    side = str(match.get("pick_side") or match.get("side") or "").upper()
    if side in {"HOME", "PLAYER1", "P1", "1"}:
        return "HOME"
    if side in {"AWAY", "PLAYER2", "P2", "2"}:
        return "AWAY"
    pick = _normalize_name(match.get("pick"))
    p1 = _normalize_name(match.get("player1") or match.get("home") or match.get("home_team"))
    p2 = _normalize_name(match.get("player2") or match.get("away") or match.get("away_team"))
    if pick and p1 and _name_match_score(pick, p1) >= 0.82:
        return "HOME"
    if pick and p2 and _name_match_score(pick, p2) >= 0.82:
        return "AWAY"
    return None


def enrich_match_with_odds(match: Dict[str, Any]) -> Dict[str, Any]:
    event_id = match.get("event_id") or match.get("match_id") or match.get("id")
    odds = get_event_odds(event_id, match=match)
    enriched = dict(match)

    if not odds or not odds.get("odds_pair_available"):
        enriched["odds_status"] = "MISSING"
        enriched["odds_pair_available"] = False
        enriched["no_odds_reason"] = "NO_TENNISAPI_PRO_ODDS"
        enriched["odds_attempts"] = odds.get("odds_attempts") if isinstance(odds, dict) else []
        enriched["pick_odds"] = None
        enriched["opponent_odds"] = None
        return enriched

    p1, p2 = _extract_odds_pair(odds)
    side = _pick_side(enriched)
    pick_odds = p1 if side == "HOME" else p2 if side == "AWAY" else None
    opponent_odds = p2 if side == "HOME" else p1 if side == "AWAY" else None

    enriched.update({
        "odds_status": "OK",
        "odds_source": odds.get("odds_source") or odds.get("source"),
        "odds_endpoint": odds.get("odds_endpoint"),
        "odds_attempts": odds.get("odds_attempts", []),
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
        "pick_odds": pick_odds,
        "opponent_odds": opponent_odds,
        "odds_matching_direction": odds.get("odds_matching_direction"),
        "odds_labels_confirmed": bool(odds.get("odds_labels_confirmed")),
        "odds_pair_available": p1 is not None and p2 is not None and pick_odds is not None and opponent_odds is not None,
    })
    return enriched
