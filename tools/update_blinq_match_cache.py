"""Preload verified API PRO previous-match data for BlinQ.

This updater runs in GitHub Actions, never in the Azure prediction runtime.
It uses only players with real ELO and a real API player ID, preserves valid
existing cache files, limits API calls, and never fabricates missing events.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

API_HOST = "tennisapi1.p.rapidapi.com"
API_BASE_URL = "https://tennisapi1.p.rapidapi.com"
REGISTRY_PATH = Path("blinq/data/players/player_registry.json")
CACHE_DIR = Path("blinq/data/form/previous_matches")
MANIFEST_PATH = Path("blinq/data/form/match_cache_manifest.json")
MISSING_PATH = Path("blinq/data/form/missing_match_cache.json")
DEFAULT_TIMEOUT = 20
DEFAULT_DELAY_SECONDS = 0.30
DEFAULT_TTL_HOURS = 168
DEFAULT_STALE_FALLBACK_DAYS = 90
DEFAULT_MAX_PAGES = 2


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except Exception:
        return default


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_time(value: Any) -> Optional[datetime]:
    try:
        text = str(value or "").replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def registry_players() -> List[Dict[str, Any]]:
    payload = read_json(REGISTRY_PATH, {})
    rows = payload.get("players") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    eligible: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("elo") in (None, ""):
            continue
        player_id = as_int(row.get("player_id") or row.get("api_team_id") or row.get("rapidapi_id"))
        if player_id is None:
            continue
        eligible.setdefault(player_id, row)
    return list(eligible.values())


def cache_path(player_id: int, page: int) -> Path:
    return CACHE_DIR / f"{player_id}_{page}.json"


def cache_state(path: Path, ttl_hours: int, stale_days: int) -> str:
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        return "MISSING"
    saved = parse_time(payload.get("saved_at_iso"))
    if saved is None:
        try:
            saved = datetime.fromtimestamp(float(payload.get("saved_at")), tz=timezone.utc)
        except Exception:
            saved = None
    if saved is None:
        return "INVALID"
    age = now_utc() - saved
    if age <= timedelta(hours=max(ttl_hours, 0)):
        return "FRESH"
    if age <= timedelta(days=max(stale_days, 0)):
        return "STALE_VALID"
    return "EXPIRED"


def fetch_page(player_id: int, page: int, api_key: str, timeout: int) -> Dict[str, Any]:
    endpoint = f"{API_BASE_URL}/api/tennis/player/{player_id}/events/previous/{page}"
    response = requests.get(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "x-rapidapi-host": API_HOST,
            "x-rapidapi-key": api_key,
        },
        timeout=timeout,
    )
    if response.status_code == 429:
        raise RuntimeError("RATE_LIMITED")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("INVALID_RESPONSE_SHAPE")
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError("INVALID_EVENTS_SHAPE")
    return {
        "status": "OK",
        "events": events,
        "has_next_page": bool(payload.get("hasNextPage")),
        "page": page,
        "player_id": player_id,
        "endpoint": endpoint,
        "api_status_code": response.status_code,
        "saved_at": time.time(),
        "saved_at_iso": now_iso(),
        "source": "API_PRO_PREVIOUS_MATCHES",
    }


def existing_cache_player_ids() -> set[int]:
    ids: set[int] = set()
    for path in CACHE_DIR.glob("*.json"):
        player_id = as_int(path.stem.split("_", 1)[0])
        if player_id is not None:
            ids.add(player_id)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Preload verified BlinQ previous-match cache")
    parser.add_argument("--max-requests", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--ttl-hours", type=int, default=DEFAULT_TTL_HOURS)
    parser.add_argument("--stale-fallback-days", type=int, default=DEFAULT_STALE_FALLBACK_DAYS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        raise SystemExit("RAPIDAPI_KEY is missing")

    players = registry_players()
    if not players:
        raise SystemExit(f"No ELO + API-ID players in {REGISTRY_PATH}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    requests_used = updated_files = fresh_skipped = stale_preserved = failed = no_events = 0
    rate_limited = False
    errors: List[Dict[str, Any]] = []
    player_results: List[Dict[str, Any]] = []
    max_requests = max(args.max_requests, 0)
    max_pages = max(1, min(args.max_pages, 3))

    for row in sorted(players, key=lambda item: str(item.get("player") or "").casefold()):
        player_id = as_int(row.get("player_id") or row.get("api_team_id") or row.get("rapidapi_id"))
        name = str(row.get("player") or row.get("canonical_name") or "")
        if player_id is None:
            continue
        result = {"player_id": player_id, "player": name, "pages": []}

        for page in range(max_pages):
            path = cache_path(player_id, page)
            state = cache_state(path, args.ttl_hours, args.stale_fallback_days)
            if not args.force and state == "FRESH":
                fresh_skipped += 1
                result["pages"].append({"page": page, "status": "FRESH_CACHE"})
                cached = read_json(path, {})
                if not cached.get("has_next_page"):
                    break
                continue
            if requests_used >= max_requests:
                result["pages"].append({"page": page, "status": "REQUEST_LIMIT_REACHED"})
                break

            requests_used += 1
            try:
                payload = fetch_page(player_id, page, api_key, args.timeout)
                write_atomic(path, payload)
                updated_files += 1
                if not payload["events"]:
                    no_events += 1
                result["pages"].append({"page": page, "status": "UPDATED", "events": len(payload["events"])})
                time.sleep(max(args.delay_seconds, 0.0))
                if not payload.get("has_next_page"):
                    break
            except Exception as exc:
                failed += 1
                error = str(exc)
                if state == "STALE_VALID":
                    stale_preserved += 1
                errors.append({
                    "player_id": player_id,
                    "player": name,
                    "page": page,
                    "error": error,
                    "preserved_cache_state": state,
                })
                result["pages"].append({"page": page, "status": "FAILED", "error": error, "preserved": state})
                if error == "RATE_LIMITED":
                    rate_limited = True
                break

        player_results.append(result)
        if rate_limited or requests_used >= max_requests:
            break

    cached_ids = existing_cache_player_ids()
    eligible_ids = {
        as_int(row.get("player_id") or row.get("api_team_id") or row.get("rapidapi_id"))
        for row in players
    }
    eligible_ids.discard(None)
    missing_ids = sorted(eligible_ids - cached_ids)
    by_id = {
        as_int(row.get("player_id") or row.get("api_team_id") or row.get("rapidapi_id")): row
        for row in players
    }
    missing = [
        {
            "player_id": player_id,
            "player": str(by_id[player_id].get("player") or by_id[player_id].get("canonical_name") or ""),
            "reason": "NO_VERIFIED_PREVIOUS_MATCH_CACHE",
        }
        for player_id in missing_ids
    ]

    generated_at = now_iso()
    manifest = {
        "version": "BLINQ_VERIFIED_MATCH_CACHE_V1",
        "generated_at": generated_at,
        "status": "RATE_LIMITED" if rate_limited else "OK",
        "source": "API_PRO_PREVIOUS_MATCHES",
        "eligible_players": len(players),
        "players_with_cache": len(cached_ids & eligible_ids),
        "players_missing_cache": len(missing),
        "requests": requests_used,
        "updated_files": updated_files,
        "fresh_cache_skipped": fresh_skipped,
        "stale_cache_preserved_after_failure": stale_preserved,
        "no_event_responses": no_events,
        "failed": failed,
        "max_pages": max_pages,
        "errors": errors[:100],
        "processed": player_results,
    }
    missing_payload = {
        "version": "BLINQ_MISSING_MATCH_CACHE_V1",
        "generated_at": generated_at,
        "count": len(missing),
        "players": missing,
    }
    write_atomic(MANIFEST_PATH, manifest)
    write_atomic(MISSING_PATH, missing_payload)
    print(json.dumps({key: value for key, value in manifest.items() if key not in {"errors", "processed"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
