from __future__ import annotations
import http.client, json, os, time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class TennisApiError(Exception):
    pass

class TennisApiClient:
    def __init__(self, api_key: Optional[str] = None, host: Optional[str] = None, timeout: int = 30, retries: int = 2):
        self.api_key = api_key or os.getenv("TENNISAPI_RAPIDAPI_KEY") or os.getenv("RAPIDAPI_KEY") or ""
        self.host = host or os.getenv("TENNISAPI_HOST", "tennisapi1.p.rapidapi.com")
        self.timeout = timeout
        self.retries = retries
        if not self.api_key:
            raise TennisApiError("Missing RAPIDAPI_KEY")

    def _headers(self):
        return {"x-rapidapi-key": self.api_key, "x-rapidapi-host": self.host, "Content-Type": "application/json"}

    def request_json(self, path: str) -> Dict[str, Any]:
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                conn = http.client.HTTPSConnection(self.host, timeout=self.timeout)
                conn.request("GET", path, headers=self._headers())
                res = conn.getresponse()
                raw = res.read().decode("utf-8", errors="replace")
                if res.status >= 400:
                    raise TennisApiError(f"HTTP {res.status} {path}: {raw[:400]}")
                if not raw:
                    return {}
                data = json.loads(raw)
                return data if isinstance(data, dict) else {"data": data}
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.8)
        raise TennisApiError(f"RapidAPI request failed for {path}: {last_error}")

    def get_events_by_date(self, target_date: datetime, category_ids: List[int]) -> List[Dict[str, Any]]:
        out, seen = [], set()
        for cid in category_ids:
            path = f"/api/tennis/category/{cid}/events/{target_date.day}/{target_date.month}/{target_date.year}"
            try:
                data = self.request_json(path)
                events = data.get("events") or data.get("data") or []
            except Exception as exc:
                print("CATEGORY FETCH ERROR", cid, exc)
                continue
            for event in events if isinstance(events, list) else []:
                eid = event.get("id")
                if eid in seen:
                    continue
                seen.add(eid)
                out.append(event)
        return out

    def get_winning_odds(self, event_id: int, provider_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        provider_id = provider_id or int(os.getenv("TENNISAPI_PROVIDER_ID", "1"))
        paths = [
            f"/api/tennis/event/{event_id}/provider/{provider_id}/winning-odds",
            f"/api/tennis/event/{event_id}/odds/{provider_id}/all",
        ]
        for path in paths:
            try:
                return self.request_json(path)
            except Exception as exc:
                print("ODDS PATH ERROR", path, exc)
        return None

def parse_category_ids() -> List[int]:
    out = []
    for part in os.getenv("TENNISAPI_CATEGORY_IDS", "3,6,871").split(","):
        try:
            if part.strip():
                out.append(int(part.strip()))
        except Exception:
            pass
    return out or [3, 6, 871]

def unix_to_iso(ts: Any) -> Optional[str]:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if ts else None
    except Exception:
        return None

def _status(status: Any) -> str:
    if not isinstance(status, dict):
        return "UNKNOWN"
    st = str(status.get("type") or "").lower()
    desc = str(status.get("description") or "").lower()
    code = status.get("code")
    if st in {"finished", "ended"} or desc in {"ended", "finished"} or code == 100:
        return "FINISHED"
    if st in {"notstarted", "not_started", "scheduled"}:
        return "NOT_STARTED"
    if st in {"inprogress", "in_progress", "live"}:
        return "LIVE"
    return st.upper() if st else "UNKNOWN"

def _gender(text: Any) -> Optional[str]:
    low = str(text or "").lower()
    if "wta" in low or "women" in low:
        return "WTA"
    if "atp" in low or "challenger" in low or "men" in low:
        return "ATP"
    return None

def _surface(text: Any) -> str:
    low = str(text or "").lower()
    if "clay" in low or "roland" in low or "french" in low:
        return "Clay"
    if "grass" in low or "wimbledon" in low:
        return "Grass"
    return "Hard"

def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(event.get("event"), dict):
        event = event["event"]
    home = event.get("homeTeam") or {}
    away = event.get("awayTeam") or {}
    tournament = event.get("tournament") or {}
    unique = tournament.get("uniqueTournament") or event.get("uniqueTournament") or {}
    category = tournament.get("category") or event.get("category") or {}
    name = unique.get("name") or tournament.get("name")
    return {
        "match_id": event.get("id"), "event_id": event.get("id"),
        "player1": home.get("name"), "player2": away.get("name"),
        "tournament": name, "category": category.get("name"), "category_id": category.get("id"),
        "gender": _gender(category.get("name") or name), "surface": _surface(name),
        "best_of": 5 if any(x in str(name or '').lower() for x in ["wimbledon","us open","australian open","roland garros","french open"]) else 3,
        "match_start": unix_to_iso(event.get("startTimestamp")), "status": _status(event.get("status") or {}), "raw": event,
    }

def _fractional_to_decimal(value: Any) -> Optional[float]:
    try:
        text = str(value).strip()
        if "/" in text:
            a, b = text.split("/", 1)
            b = float(b)
            return round(1 + float(a)/b, 4) if b else None
        val = float(text)
        return val if val > 1 else None
    except Exception:
        return None

def _choice_decimal(choice: Dict[str, Any]) -> Optional[float]:
    for key in ["decimalValue", "price", "odds", "value"]:
        try:
            val = choice.get(key)
            if val is not None and float(val) > 1:
                return round(float(val), 4)
        except Exception:
            pass
    for key in ["fractionalValue", "initialFractionalValue"]:
        val = _fractional_to_decimal(choice.get(key))
        if val:
            return val
    return None

def normalize_odds(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    source = payload.get("odds") if isinstance(payload.get("odds"), dict) else payload.get("data") if isinstance(payload.get("data"), dict) else payload
    home = source.get("home") if isinstance(source, dict) else None
    away = source.get("away") if isinstance(source, dict) else None
    if isinstance(home, dict) and isinstance(away, dict):
        o1, o2 = _choice_decimal(home), _choice_decimal(away)
        if o1 and o2:
            return {"odds_player1": o1, "odds_player2": o2, "odds_source": "TennisApi", "bookmaker": "RapidAPI"}
    markets = []
    if isinstance(source, dict):
        if isinstance(source.get("markets"), list): markets = source["markets"]
        elif isinstance(source.get("odds"), list): markets = source["odds"]
        elif isinstance(source.get("choices"), list): markets = [source]
    for market in markets:
        choices = market.get("choices") if isinstance(market, dict) else None
        if isinstance(choices, list) and len(choices) >= 2:
            o1, o2 = _choice_decimal(choices[0]), _choice_decimal(choices[1])
            if o1 and o2:
                return {"odds_player1": o1, "odds_player2": o2, "odds_source": "TennisApi", "bookmaker": "RapidAPI"}
    return {}
