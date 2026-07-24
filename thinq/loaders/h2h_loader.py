"""THINQ H2H loader.

Broad implementation for runtime building:
- RapidAPI PRO first, if event_id is available
- local cache fallback
- never blocks CORQ if no H2H data exists
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from corq.name_match import names_match, normalize_name
except Exception:
    def normalize_name(value: Any) -> str:
        return str(value or "").strip().lower()
    def names_match(a: Any, b: Any, threshold: float = 0.78) -> bool:
        return normalize_name(a) == normalize_name(b)

CACHE_DIR = Path("data/h2h_cache")


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None


def rapidapi_host() -> str:
    return os.getenv("TENNISAPI_RAPIDAPI_HOST") or os.getenv("RAPIDAPI_HOST") or "tennisapi1.p.rapidapi.com"


def rapidapi_headers() -> Optional[Dict[str, str]]:
    key = os.getenv("RAPIDAPI_KEY")
    if not key:
        return None
    return {"x-rapidapi-key": key, "x-rapidapi-host": rapidapi_host()}


def cache_path(event_id: Any, player1: str, player2: str) -> Path:
    year = str(date.today().year)
    key = str(event_id or f"{normalize_name(player1)}__{normalize_name(player2)}").replace("/", "_")
    return CACHE_DIR / year / f"h2h_{key}.json"


def save_cache(path: Path, payload: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_cache(path: Path) -> Optional[Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def api_get_with_audit(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "endpoint": path,
        "params": params or {},
        "url_path": path,
        "ok": False,
        "status_code": None,
        "error": None,
        "payload": None,
    }
    if requests is None:
        audit["error"] = "requests_unavailable"
        return audit
    headers = rapidapi_headers()
    if not headers:
        audit["error"] = "missing_rapidapi_key"
        return audit
    url = f"https://{rapidapi_host()}{path}"
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=25)
        audit["status_code"] = resp.status_code
        if resp.status_code in (204, 404):
            audit["error"] = f"empty_status_{resp.status_code}"
            return audit
        resp.raise_for_status()
        if not resp.text:
            audit["error"] = "empty_response_text"
            return audit
        audit["payload"] = resp.json()
        audit["ok"] = True
        return audit
    except Exception as exc:
        audit["error"] = str(exc)
        return audit
    finally:
        time.sleep(0.10)


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    audit = api_get_with_audit(path, params=params)
    return audit.get("payload") if audit.get("ok") else None


def string_id(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def fetch_h2h_from_api(
    event_id: Any,
    player1_id: Any = None,
    player2_id: Any = None,
    event_custom_id: Any = None,
) -> Optional[Any]:
    event_id_int = as_int(event_id)
    custom_id = string_id(event_custom_id)
    event_id_text = string_id(event_id)
    if not custom_id and event_id_text and not event_id_text.isdigit():
        custom_id = event_id_text
    attempts: List[Any] = []

    # TennisApi PRO H2H history. RapidAPI docs/examples use the event customId
    # for this endpoint, e.g. /api/tennis/event/QCtsXrI/h2h.
    if custom_id:
        attempts.extend([
            (f"/api/tennis/event/{custom_id}/h2h", None),
            (f"/api/tennis/event/{custom_id}/head-to-head", None),
        ])

    # Numeric event id fallbacks. Some endpoints accept numeric match id.
    if event_id_int:
        attempts.extend([
            (f"/api/tennis/event/{event_id_int}/h2h", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head", None),
            (f"/api/tennis/event/{event_id_int}/h2h/summary", None),
            ("/api/tennis/getHeadToHeadHistory", {"eventId": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"eventId": event_id_int}),
        ])

    p1 = as_int(player1_id)
    p2 = as_int(player2_id)
    if p1 and p2:
        attempts.extend([
            (f"/api/tennis/head-to-head/{p1}/{p2}", None),
            (f"/api/tennis/team/{p1}/versus/{p2}/matches", None),
            (f"/api/tennis/player/{p1}/versus/{p2}/matches", None),
            ("/api/tennis/getHeadToHeadHistory", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadHistory", {"homeTeamId": p1, "awayTeamId": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"homeTeamId": p1, "awayTeamId": p2}),
        ])

    endpoint_attempts: List[Dict[str, Any]] = []
    for path, params in attempts:
        audit = api_get_with_audit(path, params=params)
        endpoint_attempts.append({
            "endpoint": audit.get("endpoint"),
            "params": audit.get("params"),
            "status_code": audit.get("status_code"),
            "ok": audit.get("ok"),
            "error": audit.get("error"),
        })
        payload = audit.get("payload")
        if payload:
            return {
                "endpoint": path,
                "params": params,
                "payload": payload,
                "endpoint_attempts": endpoint_attempts,
                "api_status_code": audit.get("status_code"),
                "api_error": audit.get("error"),
            }
    if endpoint_attempts:
        return {
            "endpoint": None,
            "params": None,
            "payload": None,
            "endpoint_attempts": endpoint_attempts,
            "api_status_code": endpoint_attempts[-1].get("status_code"),
            "api_error": endpoint_attempts[-1].get("error"),
        }
    return None


def extract_events(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and "payload" in payload:
        payload = payload.get("payload")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("events", "h2h", "matches", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        nested = payload.get("data")
        if isinstance(nested, dict):
            return extract_events(nested)
    return []


def player_name_from_event_side(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "fullName", "displayName", "shortName", "slug"):
            if value.get(key):
                return str(value.get(key))
    return str(value or "")


def winner_from_event(event: Dict[str, Any]) -> Optional[str]:
    winner = event.get("winner") or event.get("winnerTeam") or event.get("winner_team")
    if winner:
        return player_name_from_event_side(winner)
    code = event.get("winnerCode")
    home = player_name_from_event_side(event.get("homeTeam") or event.get("home") or event.get("player1"))
    away = player_name_from_event_side(event.get("awayTeam") or event.get("away") or event.get("player2"))
    try:
        code_int = int(code)
        if code_int == 1:
            return home
        if code_int == 2:
            return away
    except Exception:
        return None
    return None


def summarize_h2h(payload: Any, pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    events = extract_events(payload)
    total = 0
    pick_wins = 0
    opponent_wins = 0
    same_surface_total = 0
    same_surface_pick_wins = 0
    for event in events:
        winner = winner_from_event(event)
        if not winner:
            continue
        total += 1
        if names_match(winner, pick):
            pick_wins += 1
        elif names_match(winner, opponent):
            opponent_wins += 1
        raw_surface = str(event.get("surface") or event.get("groundType") or event.get("surfaceType") or "").lower()
        if surface and str(surface).lower() in raw_surface:
            same_surface_total += 1
            if names_match(winner, pick):
                same_surface_pick_wins += 1
    if total == 0:
        return {
            "status": "NO_DATA",
            "source": "none",
            "total_matches": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "edge": 0.0,
            "confidence": 0.0,
            "reason": "No API H2H events returned",
        }
    win_pct = pick_wins / total
    edge = max(min((win_pct - 0.5) * 0.08, 0.04), -0.04)
    confidence = min(0.15 + total * 0.08, 0.55)
    return {
        "status": "OK",
        "source": "rapidapi_pro_or_cache",
        "total_matches": total,
        "pick_wins": pick_wins,
        "opponent_wins": opponent_wins,
        "pick_win_pct": round(win_pct, 4),
        "same_surface_matches": same_surface_total,
        "same_surface_pick_wins": same_surface_pick_wins,
        "edge": round(edge, 4),
        "confidence": round(confidence, 4),
        "reason": None,
    }


def build_h2h_context(
    event_id: Any,
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    player1_id: Any = None,
    player2_id: Any = None,
    event_custom_id: Any = None,
) -> Dict[str, Any]:
    cache_key = event_custom_id or event_id
    path = cache_path(cache_key, pick, opponent)
    payload = load_cache(path)
    source = "cache"
    if payload is None:
        payload = fetch_h2h_from_api(event_id, player1_id=player1_id, player2_id=player2_id, event_custom_id=event_custom_id)
        source = "rapidapi_pro"
        if payload is not None:
            save_cache(path, payload)
    summary = summarize_h2h(payload, pick, opponent, surface=surface) if payload is not None else summarize_h2h(None, pick, opponent, surface=surface)
    if isinstance(payload, dict):
        summary["endpoint"] = payload.get("endpoint")
        summary["params"] = payload.get("params")
        summary["endpoint_attempts"] = payload.get("endpoint_attempts") or []
        summary["api_status_code"] = payload.get("api_status_code")
        summary["api_error"] = payload.get("api_error")
        if payload.get("payload") is None and summary.get("status") != "OK":
            summary["reason"] = payload.get("api_error") or summary.get("reason")
    summary["cache_path"] = str(path)
    summary["requested_event_id"] = as_int(event_id) or event_id
    summary["requested_event_custom_id"] = string_id(event_custom_id)
    summary["requested_player1_id"] = as_int(player1_id)
    summary["requested_player2_id"] = as_int(player2_id)
    if summary.get("status") == "OK":
        summary["source"] = source
    return summary
