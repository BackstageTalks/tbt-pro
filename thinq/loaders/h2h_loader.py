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


def normalize_surface_bucket(value: Any) -> Optional[str]:
    """Map API and project surface labels into one H2H bucket.

    Tennis API payloads are not consistent: surface can be a plain string,
    groundType.name, nested tournament.groundType or labels such as red clay.
    The H2H same-surface calculation must compare buckets, not raw strings.
    """
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        for key in ("name", "slug", "type", "value", "displayName", "surface", "groundType"):
            bucket = normalize_surface_bucket(value.get(key))
            if bucket:
                return bucket
        return None
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = text.replace("_", " ").replace("-", " ")
    clay_terms = ("clay", "red clay", "green clay", "terre battue", "antuka", "har tru", "hartru")
    grass_terms = ("grass", "lawn")
    hard_terms = ("hard", "hardcourt", "hard court", "indoor hard", "outdoor hard", "carpet")
    if any(term in text for term in clay_terms):
        return "Clay"
    if any(term in text for term in grass_terms):
        return "Grass"
    if any(term in text for term in hard_terms):
        return "Hard"
    return None


def _surface_candidates(obj: Any, depth: int = 0) -> List[Any]:
    if depth > 4:
        return []
    out: List[Any] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_norm = str(key).lower().replace("_", "").replace("-", "")
            if key_norm in {"surface", "surfacetype", "ground", "groundtype", "courttype", "court", "surfaceinfo"}:
                out.append(value)
            if isinstance(value, (dict, list)):
                out.extend(_surface_candidates(value, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_surface_candidates(item, depth + 1))
    return out


def event_surface_bucket(event: Dict[str, Any]) -> Optional[str]:
    # First check common top-level fields, then scan nested tournament/venue data.
    direct = [
        event.get("surface"),
        event.get("groundType"),
        event.get("surfaceType"),
        event.get("courtType"),
        event.get("court"),
    ]
    for value in direct + _surface_candidates(event):
        bucket = normalize_surface_bucket(value)
        if bucket:
            return bucket
    return None


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
    # If customId is available, keep H2H lightweight and do not fan out to
    # numeric/player/team fallbacks. Those extra calls produced mostly 404/429.
    if custom_id:
        attempts.extend([
            (f"/api/tennis/event/{custom_id}/h2h", None),
            (f"/api/tennis/event/{custom_id}/head-to-head", None),
        ])

    # Numeric event id fallbacks only when customId is not available.
    if event_id_int and not custom_id:
        attempts.extend([
            (f"/api/tennis/event/{event_id_int}/h2h", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head", None),
            (f"/api/tennis/event/{event_id_int}/h2h/summary", None),
            ("/api/tennis/getHeadToHeadHistory", {"eventId": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"eventId": event_id_int}),
        ])

    p1 = as_int(player1_id)
    p2 = as_int(player2_id)
    if p1 and p2 and not custom_id:
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



def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def h2h_sample_cap(total_matches: int) -> float:
    """Maximum directional H2H edge allowed by sample size.

    H2H has high narrative value but can easily overfit on 1-2 meetings.
    This cap prevents one historical match from moving CorQ like a strong model layer.
    Returned value is probability-point scale, e.g. 0.015 = 1.5pp.
    """
    try:
        total = int(total_matches or 0)
    except Exception:
        total = 0
    if total <= 0:
        return 0.0
    if total == 1:
        return 0.015
    if total <= 3:
        return 0.025
    return 0.040


def h2h_sample_quality(total_matches: int, confidence: float) -> str:
    try:
        total = int(total_matches or 0)
    except Exception:
        total = 0
    try:
        conf = float(confidence or 0.0)
    except Exception:
        conf = 0.0
    if total <= 0:
        return "NO_SAMPLE"
    if total == 1:
        return "LOW_SAMPLE"
    if total <= 3:
        return "MEDIUM_SAMPLE"
    if conf >= 0.45:
        return "GOOD_SAMPLE"
    return "MEDIUM_SAMPLE"


def effective_h2h_edge(raw_edge: float, total_matches: int, confidence: float) -> float:
    """Shrink raw H2H edge by sample quality and confidence.

    Example: a 1-0 H2H can still support a pick, but it is capped at +/-1.5pp,
    not the old +/-4.0pp maximum.
    """
    try:
        raw = float(raw_edge or 0.0)
    except Exception:
        raw = 0.0
    try:
        conf = float(confidence or 0.0)
    except Exception:
        conf = 0.0
    cap = h2h_sample_cap(total_matches)
    if cap <= 0.0:
        return 0.0
    # Confidence max in this loader is 0.55. Use it as a smooth shrink factor,
    # then never allow the value to exceed the sample cap.
    conf_factor = _clamp(conf / 0.55, 0.20, 1.0)
    return round(_clamp(raw * conf_factor, -cap, cap), 4)


def summarize_h2h(payload: Any, pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    events = extract_events(payload)
    requested_surface = normalize_surface_bucket(surface)
    total = 0
    pick_wins = 0
    opponent_wins = 0
    same_surface_total = 0
    same_surface_pick_wins = 0
    same_surface_opponent_wins = 0
    missing_surface_matches = 0
    detected_surface_buckets: List[str] = []

    for event in events:
        winner = winner_from_event(event)
        if not winner:
            continue
        total += 1
        pick_won = names_match(winner, pick)
        opponent_won = names_match(winner, opponent)
        if pick_won:
            pick_wins += 1
        elif opponent_won:
            opponent_wins += 1

        event_bucket = event_surface_bucket(event)
        if event_bucket:
            detected_surface_buckets.append(event_bucket)
        else:
            missing_surface_matches += 1

        if requested_surface and event_bucket == requested_surface:
            same_surface_total += 1
            if pick_won:
                same_surface_pick_wins += 1
            elif opponent_won:
                same_surface_opponent_wins += 1

    if total == 0:
        return {
            "status": "NO_DATA",
            "source": "none",
            "total_matches": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "same_surface_matches": 0,
            "same_surface_pick_wins": 0,
            "same_surface_opponent_wins": 0,
            "h2h_requested_surface": surface,
            "h2h_requested_surface_bucket": requested_surface,
            "h2h_missing_surface_matches": 0,
            "raw_edge": 0.0,
            "effective_edge": 0.0,
            "edge": 0.0,
            "sample_cap": 0.0,
            "sample_quality": "NO_SAMPLE",
            "confidence": 0.0,
            "reason": "No API H2H events returned",
        }

    win_pct = pick_wins / total
    raw_edge = max(min((win_pct - 0.5) * 0.08, 0.04), -0.04)
    confidence = min(0.15 + total * 0.08, 0.55)
    edge = effective_h2h_edge(raw_edge, total, confidence)
    surface_win_pct = (same_surface_pick_wins / same_surface_total) if same_surface_total else None
    raw_surface_edge = max(min(((surface_win_pct or 0.5) - 0.5) * 0.08, 0.04), -0.04) if surface_win_pct is not None else 0.0
    surface_confidence = min(0.15 + same_surface_total * 0.08, 0.55) if same_surface_total else 0.0
    surface_edge = effective_h2h_edge(raw_surface_edge, same_surface_total, surface_confidence) if surface_win_pct is not None else 0.0
    quality = h2h_sample_quality(total, confidence)
    surface_quality = h2h_sample_quality(same_surface_total, surface_confidence)
    return {
        "status": "OK",
        "source": "rapidapi_pro_or_cache",
        "total_matches": total,
        "pick_wins": pick_wins,
        "opponent_wins": opponent_wins,
        "pick_win_pct": round(win_pct, 4),
        "same_surface_matches": same_surface_total,
        "same_surface_pick_wins": same_surface_pick_wins,
        "same_surface_opponent_wins": same_surface_opponent_wins,
        "same_surface_pick_win_pct": round(surface_win_pct, 4) if surface_win_pct is not None else None,
        "same_surface_raw_edge": round(raw_surface_edge, 4),
        "same_surface_effective_edge": round(surface_edge, 4),
        "same_surface_edge": round(surface_edge, 4),
        "same_surface_sample_quality": surface_quality,
        "h2h_requested_surface": surface,
        "h2h_requested_surface_bucket": requested_surface,
        "h2h_detected_surface_buckets": sorted(set(detected_surface_buckets)),
        "h2h_missing_surface_matches": missing_surface_matches,
        "raw_edge": round(raw_edge, 4),
        "effective_edge": round(edge, 4),
        "edge": round(edge, 4),
        "sample_cap": round(h2h_sample_cap(total), 4),
        "sample_quality": quality,
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

# ---------------------------------------------------------------------------
# Robust runtime override: RapidAPI H2H history + summary fallback
# ---------------------------------------------------------------------------
# Kept at the end so older function bodies stay available, but runtime imports
# use these safer definitions. Primary endpoint remains event/{customId}/h2h.

_H2H_ROBUST_OVERRIDE_VERSION = "2026-08-01-h2h-history-summary-fallback"


def _h2h_find_summary_counts(payload: Any) -> Optional[Dict[str, int]]:
    """Find homeWins/awayWins style counts in a nested RapidAPI response."""
    if isinstance(payload, dict) and "payload" in payload:
        payload = payload.get("payload")
    if not isinstance(payload, dict):
        return None
    stack = [payload]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        hw = current.get("homeWins")
        aw = current.get("awayWins")
        if hw is not None and aw is not None:
            try:
                return {"homeWins": int(hw or 0), "awayWins": int(aw or 0)}
            except Exception:
                pass
        for value in current.values():
            if isinstance(value, dict):
                stack.append(value)
    return None


def fetch_h2h_from_api(
    event_id: Any,
    player1_id: Any = None,
    player2_id: Any = None,
    event_custom_id: Any = None,
) -> Optional[Any]:
    """Fetch H2H with strict primary endpoint and auditable fallbacks.

    Order:
    1. /api/tennis/event/{customId}/h2h where available.
    2. numeric event h2h/history/summary endpoints.
    3. player/team pair history/summary endpoints when ids are available.

    Summary-only responses are kept, but summarize_h2h() only uses them when
    the endpoint is an explicit HeadToHeadSummary fallback, so event-order
    ambiguity cannot silently contaminate pick/opponent orientation.
    """
    custom_id = string_id(event_custom_id)
    event_id_text = string_id(event_id)
    event_id_int = as_int(event_id)
    if not custom_id and event_id_text and not event_id_text.isdigit():
        custom_id = event_id_text
    p1 = as_int(player1_id)
    p2 = as_int(player2_id)

    attempts: List[Any] = []
    if custom_id:
        attempts.extend([
            (f"/api/tennis/event/{custom_id}/h2h", None),
            (f"/api/tennis/event/{custom_id}/head-to-head", None),
        ])
    if event_id_int:
        attempts.extend([
            (f"/api/tennis/event/{event_id_int}/h2h", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head", None),
            ("/api/tennis/getHeadToHeadHistory", {"id": event_id_int}),
            ("/api/tennis/getHeadToHeadHistory", {"eventId": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"id": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"eventId": event_id_int}),
        ])
    if p1 and p2:
        attempts.extend([
            (f"/api/tennis/head-to-head/{p1}/{p2}", None),
            (f"/api/tennis/team/{p1}/versus/{p2}/matches", None),
            (f"/api/tennis/player/{p1}/versus/{p2}/matches", None),
            ("/api/tennis/getHeadToHeadHistory", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadHistory", {"homeTeamId": p1, "awayTeamId": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"homeTeamId": p1, "awayTeamId": p2}),
            # Some RapidAPI screens label path param as id. Keep this as final fallback.
            ("/api/tennis/getHeadToHeadHistory", {"id": p1, "secondId": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"id": p1, "secondId": p2}),
        ])

    endpoint_attempts: List[Dict[str, Any]] = []
    seen = set()
    for path, params in attempts:
        sig = (path, json.dumps(params or {}, sort_keys=True))
        if sig in seen:
            continue
        seen.add(sig)
        audit = api_get_with_audit(path, params=params)
        endpoint_attempts.append({
            "endpoint": audit.get("endpoint"),
            "params": audit.get("params"),
            "status_code": audit.get("status_code"),
            "ok": audit.get("ok"),
            "error": audit.get("error"),
        })
        raw = audit.get("payload")
        events = extract_events(raw)
        summary = _h2h_find_summary_counts(raw)
        if raw and (events or summary):
            return {
                "endpoint": path,
                "params": params,
                "payload": raw,
                "endpoint_attempts": endpoint_attempts,
                "api_status_code": audit.get("status_code"),
                "api_error": audit.get("error"),
                "h2h_fetch_version": _H2H_ROBUST_OVERRIDE_VERSION,
                "h2h_payload_event_count": len(events),
                "h2h_payload_has_summary": bool(summary),
            }
    if endpoint_attempts:
        return {
            "endpoint": None,
            "params": None,
            "payload": None,
            "endpoint_attempts": endpoint_attempts,
            "api_status_code": endpoint_attempts[-1].get("status_code"),
            "api_error": endpoint_attempts[-1].get("error"),
            "h2h_fetch_version": _H2H_ROBUST_OVERRIDE_VERSION,
        }
    return None


_previous_summarize_h2h = summarize_h2h


def summarize_h2h(payload: Any, pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    summary = _previous_summarize_h2h(payload, pick, opponent, surface=surface)
    if summary.get("status") == "OK":
        summary.setdefault("h2h_summary_source", "events")
        return summary

    # If history events are missing but explicit HeadToHeadSummary returned
    # homeWins/awayWins using player1/player2 params, use it as total-H2H only.
    endpoint = ""
    params = None
    if isinstance(payload, dict):
        endpoint = str(payload.get("endpoint") or "")
        params = payload.get("params")
    counts = _h2h_find_summary_counts(payload)
    params_text = json.dumps(params or {}, sort_keys=True)
    safe_summary_endpoint = "getHeadToHeadSummary" in endpoint and any(
        key in params_text for key in ("player1Id", "homeTeamId", "secondId")
    )
    if not counts or not safe_summary_endpoint:
        summary["h2h_summary_source"] = "none"
        summary["h2h_summary_usable"] = False
        return summary

    pick_wins = int(counts.get("homeWins") or 0)
    opponent_wins = int(counts.get("awayWins") or 0)
    total = pick_wins + opponent_wins
    if total <= 0:
        return summary
    win_pct = pick_wins / total
    raw_edge = max(min((win_pct - 0.5) * 0.08, 0.04), -0.04)
    confidence = min(0.12 + total * 0.06, 0.42)
    edge = effective_h2h_edge(raw_edge, total, confidence)
    return {
        "status": "OK",
        "source": "rapidapi_pro_summary",
        "h2h_summary_source": "getHeadToHeadSummary",
        "h2h_summary_usable": True,
        "h2h_orientation": "homeWins_as_pick_from_player_params",
        "total_matches": total,
        "pick_wins": pick_wins,
        "opponent_wins": opponent_wins,
        "pick_win_pct": round(win_pct, 4),
        "same_surface_matches": 0,
        "same_surface_pick_wins": 0,
        "same_surface_opponent_wins": 0,
        "same_surface_pick_win_pct": None,
        "same_surface_raw_edge": 0.0,
        "same_surface_effective_edge": 0.0,
        "same_surface_edge": 0.0,
        "same_surface_sample_quality": "NO_SAMPLE",
        "h2h_requested_surface": surface,
        "h2h_requested_surface_bucket": normalize_surface_bucket(surface),
        "h2h_detected_surface_buckets": [],
        "h2h_missing_surface_matches": 0,
        "raw_edge": round(raw_edge, 4),
        "effective_edge": round(edge, 4),
        "edge": round(edge, 4),
        "sample_cap": round(h2h_sample_cap(total), 4),
        "sample_quality": h2h_sample_quality(total, confidence),
        "confidence": round(confidence, 4),
        "reason": None,
        "warning": "Summary-only H2H cannot calculate same-surface H2H.",
    }

# ---------------------------------------------------------------------------
# Final robust override: explicit RapidAPI H2H history/summary event endpoints
# ---------------------------------------------------------------------------
# Adds the endpoint shapes visible in RapidAPI Playground:
# - /api/tennis/event/{customId}/h2h
# - /api/tennis/event/{customId}/h2h/history
# - /api/tennis/event/{customId}/h2h/summary
# Summary-only payloads are used only when orientation can be proven from
# player params or event home/away names.

_H2H_FINAL_ENDPOINT_VERSION = "2026-08-01-h2h-event-history-summary-final"


def _h2h_team_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "shortName", "fullName", "displayName", "slug"):
            if value.get(key):
                return str(value.get(key))
    return str(value or "")


def _h2h_find_event_side_names(payload: Any) -> Dict[str, str]:
    """Find current event home/away names in a nested H2H summary response."""
    if isinstance(payload, dict) and "payload" in payload:
        payload = payload.get("payload")
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            home = current.get("homeTeam") or current.get("home") or current.get("player1")
            away = current.get("awayTeam") or current.get("away") or current.get("player2")
            home_name = _h2h_team_name(home)
            away_name = _h2h_team_name(away)
            if home_name and away_name:
                return {"home": home_name, "away": away_name}
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)
    return {"home": "", "away": ""}


def _h2h_orient_summary_counts(payload: Any, pick: str, opponent: str, params: Any = None) -> Optional[Dict[str, Any]]:
    counts = _h2h_find_summary_counts(payload)
    if not counts:
        return None
    home_wins = int(counts.get("homeWins") or 0)
    away_wins = int(counts.get("awayWins") or 0)

    # Player-param fallbacks were built with home/player1 as pick and away/player2 as opponent.
    params_text = json.dumps(params or {}, sort_keys=True)
    if any(key in params_text for key in ("player1Id", "homeTeamId", "secondId")):
        return {
            "pick_wins": home_wins,
            "opponent_wins": away_wins,
            "orientation": "homeWins_as_pick_from_player_params",
        }

    # Event-summary fallbacks can be used if response exposes current event home/away names.
    sides = _h2h_find_event_side_names(payload)
    home_name = sides.get("home") or ""
    away_name = sides.get("away") or ""
    if home_name and away_name:
        if names_match(pick, home_name) and names_match(opponent, away_name):
            return {"pick_wins": home_wins, "opponent_wins": away_wins, "orientation": "homeWins_as_pick_from_event_home"}
        if names_match(pick, away_name) and names_match(opponent, home_name):
            return {"pick_wins": away_wins, "opponent_wins": home_wins, "orientation": "awayWins_as_pick_from_event_away"}
    return None


def fetch_h2h_from_api(
    event_id: Any,
    player1_id: Any = None,
    player2_id: Any = None,
    event_custom_id: Any = None,
) -> Optional[Any]:
    custom_id = string_id(event_custom_id)
    event_id_text = string_id(event_id)
    event_id_int = as_int(event_id)
    if not custom_id and event_id_text and not event_id_text.isdigit():
        custom_id = event_id_text
    p1 = as_int(player1_id)
    p2 = as_int(player2_id)

    attempts: List[Any] = []
    if custom_id:
        attempts.extend([
            (f"/api/tennis/event/{custom_id}/h2h", None),
            (f"/api/tennis/event/{custom_id}/h2h/history", None),
            (f"/api/tennis/event/{custom_id}/h2h/summary", None),
            (f"/api/tennis/event/{custom_id}/head-to-head", None),
            (f"/api/tennis/event/{custom_id}/head-to-head/history", None),
            (f"/api/tennis/event/{custom_id}/head-to-head/summary", None),
        ])
    if event_id_int:
        attempts.extend([
            (f"/api/tennis/event/{event_id_int}/h2h", None),
            (f"/api/tennis/event/{event_id_int}/h2h/history", None),
            (f"/api/tennis/event/{event_id_int}/h2h/summary", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head/history", None),
            (f"/api/tennis/event/{event_id_int}/head-to-head/summary", None),
            ("/api/tennis/getHeadToHeadHistory", {"id": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"id": event_id_int}),
            ("/api/tennis/getHeadToHeadHistory", {"eventId": event_id_int}),
            ("/api/tennis/getHeadToHeadSummary", {"eventId": event_id_int}),
        ])
    if p1 and p2:
        attempts.extend([
            ("/api/tennis/getHeadToHeadHistory", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"player1Id": p1, "player2Id": p2}),
            ("/api/tennis/getHeadToHeadHistory", {"homeTeamId": p1, "awayTeamId": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"homeTeamId": p1, "awayTeamId": p2}),
            ("/api/tennis/getHeadToHeadHistory", {"id": p1, "secondId": p2}),
            ("/api/tennis/getHeadToHeadSummary", {"id": p1, "secondId": p2}),
            (f"/api/tennis/head-to-head/{p1}/{p2}", None),
            (f"/api/tennis/team/{p1}/versus/{p2}/matches", None),
            (f"/api/tennis/player/{p1}/versus/{p2}/matches", None),
        ])

    endpoint_attempts: List[Dict[str, Any]] = []
    seen = set()
    for path, params in attempts:
        sig = (path, json.dumps(params or {}, sort_keys=True))
        if sig in seen:
            continue
        seen.add(sig)
        audit = api_get_with_audit(path, params=params)
        endpoint_attempts.append({
            "endpoint": audit.get("endpoint"),
            "params": audit.get("params"),
            "status_code": audit.get("status_code"),
            "ok": audit.get("ok"),
            "error": audit.get("error"),
        })
        raw = audit.get("payload")
        events = extract_events(raw)
        summary = _h2h_find_summary_counts(raw)
        if raw and (events or summary):
            return {
                "endpoint": path,
                "params": params,
                "payload": raw,
                "endpoint_attempts": endpoint_attempts,
                "api_status_code": audit.get("status_code"),
                "api_error": audit.get("error"),
                "h2h_fetch_version": _H2H_FINAL_ENDPOINT_VERSION,
                "h2h_payload_event_count": len(events),
                "h2h_payload_has_summary": bool(summary),
            }
    return {
        "endpoint": None,
        "params": None,
        "payload": None,
        "endpoint_attempts": endpoint_attempts,
        "api_status_code": endpoint_attempts[-1].get("status_code") if endpoint_attempts else None,
        "api_error": endpoint_attempts[-1].get("error") if endpoint_attempts else "no_h2h_attempts",
        "h2h_fetch_version": _H2H_FINAL_ENDPOINT_VERSION,
    }


_h2h_previous_summary_final = summarize_h2h


def summarize_h2h(payload: Any, pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    summary = _h2h_previous_summary_final(payload, pick, opponent, surface=surface)
    if summary.get("status") == "OK":
        summary.setdefault("h2h_summary_source", "events")
        return summary

    endpoint = ""
    params = None
    raw_payload = payload
    if isinstance(payload, dict):
        endpoint = str(payload.get("endpoint") or "")
        params = payload.get("params")
        raw_payload = payload.get("payload", payload)

    orientation = _h2h_orient_summary_counts(raw_payload, pick, opponent, params=params)
    if not orientation:
        summary["h2h_summary_source"] = "summary_unusable_orientation_unknown"
        summary["h2h_summary_usable"] = False
        return summary

    pick_wins = int(orientation.get("pick_wins") or 0)
    opponent_wins = int(orientation.get("opponent_wins") or 0)
    total = pick_wins + opponent_wins
    if total <= 0:
        return summary

    win_pct = pick_wins / total
    raw_edge = max(min((win_pct - 0.5) * 0.08, 0.04), -0.04)
    confidence = min(0.12 + total * 0.06, 0.42)
    edge = effective_h2h_edge(raw_edge, total, confidence)
    return {
        "status": "OK",
        "source": "rapidapi_pro_summary",
        "h2h_summary_source": endpoint or "HeadToHeadSummary",
        "h2h_summary_usable": True,
        "h2h_orientation": orientation.get("orientation"),
        "total_matches": total,
        "pick_wins": pick_wins,
        "opponent_wins": opponent_wins,
        "pick_win_pct": round(win_pct, 4),
        "same_surface_matches": 0,
        "same_surface_pick_wins": 0,
        "same_surface_opponent_wins": 0,
        "same_surface_pick_win_pct": None,
        "same_surface_raw_edge": 0.0,
        "same_surface_effective_edge": 0.0,
        "same_surface_edge": 0.0,
        "same_surface_sample_quality": "NO_SAMPLE",
        "h2h_requested_surface": surface,
        "h2h_requested_surface_bucket": normalize_surface_bucket(surface),
        "h2h_detected_surface_buckets": [],
        "h2h_missing_surface_matches": 0,
        "raw_edge": round(raw_edge, 4),
        "effective_edge": round(edge, 4),
        "edge": round(edge, 4),
        "sample_cap": round(h2h_sample_cap(total), 4),
        "sample_quality": h2h_sample_quality(total, confidence),
        "confidence": round(confidence, 4),
        "reason": None,
        "warning": "Summary-only H2H cannot calculate same-surface H2H.",
    }
