import os
import re
import time
import unicodedata
from urllib.parse import quote
from typing import Any, Dict, Optional

import requests

RAPID_API_HOST = "tennis-api-atp-wta-itf.p.rapidapi.com"
BASE_URL = f"https://{RAPID_API_HOST}"
TIMEOUT = 20

_LAST_REQUEST_TS = 0.0
_LAST_STATUS: Dict[str, Any] = {}
API_REQUEST_AUDIT = []


def _api_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "").strip()


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPID_API_HOST,
        "x-rapidapi-key": _api_key(),
    }


def _min_delay_seconds() -> float:
    try:
        rps = float(os.getenv("MARQ_RAPIDAPI_MAX_RPS", "5"))
        if rps <= 0:
            rps = 5.0
        return max(0.20, (1.0 / rps) + 0.02)
    except Exception:
        return 0.24


def _throttle() -> None:
    global _LAST_REQUEST_TS
    now = time.time()
    wait = _min_delay_seconds() - (now - _LAST_REQUEST_TS)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TS = time.time()


def _record(path: str, status: Optional[int], ok: bool, note: str) -> None:
    global _LAST_STATUS
    _LAST_STATUS = {
        "path": path,
        "status_code": status,
        "ok": bool(ok),
        "note": note,
        "helper": "rapid_api.py:2026-08-02-max5",
    }
    API_REQUEST_AUDIT.append(dict(_LAST_STATUS))
    if len(API_REQUEST_AUDIT) > 1000:
        del API_REQUEST_AUDIT[:250]


def _request_json(path: str) -> Optional[Any]:
    if not _api_key():
        _record(path, None, False, "MISSING_KEY")
        return None
    url = f"{BASE_URL}{path}"
    for attempt in range(2):
        _throttle()
        try:
            response = requests.get(url, headers=_headers(), timeout=TIMEOUT)
            status = int(response.status_code)
            if status == 429:
                _record(path, status, False, "RATE_LIMIT")
                if attempt == 0:
                    time.sleep(max(3.0, float(os.getenv("MARQ_RAPIDAPI_429_SLEEP_SECONDS", "10"))))
                    continue
                return None
            if status == 204:
                _record(path, status, False, "NO_CONTENT")
                return None
            if status >= 400:
                _record(path, status, False, "HTTP_ERROR")
                return None
            if not response.text or not response.text.strip():
                _record(path, status, False, "EMPTY_BODY")
                return None
            data = response.json()
            _record(path, status, True, "OK")
            return data
        except Exception as exc:
            _record(path, None, False, f"EXCEPTION:{exc}")
            return None
    return None


def _participant_slug(name: str) -> str:
    if name is None:
        return ""
    text = str(name).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def _get_event_id_once(participant1: str, participant2: str, date_only: str):
    p1 = quote(_participant_slug(participant1), safe="")
    p2 = quote(_participant_slug(participant2), safe="")
    path = f"/tennis/v2/extend/api/event/get/{p1}/{p2}/{date_only}"
    payload = _request_json(path)
    if not isinstance(payload, dict):
        return None
    result = payload.get("result", {})
    event_id = result.get("id") if isinstance(result, dict) else None
    return str(event_id) if event_id else None


def get_event_id(player1: str, player2: str, date_only: str):
    event_id = _get_event_id_once(player1, player2, date_only)
    if event_id:
        return event_id
    return _get_event_id_once(player2, player1, date_only)


def get_odds_summary(event_id: str):
    return _request_json(f"/tennis/v2/extend/api/odds/summary/{event_id}")


def get_recent_odds(event_id: str):
    return _request_json(f"/tennis/v2/extend/api/event/recent-odds/get/{event_id}")
