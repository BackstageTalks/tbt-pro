"""THINQ H2H loader using TennisAPI PRO customId endpoint with lazy JSON cache.

Policy:
- TennisAPI PRO is the only external H2H source.
- Primary endpoint: /api/tennis/event/{customId}/h2h.
- Cache lives under thinq/data/h2h/ so H2H data is organized with ThinQ data.
- Missing data returns NO_DATA and never fabricates values.
- Cached API data can be used if the API is temporarily unavailable.

Runtime orientation:
- build_h2h_context receives pick/opponent and side-aware player IDs from
  thinq.service.
- H2H wins are oriented to pick -> opponent.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    from corq.name_match import names_match, normalize_name
except Exception:  # pragma: no cover
    def normalize_name(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    def names_match(a: Any, b: Any, threshold: float = 0.78) -> bool:
        return normalize_name(a) == normalize_name(b)


CACHE_DIR = Path("thinq/data/h2h")
CACHE_PATH = CACHE_DIR / "h2h_cache.json"
LAST_REFRESH_PATH = CACHE_DIR / "h2h_last_refresh.json"
CACHE_VERSION = "TENNISAPI_PRO_H2H_LAZY_CACHE_V1"
DEFAULT_CACHE_TTL_DAYS = int(os.getenv("H2H_CACHE_TTL_DAYS", "14"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("H2H_REQUEST_TIMEOUT_SECONDS", "25"))
REQUEST_DELAY_SECONDS = float(os.getenv("H2H_REQUEST_DELAY_SECONDS", "0.10"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-", "N/A"):
            return None
        return float(value)
    except Exception:
        return None


def string_id(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def compact_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def rapidapi_host() -> str:
    return os.getenv("TENNISAPI_RAPIDAPI_HOST") or os.getenv("RAPIDAPI_HOST") or "tennisapi1.p.rapidapi.com"


def rapidapi_headers() -> Optional[Dict[str, str]]:
    key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not key:
        return None
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": rapidapi_host(),
        "Content-Type": "application/json",
    }


def normalize_surface_bucket(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        for key in ("name", "slug", "type", "value", "displayName", "surface", "groundType"):
            bucket = normalize_surface_bucket(value.get(key))
            if bucket:
                return bucket
        return None
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if not text:
        return None
    if any(term in text for term in ("clay", "red clay", "green clay", "terre battue", "har tru", "hartru")):
        return "Clay"
    if any(term in text for term in ("grass", "lawn")):
        return "Grass"
    if any(term in text for term in ("hard", "hardcourt", "hard court", "indoor", "carpet")):
        return "Hard"
    return None


def _nested_get(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _team_name(team: Any) -> str:
    if isinstance(team, dict):
        for key in ("name", "fullName", "displayName", "shortName", "slug"):
            if team.get(key):
                return str(team.get(key))
    return str(team or "")


def _team_id(team: Any) -> Optional[int]:
    if not isinstance(team, dict):
        return None
    for key in ("id", "teamId", "playerId"):
        value = as_int(team.get(key))
        if value is not None:
            return value
    value = as_int(_nested_get(team, "playerTeamInfo", "id"))
    if value is not None:
        return value
    return None


def _score_string(event: Dict[str, Any]) -> str:
    home_score = event.get("homeScore") if isinstance(event.get("homeScore"), dict) else {}
    away_score = event.get("awayScore") if isinstance(event.get("awayScore"), dict) else {}
    parts: List[str] = []
    for idx in range(1, 6):
        hp = home_score.get(f"period{idx}")
        ap = away_score.get(f"period{idx}")
        if hp in (None, "") or ap in (None, ""):
            continue
        ht = home_score.get(f"period{idx}TieBreak")
        at = away_score.get(f"period{idx}TieBreak")
        tb = ""
        if ht not in (None, "") or at not in (None, ""):
            tb = f"({ht or 0}-{at or 0})"
        parts.append(f"{hp}-{ap}{tb}")
    return " ".join(parts)


def _event_date_from_timestamp(value: Any) -> Optional[str]:
    try:
        ts = int(value)
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except Exception:
        return None


def normalize_h2h_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(event, dict):
        return None

    home = event.get("homeTeam") or event.get("home") or event.get("player1")
    away = event.get("awayTeam") or event.get("away") or event.get("player2")
    home_name = _team_name(home)
    away_name = _team_name(away)
    home_id = _team_id(home)
    away_id = _team_id(away)
    winner_code = as_int(event.get("winnerCode"))

    winner_side = None
    winner_name = ""
    winner_id = None
    if winner_code == 1:
        winner_side = "HOME"
        winner_name = home_name
        winner_id = home_id
    elif winner_code == 2:
        winner_side = "AWAY"
        winner_name = away_name
        winner_id = away_id
    else:
        winner = event.get("winner") or event.get("winnerTeam") or event.get("winner_team")
        winner_name = _team_name(winner)
        winner_id = _team_id(winner)
        if winner_id is not None and winner_id == home_id:
            winner_side = "HOME"
        elif winner_id is not None and winner_id == away_id:
            winner_side = "AWAY"
        elif winner_name and names_match(winner_name, home_name):
            winner_side = "HOME"
            winner_id = home_id
        elif winner_name and names_match(winner_name, away_name):
            winner_side = "AWAY"
            winner_id = away_id

    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    category = tournament.get("category") if isinstance(tournament.get("category"), dict) else {}
    unique_tournament = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}

    surface_raw = event.get("groundType") or tournament.get("groundType") or unique_tournament.get("groundType")
    surface_bucket = normalize_surface_bucket(surface_raw)

    return {
        "event_id": event.get("id"),
        "custom_id": event.get("customId") or event.get("custom_id"),
        "date": _event_date_from_timestamp(event.get("startTimestamp")),
        "start_timestamp": event.get("startTimestamp"),
        "tournament": tournament.get("name") or unique_tournament.get("name"),
        "category": category.get("name"),
        "round": _nested_get(event, "roundInfo", "name") or _nested_get(event, "roundInfo", "round"),
        "surface": surface_bucket,
        "surface_raw": surface_raw,
        "home_name": home_name,
        "away_name": away_name,
        "home_id": home_id,
        "away_id": away_id,
        "winner_side": winner_side,
        "winner_name": winner_name,
        "winner_id": winner_id,
        "winner_code": winner_code,
        "status_type": status.get("type"),
        "status_description": status.get("description"),
        "score": _score_string(event),
    }


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


def normalize_events(payload: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in extract_events(payload):
        item = normalize_h2h_event(event)
        if item:
            out.append(item)
    return out


def h2h_event_key(event: Dict[str, Any]) -> str:
    event_id = event.get("event_id")
    if event_id not in (None, ""):
        return f"event:{event_id}"
    parts = [
        str(event.get("date") or ""),
        str(event.get("home_id") or event.get("home_name") or ""),
        str(event.get("away_id") or event.get("away_name") or ""),
        str(event.get("score") or ""),
    ]
    return "fallback:" + "|".join(parts)


def merge_h2h_events(existing: Any, new_events: Any) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for source in (existing, new_events):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            key = h2h_event_key(item)
            if key in merged:
                updated = dict(merged[key])
                updated.update({k: v for k, v in item.items() if v not in (None, "")})
                merged[key] = updated
            else:
                merged[key] = dict(item)

    def sort_key(item: Dict[str, Any]) -> tuple:
        ts = as_int(item.get("start_timestamp")) or 0
        ev = str(item.get("event_id") or "")
        return (-ts, ev)

    return sorted(merged.values(), key=sort_key)


def _empty_cache() -> Dict[str, Any]:
    return {
        "version": CACHE_VERSION,
        "source": "TENNISAPI_PRO_H2H",
        "generated_at": now_iso(),
        "updated_at": now_iso(),
        "pairs": {},
    }


def load_h2h_cache() -> Dict[str, Any]:
    try:
        if CACHE_PATH.exists():
            payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("version", CACHE_VERSION)
                payload.setdefault("source", "TENNISAPI_PRO_H2H")
                payload.setdefault("pairs", {})
                return payload
    except Exception:
        pass
    return _empty_cache()


def save_h2h_cache(cache: Dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache["updated_at"] = now_iso()
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_last_refresh(meta: Dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_REFRESH_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def cache_key(event_custom_id: Any, event_id: Any, player1_id: Any, player2_id: Any, pick: str, opponent: str) -> str:
    custom_id = string_id(event_custom_id)
    if custom_id:
        return f"custom:{custom_id}"
    event_text = string_id(event_id)
    if event_text and not event_text.isdigit():
        return f"custom:{event_text}"
    p1 = as_int(player1_id)
    p2 = as_int(player2_id)
    if p1 is not None and p2 is not None:
        left, right = sorted([p1, p2])
        return f"teamids:{left}|{right}"
    names = sorted([compact_text(pick), compact_text(opponent)])
    return f"names:{names[0]}|{names[1]}"


def parse_iso_dt(value: Any) -> Optional[datetime]:
    try:
        text = str(value or "").replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def cache_entry_is_fresh(entry: Dict[str, Any], ttl_days: int = DEFAULT_CACHE_TTL_DAYS) -> bool:
    if not isinstance(entry, dict):
        return False
    updated = parse_iso_dt(entry.get("updated_at"))
    if updated is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - updated).total_seconds()
    return age_seconds <= max(ttl_days, 0) * 86400


def api_get_with_audit(path: str) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "endpoint": path,
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
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        audit["status_code"] = response.status_code
        if response.status_code in (204, 404):
            audit["error"] = f"empty_status_{response.status_code}"
            return audit
        response.raise_for_status()
        if not response.text:
            audit["error"] = "empty_response_text"
            return audit
        audit["payload"] = response.json()
        audit["ok"] = True
        return audit
    except Exception as exc:
        audit["error"] = str(exc)
        return audit
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)


def fetch_h2h_from_api(event_custom_id: Any) -> Dict[str, Any]:
    custom_id = string_id(event_custom_id)
    if not custom_id:
        return {
            "endpoint": None,
            "payload": None,
            "normalized_events": [],
            "endpoint_attempts": [],
            "api_status_code": None,
            "api_error": "missing_custom_id",
            "h2h_fetch_version": CACHE_VERSION,
        }

    path = f"/api/tennis/event/{custom_id}/h2h"
    audit = api_get_with_audit(path)
    attempts = [{
        "endpoint": audit.get("endpoint"),
        "status_code": audit.get("status_code"),
        "ok": audit.get("ok"),
        "error": audit.get("error"),
    }]
    payload = audit.get("payload") if audit.get("ok") else None
    normalized = normalize_events(payload) if payload is not None else []
    return {
        "endpoint": path,
        "payload": payload,
        "normalized_events": normalized,
        "endpoint_attempts": attempts,
        "api_status_code": audit.get("status_code"),
        "api_error": audit.get("error"),
        "h2h_fetch_version": CACHE_VERSION,
        "h2h_payload_event_count": len(normalized),
    }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def h2h_sample_cap(total_matches: int) -> float:
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
    conf_factor = _clamp(conf / 0.55, 0.20, 1.0)
    return round(_clamp(raw * conf_factor, -cap, cap), 4)


def _winner_matches_player(event: Dict[str, Any], player_id: Optional[int], player_name: str) -> bool:
    winner_id = as_int(event.get("winner_id"))
    if player_id is not None and winner_id is not None:
        return winner_id == player_id
    winner_name = event.get("winner_name")
    return bool(winner_name and names_match(winner_name, player_name))


def summarize_h2h_events(
    events: List[Dict[str, Any]],
    pick: str,
    opponent: str,
    surface: Optional[str] = None,
    pick_player_id: Any = None,
    opponent_player_id: Any = None,
) -> Dict[str, Any]:
    requested_surface = normalize_surface_bucket(surface)
    pick_id = as_int(pick_player_id)
    opponent_id = as_int(opponent_player_id)

    total = 0
    pick_wins = 0
    opponent_wins = 0
    same_surface_total = 0
    same_surface_pick_wins = 0
    same_surface_opponent_wins = 0
    missing_surface_matches = 0
    detected_surfaces: List[str] = []

    for event in events or []:
        if not isinstance(event, dict):
            continue
        if event.get("status_type") not in (None, "finished"):
            continue
        winner_id = as_int(event.get("winner_id"))
        winner_name = str(event.get("winner_name") or "")
        if winner_id is None and not winner_name:
            continue

        pick_won = _winner_matches_player(event, pick_id, pick)
        opponent_won = _winner_matches_player(event, opponent_id, opponent)
        if not pick_won and not opponent_won:
            # API returned a H2H event, but orientation cannot be proven.
            continue

        total += 1
        if pick_won:
            pick_wins += 1
        elif opponent_won:
            opponent_wins += 1

        event_surface = normalize_surface_bucket(event.get("surface") or event.get("surface_raw"))
        if event_surface:
            detected_surfaces.append(event_surface)
        else:
            missing_surface_matches += 1

        if requested_surface and event_surface == requested_surface:
            same_surface_total += 1
            if pick_won:
                same_surface_pick_wins += 1
            elif opponent_won:
                same_surface_opponent_wins += 1

    if total <= 0:
        return {
            "status": "NO_DATA",
            "source": "none",
            "total_matches": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "same_surface_matches": 0,
            "same_surface_pick_wins": 0,
            "same_surface_opponent_wins": 0,
            "same_surface_pick_win_pct": None,
            "same_surface_raw_edge": 0.0,
            "same_surface_effective_edge": 0.0,
            "same_surface_edge": 0.0,
            "same_surface_sample_quality": "NO_SAMPLE",
            "h2h_requested_surface": surface,
            "h2h_requested_surface_bucket": requested_surface,
            "h2h_detected_surface_buckets": [],
            "h2h_missing_surface_matches": 0,
            "raw_edge": 0.0,
            "effective_edge": 0.0,
            "edge": 0.0,
            "sample_cap": 0.0,
            "sample_quality": "NO_SAMPLE",
            "confidence": 0.0,
            "reason": "No oriented TennisAPI PRO H2H events available",
        }

    win_pct = pick_wins / total
    raw_edge = _clamp((win_pct - 0.5) * 0.08, -0.04, 0.04)
    confidence = min(0.15 + total * 0.08, 0.55)
    edge = effective_h2h_edge(raw_edge, total, confidence)

    surface_win_pct = (same_surface_pick_wins / same_surface_total) if same_surface_total else None
    raw_surface_edge = _clamp(((surface_win_pct or 0.5) - 0.5) * 0.08, -0.04, 0.04) if surface_win_pct is not None else 0.0
    surface_confidence = min(0.15 + same_surface_total * 0.08, 0.55) if same_surface_total else 0.0
    surface_edge = effective_h2h_edge(raw_surface_edge, same_surface_total, surface_confidence) if surface_win_pct is not None else 0.0

    return {
        "status": "OK",
        "source": "TENNISAPI_PRO_H2H",
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
        "same_surface_sample_quality": h2h_sample_quality(same_surface_total, surface_confidence),
        "h2h_requested_surface": surface,
        "h2h_requested_surface_bucket": requested_surface,
        "h2h_detected_surface_buckets": sorted(set(detected_surfaces)),
        "h2h_missing_surface_matches": missing_surface_matches,
        "raw_edge": round(raw_edge, 4),
        "effective_edge": round(edge, 4),
        "edge": round(edge, 4),
        "sample_cap": round(h2h_sample_cap(total), 4),
        "sample_quality": h2h_sample_quality(total, confidence),
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
    custom_id = string_id(event_custom_id)
    event_id_text = string_id(event_id)
    if not custom_id and event_id_text and not event_id_text.isdigit():
        custom_id = event_id_text

    key = cache_key(custom_id, event_id, player1_id, player2_id, pick, opponent)
    cache = load_h2h_cache()
    pairs = cache.setdefault("pairs", {})
    entry = pairs.get(key) if isinstance(pairs, dict) else None

    source = "cache"
    api_result: Optional[Dict[str, Any]] = None
    used_stale_cache = False

    if not isinstance(entry, dict) or not cache_entry_is_fresh(entry):
        api_result = fetch_h2h_from_api(custom_id)
        if api_result.get("payload") is not None:
            existing_events = entry.get("normalized_events") if isinstance(entry, dict) else []
            merged_events = merge_h2h_events(existing_events, api_result.get("normalized_events") or [])
            entry = {
                "cache_key": key,
                "custom_id": custom_id,
                "event_id": event_id,
                "pick": pick,
                "opponent": opponent,
                "pick_player_id": as_int(player1_id),
                "opponent_player_id": as_int(player2_id),
                "updated_at": now_iso(),
                "source": "TENNISAPI_PRO_H2H",
                "endpoint": api_result.get("endpoint"),
                "api_status_code": api_result.get("api_status_code"),
                "api_error": api_result.get("api_error"),
                "endpoint_attempts": api_result.get("endpoint_attempts") or [],
                "normalized_events": merged_events,
                "event_count": len(merged_events),
                "last_api_event_count": len(api_result.get("normalized_events") or []),
                "archive_policy": "append_update_merge_by_event_id_no_delete",
                "fetch_version": CACHE_VERSION,
            }
            pairs[key] = entry
            save_h2h_cache(cache)
            source = "api"
            write_last_refresh({
                "refreshed_at_utc": now_iso(),
                "source": "TENNISAPI_PRO_H2H",
                "cache_path": str(CACHE_PATH),
                "last_key": key,
                "pair_count": len(pairs),
                "last_api_status_code": api_result.get("api_status_code"),
                "last_api_error": api_result.get("api_error"),
                "last_event_count": len(api_result.get("normalized_events") or []),
            })
        elif isinstance(entry, dict):
            used_stale_cache = True
            source = "stale_cache"
        else:
            entry = None
            source = "api_no_data"

    events = (entry or {}).get("normalized_events") if isinstance(entry, dict) else []
    summary = summarize_h2h_events(
        events if isinstance(events, list) else [],
        pick=pick,
        opponent=opponent,
        surface=surface,
        pick_player_id=player1_id,
        opponent_player_id=player2_id,
    )

    if summary.get("status") == "OK":
        summary["source"] = {
            "api": "TENNISAPI_PRO_H2H_API",
            "cache": "TENNISAPI_PRO_H2H_CACHE",
            "stale_cache": "TENNISAPI_PRO_H2H_STALE_CACHE",
        }.get(source, "TENNISAPI_PRO_H2H")
    else:
        summary["source"] = "none" if source == "api_no_data" else source

    summary["cache_key"] = key
    summary["cache_path"] = str(CACHE_PATH)
    summary["last_refresh_path"] = str(LAST_REFRESH_PATH)
    summary["cache_updated_at"] = (entry or {}).get("updated_at") if isinstance(entry, dict) else None
    summary["cache_fresh"] = cache_entry_is_fresh(entry) if isinstance(entry, dict) else False
    summary["used_stale_cache"] = used_stale_cache
    summary["endpoint"] = (entry or {}).get("endpoint") if isinstance(entry, dict) else None
    summary["endpoint_attempts"] = (entry or {}).get("endpoint_attempts") if isinstance(entry, dict) else ((api_result or {}).get("endpoint_attempts") if api_result else [])
    summary["api_status_code"] = (entry or {}).get("api_status_code") if isinstance(entry, dict) else ((api_result or {}).get("api_status_code") if api_result else None)
    summary["api_error"] = (entry or {}).get("api_error") if isinstance(entry, dict) else ((api_result or {}).get("api_error") if api_result else None)
    summary["h2h_fetch_version"] = CACHE_VERSION
    summary["h2h_payload_event_count"] = (entry or {}).get("event_count") if isinstance(entry, dict) else 0
    summary["requested_event_id"] = as_int(event_id) or event_id
    summary["requested_event_custom_id"] = custom_id
    summary["requested_player1_id"] = as_int(player1_id)
    summary["requested_player2_id"] = as_int(player2_id)
    return summary



# ---------------------------------------------------------------------------
# Prewarm / registry helpers
# ---------------------------------------------------------------------------

PLAYERS_DIR = Path("thinq/data/players")
PLAYER_REGISTRY_PATH = PLAYERS_DIR / "player_registry.json"
PLAYER_REGISTRY_MANIFEST_PATH = PLAYERS_DIR / "player_registry_manifest.json"
H2H_MATCHUPS_PATH = CACHE_DIR / "h2h_matchups.json"
H2H_MANIFEST_PATH = CACHE_DIR / "h2h_manifest.json"
RUNTIME_H2H_DIR = Path("runtime/h2h")
RUNTIME_H2H_REPORT_PATH = RUNTIME_H2H_DIR / "h2h_coverage_report.json"
ELO_PLAYERS_INDEX_PATH = Path("thinq/data/elo/elo_players_index.json")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def load_elo_universe(path: Path = ELO_PLAYERS_INDEX_PATH) -> Dict[str, Dict[str, Any]]:
    payload = _load_json(path)
    players: Dict[str, Dict[str, Any]] = {}
    if isinstance(payload, dict):
        raw = payload.get("players")
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, dict):
                    players[compact_text(value.get("name") or key)] = value
        elif isinstance(raw, list):
            for value in raw:
                if isinstance(value, dict):
                    name = value.get("name") or value.get("player")
                    if name:
                        players[compact_text(name)] = value
    return players


def _rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "items", "all", "top7", "picks", "records", "data", "matches"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _load_rows(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    return _rows_from_payload(payload)


def _first(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "-", "N/A", "None"):
            return value
    return None


def _raw_event(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw")
    return raw if isinstance(raw, dict) else {}


def _side_player_id(row: Dict[str, Any], side: str) -> Any:
    raw = _raw_event(row)
    team_key = "homeTeam" if side == "HOME" else "awayTeam"
    team = raw.get(team_key) if isinstance(raw.get(team_key), dict) else {}
    return _first(row, (
        f"{side.lower()}_id",
        f"{side.lower()}_player_id",
    )) or team.get("id") or _nested_get(team, "playerTeamInfo", "id")


def _row_identity(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = _raw_event(row)
    custom_id = string_id(_first(row, (
        "event_custom_id",
        "custom_id",
        "customId",
        "thinq_h2h_requested_event_custom_id",
    )))
    if not custom_id:
        custom_id = string_id(raw.get("customId") or raw.get("custom_id"))

    event_id = _first(row, ("event_id", "match_id", "id")) or raw.get("id")
    if not custom_id and event_id not in (None, "") and not str(event_id).isdigit():
        custom_id = string_id(event_id)

    pick = str(_first(row, ("pick", "top7_pick", "cloq_pick", "player", "player1", "home_name")) or "").strip()
    opponent = str(_first(row, ("opponent", "opp", "player2", "away_name")) or "").strip()

    pick_id = _first(row, ("thinq_pick_player_id", "pick_player_id", "player1_id", "home_id", "home_player_id"))
    opponent_id = _first(row, ("thinq_opponent_player_id", "opponent_player_id", "player2_id", "away_id", "away_player_id"))
    if pick_id in (None, ""):
        pick_side = str(row.get("pick_side") or "").upper()
        pick_id = _side_player_id(row, pick_side) if pick_side in {"HOME", "AWAY"} else None
    if opponent_id in (None, ""):
        opponent_side = str(row.get("opponent_side") or "").upper()
        opponent_id = _side_player_id(row, opponent_side) if opponent_side in {"HOME", "AWAY"} else None

    return {
        "custom_id": custom_id,
        "event_id": event_id or custom_id,
        "pick": pick,
        "opponent": opponent,
        "surface": _first(row, ("surface", "surface_raw", "groundType", "court")) or raw.get("groundType"),
        "pick_id": pick_id,
        "opponent_id": opponent_id,
        "tournament": _first(row, ("tournament", "tournament_name", "event_tournament")) or _nested_get(raw, "tournament", "name"),
        "start_time": _first(row, ("start_time", "match_start", "startTimestamp", "start_timestamp", "match_time")) or raw.get("startTimestamp"),
    }


def _upsert_player(registry: Dict[str, Any], name: str, api_id: Any, tour: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    if not name:
        return
    key = f"api:{api_id}" if api_id not in (None, "") else f"name:{compact_text(name)}"
    players = registry.setdefault("players", {})
    current = players.get(key) if isinstance(players.get(key), dict) else {}
    current.update({
        "name": name,
        "compact_key": compact_text(name),
        "api_team_id": as_int(api_id),
        "tour": tour or current.get("tour"),
        "last_seen_at": now_iso(),
    })
    if extra:
        current.update({k: v for k, v in extra.items() if v not in (None, "")})
    players[key] = current


def prewarm_h2h_cache(outputs_dir: str = "outputs", max_requests: int = 60, require_elo: bool = True) -> Dict[str, Any]:
    out_dir = Path(outputs_dir)
    source_files = [
        out_dir / "latest_all.json",
        out_dir / "latest_top7.json",
        out_dir / "latest_cloq.json",
        out_dir / "cloq" / "latest_cloq.json",
    ]
    elo = load_elo_universe()
    registry = _load_json(PLAYER_REGISTRY_PATH) or {"version": CACHE_VERSION, "updated_at": now_iso(), "players": {}}
    matchups = _load_json(H2H_MATCHUPS_PATH) or {"version": CACHE_VERSION, "updated_at": now_iso(), "matchups": {}}

    seen = set()
    work: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    rejects = {"missing_identity": 0, "missing_custom_id": 0, "not_in_elo_universe": 0, "duplicate": 0}

    for path in source_files:
        rows = _load_rows(path)
        source_counts[str(path)] = len(rows)
        for row in rows:
            ident = _row_identity(row)
            if not ident["pick"] or not ident["opponent"]:
                rejects["missing_identity"] += 1
                continue
            if not ident["custom_id"]:
                rejects["missing_custom_id"] += 1
                continue
            pick_key = compact_text(ident["pick"])
            opp_key = compact_text(ident["opponent"])
            in_elo = (pick_key in elo) and (opp_key in elo)
            if require_elo and not in_elo:
                rejects["not_in_elo_universe"] += 1
                continue
            sig = (ident["custom_id"], pick_key, opp_key)
            if sig in seen:
                rejects["duplicate"] += 1
                continue
            seen.add(sig)
            work.append(ident)

    attempted = ok = no_data = errors = 0
    results: List[Dict[str, Any]] = []
    for ident in work[:max_requests]:
        attempted += 1
        try:
            ctx = build_h2h_context(
                event_id=ident["event_id"],
                pick=ident["pick"],
                opponent=ident["opponent"],
                surface=ident["surface"],
                player1_id=ident["pick_id"],
                player2_id=ident["opponent_id"],
                event_custom_id=ident["custom_id"],
            )
            if ctx.get("status") == "OK":
                ok += 1
            else:
                no_data += 1
            mkey = f"custom:{ident['custom_id']}"
            matchups.setdefault("matchups", {})[mkey] = {
                "custom_id": ident["custom_id"],
                "event_id": ident["event_id"],
                "player1_id": as_int(ident["pick_id"]),
                "player2_id": as_int(ident["opponent_id"]),
                "player1_name": ident["pick"],
                "player2_name": ident["opponent"],
                "surface": ident["surface"],
                "tournament": ident["tournament"],
                "start_time": ident["start_time"],
                "both_players_in_elo_universe": compact_text(ident["pick"]) in elo and compact_text(ident["opponent"]) in elo,
                "h2h_cache_key": ctx.get("cache_key"),
                "h2h_status": ctx.get("status"),
                "last_seen_at": now_iso(),
            }
            _upsert_player(registry, ident["pick"], ident["pick_id"], extra={"elo_available": compact_text(ident["pick"]) in elo})
            _upsert_player(registry, ident["opponent"], ident["opponent_id"], extra={"elo_available": compact_text(ident["opponent"]) in elo})
            results.append({"custom_id": ident["custom_id"], "status": ctx.get("status"), "matches": ctx.get("total_matches"), "cache_key": ctx.get("cache_key")})
        except Exception as exc:
            errors += 1
            results.append({"custom_id": ident.get("custom_id"), "status": "ERROR", "error": str(exc)})

    registry["updated_at"] = now_iso()
    matchups["updated_at"] = now_iso()
    _write_json(PLAYER_REGISTRY_PATH, registry)
    _write_json(PLAYER_REGISTRY_MANIFEST_PATH, {"updated_at": now_iso(), "player_count": len(registry.get("players", {}))})
    _write_json(H2H_MATCHUPS_PATH, matchups)

    manifest = {
        "status": "OK" if work else "NO_ELIGIBLE_MATCHES",
        "updated_at": now_iso(),
        "outputs_dir": outputs_dir,
        "require_elo": require_elo,
        "elo_universe_count": len(elo),
        "candidate_pairs": len(work),
        "attempted": attempted,
        "ok": ok,
        "no_data": no_data,
        "errors": errors,
        "source_counts": source_counts,
        "rejects": rejects,
        "cache_path": str(CACHE_PATH),
        "matchups_path": str(H2H_MATCHUPS_PATH),
        "player_registry_path": str(PLAYER_REGISTRY_PATH),
    }
    _write_json(H2H_MANIFEST_PATH, manifest)
    _write_json(RUNTIME_H2H_REPORT_PATH, {**manifest, "results": results})
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ThinQ H2H loader and cache prewarm")
    parser.add_argument("--custom-id", default=None)
    parser.add_argument("--pick", default="")
    parser.add_argument("--opponent", default="")
    parser.add_argument("--surface", default=None)
    parser.add_argument("--pick-id", default=None)
    parser.add_argument("--opponent-id", default=None)
    parser.add_argument("--prewarm", action="store_true")
    parser.add_argument("--outputs-dir", default=os.getenv("OUTPUTS_DIR", "outputs"))
    parser.add_argument("--max-requests", type=int, default=int(os.getenv("MAX_REQUESTS", "60") or 60))
    parser.add_argument("--require-elo", default=os.getenv("H2H_REQUIRE_ELO", "true"))
    args = parser.parse_args()

    if args.prewarm:
        require_elo = str(args.require_elo).strip().lower() not in {"0", "false", "no"}
        print(json.dumps(prewarm_h2h_cache(args.outputs_dir, args.max_requests, require_elo), ensure_ascii=False, indent=2))
    elif args.custom_id:
        print(json.dumps(build_h2h_context(
            event_id=args.custom_id,
            event_custom_id=args.custom_id,
            pick=args.pick,
            opponent=args.opponent,
            surface=args.surface,
            player1_id=args.pick_id,
            player2_id=args.opponent_id,
        ), ensure_ascii=False, indent=2))
    else:
        cache = load_h2h_cache()
        print(json.dumps({
            "cache_path": str(CACHE_PATH),
            "pair_count": len(cache.get("pairs", {})),
            "updated_at": cache.get("updated_at"),
        }, ensure_ascii=False, indent=2))
