from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SNAPSHOT_ROOT = Path("data/marq_ai/odds_snapshots")
EVENTS_DIR = SNAPSHOT_ROOT / "events"
LATEST_PATH = SNAPSHOT_ROOT / "latest.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return None
        number = float(str(value).replace(",", "."))
        if math.isfinite(number):
            return number
    except Exception:
        return None
    return None


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _slug(value: Any) -> str:
    text = _normalize_name(value).replace(" ", "-")
    return text or "unknown"


def _tokens(value: Any) -> set[str]:
    return set(_normalize_name(value).split())


def _name_score(a: Any, b: Any) -> float:
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    ta = _tokens(na)
    tb = _tokens(nb)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _event_key(date_only: str, player1: Any, player2: Any) -> str:
    a, b = sorted([_slug(player1), _slug(player2)])
    return f"{str(date_only)[:10]}_{a}_vs_{b}"


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if re.fullmatch(r"\d{10,13}", text):
            dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
        else:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event_start_time(event: Dict[str, Any], date_only: str) -> Optional[str]:
    for key in (
        "startTimestamp", "start_time_utc", "startTime", "startDate", "startAt",
        "scheduledAt", "commence_time", "time", "dateTime", "date",
    ):
        value = event.get(key)
        if value in (None, ""):
            continue
        if key == "startTimestamp":
            dt = _parse_datetime(str(value))
        else:
            dt = _parse_datetime(value)
        if dt:
            return dt.isoformat()
    return None


def _team_name_from_obj(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "shortName", "fullName", "displayName", "slug"):
            found = value.get(key)
            if found:
                return str(found)
    return str(value or "")


def _event_from_bulk_payload(bulk_odds: Any) -> Optional[Dict[str, Any]]:
    """Best-effort event extraction from the daily odds payload.

    This avoids one /event/{id} detail request per fixture. We only call the
    detail endpoint when the daily odds payload does not contain team names.
    """
    if not isinstance(bulk_odds, dict):
        return None
    for key in ("event", "match", "fixture", "data"):
        value = bulk_odds.get(key)
        if isinstance(value, dict) and (value.get("homeTeam") or value.get("awayTeam") or value.get("home") or value.get("away")):
            return value
    if bulk_odds.get("homeTeam") or bulk_odds.get("awayTeam") or bulk_odds.get("home") or bulk_odds.get("away"):
        return bulk_odds
    return None


def _event_home_away_from_any(event: Dict[str, Any]) -> Tuple[str, str]:
    home = _team_name_from_obj(
        event.get("homeTeam") or event.get("home") or event.get("participant1") or event.get("team1")
    )
    away = _team_name_from_obj(
        event.get("awayTeam") or event.get("away") or event.get("participant2") or event.get("team2")
    )
    return home, away


def _is_doubles_or_team_match(player1: Any, player2: Any, event: Optional[Dict[str, Any]] = None) -> bool:
    text = f"{player1 or ''} {player2 or ''}".lower()
    if " / " in text or "/" in str(player1 or "") or "/" in str(player2 or ""):
        return True
    if isinstance(event, dict):
        tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
        t_name = str(tournament.get("name") or event.get("tournamentName") or "").lower()
        t_slug = str(tournament.get("slug") or event.get("tournamentSlug") or "").lower()
        if "doubles" in t_name or "doubles" in t_slug:
            return True
    return False


def _rate_limited(provider_mod: Any) -> bool:
    return bool(getattr(provider_mod, "_RATE_LIMITED", False))


def _load_event_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"event_key": path.stem, "snapshots": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("snapshots", [])
            return payload
    except Exception:
        pass
    return {"event_key": path.stem, "snapshots": []}


def _save_event_snapshot(record: Dict[str, Any]) -> None:
    event_key = str(record.get("event_key") or "").strip()
    if not event_key:
        return
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVENTS_DIR / f"{event_key}.json"
    payload = _load_event_file(path)
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        snapshots = []
    signature = (
        record.get("snapshot_time_utc"),
        round(float(record.get("odds_player1") or 0), 5),
        round(float(record.get("odds_player2") or 0), 5),
    )
    existing = {
        (
            snap.get("snapshot_time_utc"),
            round(float(snap.get("odds_player1") or 0), 5),
            round(float(snap.get("odds_player2") or 0), 5),
        )
        for snap in snapshots
        if isinstance(snap, dict)
    }
    if signature not in existing:
        snapshots.append(record)
    snapshots = sorted(snapshots, key=lambda item: str(item.get("snapshot_time_utc") or ""))[-80:]
    payload.update({
        "event_key": event_key,
        "event_id": record.get("event_id") or payload.get("event_id"),
        "player1": record.get("player1") or payload.get("player1"),
        "player2": record.get("player2") or payload.get("player2"),
        "start_time_utc": record.get("start_time_utc") or payload.get("start_time_utc"),
        "updated_at_utc": _utc_now().isoformat(),
        "snapshots": snapshots,
    })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _extract_full_time_odds_from_bulk(bulk_odds: Any) -> Tuple[Optional[float], Optional[float]]:
    # Re-use the provider parser when the module is available inside the repo.
    try:
        from marq import provider as provider_mod  # type: ignore
        markets = provider_mod._extract_markets(bulk_odds)  # noqa: SLF001
        market = provider_mod._select_full_time_market(markets)  # noqa: SLF001
        if market:
            parsed = provider_mod._extract_choice_markets(market)  # noqa: SLF001
            return _as_float(parsed.get("odds_1")), _as_float(parsed.get("odds_2"))
    except Exception:
        pass
    if isinstance(bulk_odds, dict):
        for left, right in (("odds_1", "odds_2"), ("odds1", "odds2"), ("home_odds", "away_odds")):
            o1, o2 = _as_float(bulk_odds.get(left)), _as_float(bulk_odds.get(right))
            if o1 and o2:
                return o1, o2
    return None, None


def collect_horizon_snapshots(days_ahead: int = 6, force_refresh: bool = False, max_detail_events_per_day: int = 80) -> Dict[str, Any]:
    """Collect match-winner odds snapshots for today through days_ahead.

    The collector first uses the daily odds payload and only calls the event
    detail endpoint when team names are missing. This prevents burning hundreds
    of detail requests on ITF/doubles matches and avoids 429 rate spikes.
    """
    from marq import provider as provider_mod  # type: ignore

    snapshot_time = _utc_now()
    today = snapshot_time.date()
    daily_records: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    detail_counts: Dict[str, int] = {}
    skipped_counts: Dict[str, int] = {}
    rate_limited = False

    for offset in range(max(0, days_ahead) + 1):
        day = today + timedelta(days=offset)
        date_only = day.isoformat()
        if _rate_limited(provider_mod):
            rate_limited = True
            counts[date_only] = 0
            detail_counts[date_only] = 0
            skipped_counts[date_only] = 0
            continue

        odds_by_event = provider_mod.fetch_events_odds_by_date(date_only, force_refresh=force_refresh)
        saved_count = 0
        skipped_count = 0
        detail_used = 0

        for event_id, bulk_odds in list(odds_by_event.items()):
            if _rate_limited(provider_mod):
                rate_limited = True
                break

            # Odds first. If there is no match-winner price in the daily payload,
            # do not spend a detail request on this event.
            odds1, odds2 = _extract_full_time_odds_from_bulk(bulk_odds)
            if odds1 is None or odds2 is None:
                quote = provider_mod._quote_from_payload(  # noqa: SLF001
                    bulk_odds,
                    event_id=str(event_id),
                    provider_id=None,
                    provider_name="bulk",
                )
                if isinstance(quote, dict):
                    odds1, odds2 = _as_float(quote.get("odds_1")), _as_float(quote.get("odds_2"))
            if odds1 is None or odds2 is None:
                skipped_count += 1
                continue

            event = _event_from_bulk_payload(bulk_odds)
            if event:
                player1, player2 = _event_home_away_from_any(event)
            else:
                if detail_used >= max_detail_events_per_day:
                    skipped_count += 1
                    continue
                event = provider_mod.fetch_match_details(str(event_id), force_refresh=force_refresh)
                detail_used += 1
                if not event:
                    skipped_count += 1
                    continue
                player1, player2 = provider_mod._event_home_away(event)  # noqa: SLF001

            if not player1 or not player2:
                skipped_count += 1
                continue
            if _is_doubles_or_team_match(player1, player2, event):
                skipped_count += 1
                continue

            start_time_utc = _event_start_time(event or {}, date_only)
            start_dt = _parse_datetime(start_time_utc)
            hours_to_start = None
            if start_dt:
                hours_to_start = round((start_dt - snapshot_time).total_seconds() / 3600.0, 2)

            record = {
                "schema": "marq_internal_odds_snapshot_v1",
                "source": "TennisAPI_PRO",
                "snapshot_time_utc": snapshot_time.isoformat(),
                "target_date": date_only,
                "hours_to_start": hours_to_start,
                "event_id": str(event_id),
                "event_key": _event_key(date_only, player1, player2),
                "player1": player1,
                "player2": player2,
                "start_time_utc": start_time_utc,
                "market": "match_winner",
                "odds_player1": round(float(odds1), 5),
                "odds_player2": round(float(odds2), 5),
            }
            _save_event_snapshot(record)
            daily_records.append(record)
            saved_count += 1

        counts[date_only] = saved_count
        detail_counts[date_only] = detail_used
        skipped_counts[date_only] = skipped_count

    year_dir = SNAPSHOT_ROOT / str(today.year)
    year_dir.mkdir(parents=True, exist_ok=True)
    daily_path = year_dir / f"{today.isoformat()}.json"
    summary = {
        "schema": "marq_internal_odds_snapshot_daily_v1",
        "generated_at_utc": snapshot_time.isoformat(),
        "days_ahead": days_ahead,
        "source": "TennisAPI_PRO",
        "rate_limited": rate_limited,
        "date_counts": counts,
        "detail_request_counts": detail_counts,
        "skipped_counts": skipped_counts,
        "snapshot_count": len(daily_records),
        "snapshots": daily_records,
    }
    daily_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary

def _find_event_payload(player1: Any, player2: Any, date_only: str) -> Optional[Dict[str, Any]]:
    key = _event_key(date_only, player1, player2)
    direct_path = EVENTS_DIR / f"{key}.json"
    if direct_path.exists():
        return _load_event_file(direct_path)
    if not EVENTS_DIR.exists():
        return None
    best_payload = None
    best_score = 0.0
    for path in EVENTS_DIR.glob(f"{str(date_only)[:10]}_*.json"):
        payload = _load_event_file(path)
        p1, p2 = payload.get("player1"), payload.get("player2")
        direct = (_name_score(player1, p1) + _name_score(player2, p2)) / 2.0
        reverse = (_name_score(player1, p2) + _name_score(player2, p1)) / 2.0
        score = max(direct, reverse)
        if score > best_score:
            best_score = score
            best_payload = payload
    return best_payload if best_score >= 0.74 else None


def _side_for_pick(payload: Dict[str, Any], pick: Any) -> Optional[str]:
    pick_text = str(pick or "")
    p1, p2 = payload.get("player1"), payload.get("player2")
    if _name_score(pick_text, p1) >= 0.74:
        return "player1"
    if _name_score(pick_text, p2) >= 0.74:
        return "player2"
    return None


def _implied_probability(odds: Optional[float]) -> Optional[float]:
    if odds is None or odds <= 1.0:
        return None
    return 100.0 / odds


def _select_baseline_snapshot(snapshots: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not snapshots:
        return None
    # Prefer a snapshot nearest to 72h before start, otherwise use earliest.
    with_hours = [s for s in snapshots if _as_float(s.get("hours_to_start")) is not None]
    if with_hours:
        valid = [s for s in with_hours if (_as_float(s.get("hours_to_start")) or 0) >= 6]
        pool = valid or with_hours
        return min(pool, key=lambda s: abs((_as_float(s.get("hours_to_start")) or 0) - 72.0))
    return snapshots[0]


def _move_signal(old_odds: float, new_odds: float) -> str:
    old_imp = _implied_probability(old_odds)
    new_imp = _implied_probability(new_odds)
    if old_imp is None or new_imp is None:
        return "Pending"
    diff = new_imp - old_imp
    if diff >= 1.0:
        return "Toward Pick"
    if diff <= -1.0:
        return "Against Pick"
    return "Stable"


def _clv_status(pp: Optional[float]) -> str:
    if pp is None:
        return "NO_SNAPSHOT"
    if pp >= 1.0:
        return "POSITIVE_CLV"
    if pp <= -1.0:
        return "NEGATIVE_CLV"
    return "FLAT_CLV"


def enrich_row_with_internal_marq(row: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(row)
    date_only = str(
        output.get("match_date") or output.get("date") or output.get("start_time_utc") or output.get("match_time_utc") or ""
    )[:10]
    if not date_only:
        return output
    payload = _find_event_payload(output.get("player1"), output.get("player2"), date_only)
    if not payload:
        output.setdefault("marq_internal_status", "NO_SNAPSHOT")
        return output
    side = _side_for_pick(payload, output.get("pick") or output.get("player"))
    if side not in {"player1", "player2"}:
        output.setdefault("marq_internal_status", "PICK_NOT_MATCHED")
        return output
    snapshots = [s for s in payload.get("snapshots", []) if isinstance(s, dict)]
    snapshots.sort(key=lambda item: str(item.get("snapshot_time_utc") or ""))
    if not snapshots:
        output.setdefault("marq_internal_status", "NO_SNAPSHOT")
        return output
    baseline = _select_baseline_snapshot(snapshots)
    latest = snapshots[-1]
    key = "odds_player1" if side == "player1" else "odds_player2"
    old_odds = _as_float(baseline.get(key) if baseline else None)
    latest_odds = _as_float(latest.get(key))
    current_odds = _as_float(output.get("marq_current_pick_odds") or output.get("pick_odds") or output.get("odds"))
    new_odds = current_odds or latest_odds
    if old_odds is None or new_odds is None:
        output.setdefault("marq_internal_status", "NO_ODDS")
        return output
    old_imp = _implied_probability(old_odds)
    new_imp = _implied_probability(new_odds)
    pp = round((new_imp or 0) - (old_imp or 0), 2) if old_imp is not None and new_imp is not None else None
    signal = _move_signal(old_odds, new_odds)
    status = _clv_status(pp)
    edge = _as_float(output.get("marq_edge_pct"))
    final = None
    if pp is not None:
        if pp <= -2.0:
            final = "Market Against Pick - Internal CLV"
        elif pp >= 2.0 and (edge is None or edge >= 0):
            final = "Market With Pick - Internal CLV"
        elif pp >= 2.0 and edge < 0:
            final = "Mixed Market - Internal CLV"
        elif abs(pp) < 1.0 and edge is not None and edge >= 5.0:
            final = "Market With Pick - Stable"
        elif abs(pp) < 1.0 and edge is not None and edge <= -2.0:
            final = "Market Against Pick - Stable"
        elif abs(pp) < 1.0:
            final = "Neutral - Stable"

    output.update({
        "marq_internal_status": status,
        "marq_internal_source": "TennisAPI_PRO snapshots",
        "marq_internal_event_key": payload.get("event_key"),
        "marq_internal_baseline_hours": baseline.get("hours_to_start") if baseline else None,
        "marq_internal_baseline_time_utc": baseline.get("snapshot_time_utc") if baseline else None,
        "marq_internal_latest_time_utc": latest.get("snapshot_time_utc"),
        "marq_internal_opening_pick_odds": round(old_odds, 4),
        "marq_internal_latest_pick_odds": round(new_odds, 4),
        "marq_internal_range": f"{old_odds:.2f} -> {new_odds:.2f}",
        "marq_internal_move_signal": signal,
        "marq_internal_clv_pp": pp,
        "marq_internal_clv_status": status,
        "marq_clv_pct": pp,
        "marq_clv_status": status,
    })
    if final:
        output["marq_final"] = final
        output["marq_final_display"] = final
    # Use internal movement to improve MarQ when provider movement is missing/flat.
    existing_move = str(output.get("marq_move_signal") or "").upper()
    if existing_move in {"", "UNKNOWN", "PENDING", "STABLE"}:
        output["marq_move_signal"] = signal
        output["marq_display_move_signal"] = signal
        output["marq_move_range"] = output["marq_internal_range"]
        output["marq_initial_pick_odds"] = output["marq_internal_opening_pick_odds"]
        output["marq_current_pick_odds"] = output["marq_internal_latest_pick_odds"]
        output["marq_movement_available"] = True
    return output


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Collect internal MARQ odds snapshots")
    parser.add_argument("--days-ahead", type=int, default=6)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--max-detail-events-per-day", type=int, default=80)
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = collect_horizon_snapshots(
        days_ahead=args.days_ahead,
        force_refresh=args.force_refresh,
        max_detail_events_per_day=args.max_detail_events_per_day,
    )
    print(json.dumps({
        "snapshot_count": summary.get("snapshot_count"),
        "date_counts": summary.get("date_counts"),
        "generated_at_utc": summary.get("generated_at_utc"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
