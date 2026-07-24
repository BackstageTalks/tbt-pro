"""THINQ H2H Loader.

H2H belongs to THINQ. This loader never raises during daily build.
It returns AVAILABLE, NO_DATA, or ERROR_NON_BLOCKING statuses.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import os
import re
import unicodedata

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

HOST = os.getenv("TENNISAPI_PRO_HOST", "tennisapi1.p.rapidapi.com")
BASE_URL = os.getenv("TENNISAPI_PRO_BASE_URL", "https://tennisapi1.p.rapidapi.com")


def norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def empty_h2h(reason: str = "No usable H2H events", status: str = "NO_DATA") -> Dict[str, Any]:
    return {
        "status": status,
        "source": "none",
        "total_matches": 0,
        "player1_wins": 0,
        "player2_wins": 0,
        "pick_wins": 0,
        "opponent_wins": 0,
        "edge": 0.0,
        "confidence": 0.0,
        "reason": reason,
        "flags": [status],
    }


def _api_headers() -> Optional[Dict[str, str]]:
    key = os.getenv("RAPIDAPI_KEY") or os.getenv("X_RAPIDAPI_KEY")
    if not key:
        return None
    return {"x-rapidapi-key": key, "x-rapidapi-host": HOST, "Content-Type": "application/json"}


def _try_event_api(event_id: Any) -> Optional[Dict[str, Any]]:
    if not event_id or requests is None:
        return None
    headers = _api_headers()
    if not headers:
        return None
    paths = [
        f"/api/tennis/event/{event_id}/h2h/events",
        f"/api/tennis/event/{event_id}/h2h/history",
        f"/api/tennis/event/{event_id}/head-to-head/history",
        f"/api/tennis/event/{event_id}/head-to-head",
        f"/api/tennis/event/{event_id}/h2h",
    ]
    for path in paths:
        try:
            url = f"{BASE_URL.rstrip('/')}{path}"
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code >= 400:
                continue
            payload = response.json()
            # Keep parsing conservative. If unknown shape, expose source but no edge.
            events = payload.get("events") or payload.get("data") or payload.get("matches")
            if isinstance(events, list) and events:
                return {"payload": payload, "endpoint": path, "events": events}
        except Exception:
            continue
    return None


def build_h2h_context(player1: str, player2: str, pick: Optional[str] = None, opponent: Optional[str] = None, surface: Optional[str] = None, event_id: Any = None, **kwargs) -> Dict[str, Any]:
    try:
        api = _try_event_api(event_id)
        if not api:
            return empty_h2h("No API H2H events returned")
        # We have events but do not assume complex winner schema yet.
        total = len(api.get("events") or [])
        if total <= 0:
            return empty_h2h("API H2H returned empty list")
        return {
            "status": "AVAILABLE",
            "source": "api_pro",
            "endpoint": api.get("endpoint"),
            "total_matches": total,
            "player1_wins": 0,
            "player2_wins": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "edge": 0.0,
            "confidence": min(0.25 + total * 0.08, 0.65),
            "reason": "API H2H events available; winner parsing conservative",
            "flags": ["H2H_API_EVENTS_AVAILABLE"],
        }
    except Exception as exc:
        out = empty_h2h(str(exc), status="ERROR_NON_BLOCKING")
        out["flags"] = ["H2H_ERROR_NON_BLOCKING"]
        return out


class H2HLoader:
    def load_h2h(self, player1: str, player2: str, **kwargs) -> Dict[str, Any]:
        return build_h2h_context(player1=player1, player2=player2, **kwargs)
