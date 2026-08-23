"""Update API PRO rankings per player ID without inventing missing data.

Source endpoint:
    GET /api/tennis/player/{player_id}/rankings

The updater reads player IDs from player_registry.json, keeps valid cached rows,
limits requests, and never replaces the cache with an empty result.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

API_HOST = "tennisapi1.p.rapidapi.com"
API_BASE_URL = "https://tennisapi1.p.rapidapi.com"
DEFAULT_REGISTRY = Path("thinq/data/players/player_registry.json")
DEFAULT_OUTPUT = Path("thinq/data/rankings/api_pro_player_rankings.json")
DEFAULT_TIMEOUT = 20
DEFAULT_DELAY_SECONDS = 0.25


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_name(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split())


def normalize_country(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("alpha3") or value.get("alpha2") or value.get("name")
    text = str(value or "").strip().upper()
    return text or None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except Exception:
        return default


def registry_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("players", "items", "rows", "data", "registry"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            return [dict(row) for row in value.values() if isinstance(row, dict)]
    return [dict(row) for row in payload.values() if isinstance(row, dict)]


def player_id(row: Dict[str, Any]) -> Optional[int]:
    for key in ("api_team_id", "rapidapi_id", "player_id", "team_id", "id"):
        value = as_int(row.get(key))
        if value is not None:
            return value
    return None


def player_name(row: Dict[str, Any]) -> str:
    for key in ("display_name", "canonical_name", "player", "name", "player_name"):
        name = clean_name(row.get(key))
        if name:
            return name
    return ""


def player_country(row: Dict[str, Any]) -> Optional[str]:
    for key in ("country_alpha3", "country_code", "country", "nationality"):
        country = normalize_country(row.get(key))
        if country:
            return country
    return None


def existing_players(payload: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    players = payload.get("players")
    return dict(players) if isinstance(players, dict) else {}


def parse_time(value: Any) -> Optional[datetime]:
    try:
        text = str(value or "").replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except Exception:
        return None


def is_fresh(row: Dict[str, Any], ttl_hours: int) -> bool:
    updated = parse_time(row.get("updated_at"))
    return bool(updated and now_utc() - updated < timedelta(hours=max(ttl_hours, 0)))


def fetch_rankings(player: int, api_key: str, timeout: int) -> Dict[str, Any]:
    endpoint = f"{API_BASE_URL}/api/tennis/player/{player}/rankings"
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
    return payload


def select_current_ranking(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rankings = payload.get("rankings")
    if not isinstance(rankings, list):
        return None
    candidates: List[Dict[str, Any]] = []
    for row in rankings:
        if not isinstance(row, dict):
            continue
        rank = as_int(row.get("ranking"))
        if rank is None:
            continue
        ranking_class = str(row.get("rankingClass") or "").strip().lower()
        row_type = as_int(row.get("type"))
        disabled = bool(row.get("disabled"))
        if disabled:
            continue
        quality = 0
        if ranking_class in {"team", "singles", "player"}:
            quality += 4
        if row_type in (None, 6):
            quality += 2
        if as_int(row.get("points")) is not None:
            quality += 1
        candidates.append({"quality": quality, "row": row})
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item["quality"], as_int(item["row"].get("ranking")) or 999999))
    return candidates[0]["row"]


def build_record(registry_row: Dict[str, Any], ranking_row: Dict[str, Any], pid: int) -> Dict[str, Any]:
    team = ranking_row.get("team") if isinstance(ranking_row.get("team"), dict) else {}
    country = team.get("country") if isinstance(team.get("country"), dict) else {}
    name = clean_name(team.get("name")) or player_name(registry_row)
    alpha3 = normalize_country(country.get("alpha3")) or player_country(registry_row)
    return {
        "player_id": pid,
        "name": name,
        "country": alpha3,
        "ranking": as_int(ranking_row.get("ranking")),
        "points": as_int(ranking_row.get("points")),
        "previous_ranking": as_int(ranking_row.get("previousRanking")),
        "best_ranking": as_int(ranking_row.get("bestRanking")),
        "ranking_class": ranking_row.get("rankingClass"),
        "source": "API_PRO_PLAYER_RANKINGS",
        "updated_at": iso_utc(),
    }


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update API PRO player ranking cache")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-players", type=int, default=100)
    parser.add_argument("--ttl-hours", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        raise SystemExit("RAPIDAPI_KEY is missing")

    registry_path = Path(args.registry)
    output_path = Path(args.output)
    rows = registry_rows(load_json(registry_path, {}))
    if not rows:
        raise SystemExit(f"Player registry has no usable rows: {registry_path}")

    old_payload = load_json(output_path, {})
    players = existing_players(old_payload)
    unique: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        pid = player_id(row)
        if pid is not None and player_name(row):
            unique.setdefault(pid, row)

    requested = updated = skipped_fresh = no_ranking = failed = 0
    errors: List[Dict[str, Any]] = []
    limit = max(args.max_players, 0)

    for pid, row in unique.items():
        key = str(pid)
        cached = players.get(key) if isinstance(players.get(key), dict) else {}
        if not args.force and cached and is_fresh(cached, args.ttl_hours):
            skipped_fresh += 1
            continue
        if requested >= limit:
            break
        requested += 1
        try:
            payload = fetch_rankings(pid, api_key, args.timeout)
            ranking = select_current_ranking(payload)
            if ranking is None:
                no_ranking += 1
            else:
                record = build_record(row, ranking, pid)
                if record.get("ranking") is not None:
                    players[key] = record
                    updated += 1
            time.sleep(max(args.delay_seconds, 0.0))
        except Exception as exc:
            failed += 1
            errors.append({"player_id": pid, "name": player_name(row), "error": str(exc)})
            if str(exc) == "RATE_LIMITED":
                break

    if not players:
        raise SystemExit("Ranking update produced no rows; existing cache was not overwritten")

    output = {
        "generated_at": iso_utc(),
        "source": "API_PRO_PLAYER_RANKINGS",
        "endpoint_template": "/api/tennis/player/{player_id}/rankings",
        "registry": str(registry_path),
        "stats": {
            "registry_players_with_id": len(unique),
            "requests": requested,
            "updated": updated,
            "fresh_cache_skipped": skipped_fresh,
            "no_ranking": no_ranking,
            "failed": failed,
            "cached_players": len(players),
        },
        "errors": errors[:50],
        "players": players,
    }
    write_atomic(output_path, output)
    print(json.dumps(output["stats"], indent=2))
    print(f"Ranking cache written: {output_path}")


if __name__ == "__main__":
    main()
