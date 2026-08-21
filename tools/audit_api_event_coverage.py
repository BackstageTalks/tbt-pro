#!/usr/bin/env python3
"""Audit all API PRO tennis events available for a LucQ betting-day window.

Purpose:
- discover events independently of winner odds;
- merge category/date and odds/date event feeds;
- keep every unique API event for audit;
- produce a clean list of singles inside the 06:00 -> 06:00 Europe/Bratislava window;
- never apply CorQ, ThinQ, CloQ, MarQ, ELO, ranking, or odds eligibility filters.

Outputs:
- runtime/api/api_all_discovered_events.json
- runtime/api/api_event_coverage_audit.json
- outputs/lucq/discovered_singles.json

Only API PRO is used. No synthetic matches or values are created.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import (
    RapidApiClient,
    dedupe_events,
    normalize_event_for_corq,
)

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
DEFAULT_CATEGORY_IDS = (3, 6, 871)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_date(value: Optional[str]) -> datetime:
    if value:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.replace(tzinfo=LOCAL_TZ)
    return datetime.now(LOCAL_TZ)


def betting_window(target: datetime) -> Tuple[datetime, datetime, str]:
    local = target.astimezone(LOCAL_TZ)
    day = local.date()
    start = datetime.combine(day, time(6, 0), tzinfo=LOCAL_TZ)
    if local < start:
        start -= timedelta(days=1)
    end = start + timedelta(days=1)
    return start, end, start.date().isoformat()


def fetch_dates(start: datetime, end: datetime) -> List[datetime]:
    dates: List[datetime] = []
    cursor = start.date()
    last = (end - timedelta(microseconds=1)).date()
    while cursor <= last:
        dates.append(datetime.combine(cursor, time(12, 0), tzinfo=LOCAL_TZ))
        cursor += timedelta(days=1)
    return dates


def as_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("events", "data", "items", "results", "categories"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = as_list(value)
            if nested:
                return nested

    # Some odds/date payloads are keyed by event or are a single event-like row.
    if any(k in payload for k in ("id", "eventId", "event_id", "homeTeam", "awayTeam", "event")):
        return [payload]
    return []


def unwrap_event(item: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("event", "match"):
        value = item.get(key)
        if isinstance(value, dict):
            merged = dict(value)
            merged.setdefault("_coverage_wrapper", {k: v for k, v in item.items() if k != key})
            return merged
    return dict(item)


def event_key(event: Dict[str, Any]) -> str:
    for key in ("id", "eventId", "event_id", "matchId", "match_id", "customId", "custom_id"):
        value = event.get(key)
        if value not in (None, ""):
            return f"id:{value}"
    normalized = normalize_event_for_corq(event) or {}
    p1 = str(normalized.get("player1") or "").strip().lower()
    p2 = str(normalized.get("player2") or "").strip().lower()
    start = str(normalized.get("match_start") or normalized.get("start_time") or "")
    return f"fallback:{p1}|{p2}|{start}"


def parse_start(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def normalized_start(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("match_start", "start_time", "start_time_utc", "match_time_utc", "startTimestamp", "start_timestamp"):
        dt = parse_start(row.get(key))
        if dt is not None:
            return dt
    raw = row.get("raw")
    if isinstance(raw, dict):
        for key in ("startTimestamp", "start_timestamp"):
            dt = parse_start(raw.get(key))
            if dt is not None:
                return dt
    return None


def category_ids_from_env() -> List[int]:
    raw = os.getenv("TENNISAPI_CATEGORY_IDS", "")
    found: List[int] = []
    for part in raw.split(","):
        try:
            value = int(part.strip())
            if value > 0 and value not in found:
                found.append(value)
        except Exception:
            pass
    for value in DEFAULT_CATEGORY_IDS:
        if value not in found:
            found.append(value)
    return found


def merge_event(store: Dict[str, Dict[str, Any]], sources: Dict[str, set], event: Dict[str, Any], source: str) -> None:
    event = unwrap_event(event)
    key = event_key(event)
    if key not in store:
        store[key] = event
    else:
        merged = dict(store[key])
        for field, value in event.items():
            if value not in (None, "", [], {}):
                merged[field] = value
        store[key] = merged
    sources[key].add(source)


def safe_get(client: RapidApiClient, path: str) -> Tuple[Any, Optional[str]]:
    try:
        return client.get(path), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit all API PRO tennis event coverage")
    parser.add_argument("--date", help="Date inside the required betting day, YYYY-MM-DD")
    parser.add_argument("--output-root", default="runtime/api")
    parser.add_argument("--lucq-output", default="outputs/lucq/discovered_singles.json")
    args = parser.parse_args()

    target = parse_date(args.date)
    window_start, window_end, betting_day = betting_window(target)
    dates = fetch_dates(window_start, window_end)
    client = RapidApiClient()

    events: Dict[str, Dict[str, Any]] = {}
    event_sources: Dict[str, set] = defaultdict(set)
    endpoint_audit: List[Dict[str, Any]] = []
    category_ids = set(category_ids_from_env())

    for date_dt in dates:
        d, m, y = date_dt.day, date_dt.month, date_dt.year

        category_paths = (
            f"/api/tennis/calendar/{d}/{m}/{y}/categories",
            f"/api/tennis/categories/{d}/{m}/{y}",
        )
        for path in category_paths:
            payload, error = safe_get(client, path)
            items = as_list(payload)
            discovered: List[int] = []
            for item in items:
                value = item.get("id") or item.get("categoryId") or item.get("category_id")
                try:
                    discovered.append(int(value))
                except Exception:
                    pass
            category_ids.update(discovered)
            endpoint_audit.append({
                "source": "category_discovery",
                "date": date_dt.date().isoformat(),
                "path": path,
                "items": len(items),
                "category_ids": sorted(set(discovered)),
                "error": error,
            })

        # Wider odds/date feed. It is merged as event discovery only and is not
        # a requirement for LucQ eligibility.
        odds_path = f"/api/tennis/events/odds/{d}/{m}/{y}"
        payload, error = safe_get(client, odds_path)
        odds_items = as_list(payload)
        for item in odds_items:
            merge_event(events, event_sources, item, "events_odds_by_date")
        endpoint_audit.append({
            "source": "events_odds_by_date",
            "date": date_dt.date().isoformat(),
            "path": odds_path,
            "items": len(odds_items),
            "error": error,
        })

        # Calendar category feeds are the broad master event source.
        for category_id in sorted(category_ids):
            paths = (
                f"/api/tennis/category/{category_id}/events/{d}/{m}/{y}",
                f"/api/tennis/categories/{category_id}/events/{d}/{m}/{y}",
            )
            category_found = False
            for path in paths:
                payload, error = safe_get(client, path)
                items = as_list(payload)
                for item in items:
                    merge_event(events, event_sources, item, f"category:{category_id}")
                endpoint_audit.append({
                    "source": "category_events",
                    "category_id": category_id,
                    "date": date_dt.date().isoformat(),
                    "path": path,
                    "items": len(items),
                    "error": error,
                })
                if items:
                    category_found = True
                    break
            if not category_found:
                continue

    all_events = list(events.values())
    all_events = dedupe_events(all_events)

    normalized_rows: List[Dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    start_utc = window_start.astimezone(timezone.utc)
    end_utc = window_end.astimezone(timezone.utc)

    for event in all_events:
        key = event_key(event)
        for source in event_sources.get(key, set()):
            source_counts[source] += 1

        row = normalize_event_for_corq(event)
        if not isinstance(row, dict):
            reject_counts["normalization_failed"] += 1
            continue
        start = normalized_start(row)
        if start is None:
            reject_counts["missing_start"] += 1
            continue
        if start < start_utc:
            reject_counts["before_window"] += 1
            continue
        if start >= end_utc:
            reject_counts["after_window"] += 1
            continue
        if row.get("is_doubles"):
            reject_counts["doubles"] += 1
            continue

        item = dict(row)
        item["betting_day"] = betting_day
        item["betting_day_start_local"] = window_start.isoformat()
        item["betting_day_end_local"] = window_end.isoformat()
        item["betting_day_timezone"] = "Europe/Bratislava"
        item["coverage_sources"] = sorted(event_sources.get(key, set()))
        item["event_discovery_policy"] = "API_PRO_ALL_EVENTS_NO_ODDS_REQUIREMENT"
        normalized_rows.append(item)

    normalized_rows.sort(key=lambda r: normalized_start(r) or datetime.max.replace(tzinfo=timezone.utc))

    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    lucq_path = Path(args.lucq_output)
    lucq_path.parent.mkdir(parents=True, exist_ok=True)

    raw_output = {
        "generated_at": now_iso(),
        "betting_day": betting_day,
        "betting_day_start_local": window_start.isoformat(),
        "betting_day_end_local": window_end.isoformat(),
        "event_count": len(all_events),
        "events": all_events,
    }
    audit_output = {
        "generated_at": now_iso(),
        "status": "OK",
        "source_policy": "API_PRO_ONLY",
        "betting_day": betting_day,
        "betting_day_start_local": window_start.isoformat(),
        "betting_day_end_local": window_end.isoformat(),
        "fetch_dates": [d.date().isoformat() for d in dates],
        "category_ids": sorted(category_ids),
        "raw_unique_events": len(all_events),
        "singles_in_window": len(normalized_rows),
        "reject_counts": dict(sorted(reject_counts.items())),
        "source_event_counts": dict(sorted(source_counts.items())),
        "endpoint_attempts": endpoint_audit,
        "outputs": {
            "raw_events": str(out_root / "api_all_discovered_events.json"),
            "audit": str(out_root / "api_event_coverage_audit.json"),
            "lucq_singles": str(lucq_path),
        },
    }
    lucq_output = {
        "generated_at": now_iso(),
        "status": "OK" if normalized_rows else "NO_SINGLES_IN_WINDOW",
        "source_policy": "API_PRO_ALL_EVENTS_NO_ODDS_REQUIREMENT",
        "betting_day": betting_day,
        "betting_day_start_local": window_start.isoformat(),
        "betting_day_end_local": window_end.isoformat(),
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
    }

    (out_root / "api_all_discovered_events.json").write_text(
        json.dumps(raw_output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (out_root / "api_event_coverage_audit.json").write_text(
        json.dumps(audit_output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lucq_path.write_text(
        json.dumps(lucq_output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print("API PRO COVERAGE AUDIT")
    print(f"betting_day={betting_day}")
    print(f"window={window_start.isoformat()} -> {window_end.isoformat()}")
    print(f"categories={sorted(category_ids)}")
    print(f"raw_unique_events={len(all_events)}")
    print(f"singles_in_window={len(normalized_rows)}")
    print(f"reject_counts={dict(sorted(reject_counts.items()))}")
    print(f"raw_output={out_root / 'api_all_discovered_events.json'}")
    print(f"audit_output={out_root / 'api_event_coverage_audit.json'}")
    print(f"lucq_output={lucq_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
