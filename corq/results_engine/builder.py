from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from .common import (
    as_float,
    dedupe_match_rows,
    flags,
    json_rows,
    match_identity,
    normalize_name,
    now_iso,
    opponent_name,
    opponent_odds,
    pick_name,
    pick_odds,
    probability,
    read_json,
    row_date,
    run_date_from_payload,
    side_identity,
    write_json,
)
from .provider import event_id, fetch_event_detail, score_from_event, status_from_obj, winner_from_event

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
RESULTS_DIR = OUTPUTS / "results"
SNAPSHOTS_DIR = OUTPUTS / "snapshots"


def existing_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {side_identity(row): row for row in rows if isinstance(row, dict)}


def source_candidates(kind: str) -> List[Path]:
    if kind == "corq":
        return [
            SNAPSHOTS_DIR / "latest_corq_top7_snapshot.json",
            OUTPUTS / "latest_top7.json",
        ]
    if kind == "cloq":
        return [
            SNAPSHOTS_DIR / "latest_cloq_snapshot.json",
            OUTPUTS / "latest_cloq.json",
        ]
    return [
        SNAPSHOTS_DIR / "latest_all_audit_snapshot.json",
        OUTPUTS / "latest_audit.json",
        OUTPUTS / "latest_all.json",
    ]


def load_source_rows(kind: str) -> Tuple[Any, List[Dict[str, Any]], str]:
    for path in source_candidates(kind):
        payload = read_json(path, None)
        rows = json_rows(payload)
        if rows:
            return payload, rows, str(path)
    return {}, [], ""


def snapshot_status(row: Dict[str, Any]) -> str:
    raw = row.get("status") or row.get("status_type") or row.get("match_status_type") or row.get("event_status")
    if not raw and isinstance(row.get("raw"), dict):
        raw = ((row.get("raw") or {}).get("status") or {}).get("type")
    return status_from_obj(raw)


def snapshot_winner(row: Dict[str, Any]) -> str:
    winner = row.get("winner") or row.get("match_winner")
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if not winner and raw:
        winner = winner_from_event(raw)
    return str(winner or "").strip()


def snapshot_score(row: Dict[str, Any]) -> Tuple[str, Optional[int], Optional[int], bool]:
    for key in ("score", "result_score", "final_score"):
        if row.get(key):
            return str(row[key]), None, None, False
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if raw:
        return score_from_event(raw)
    return "", None, None, False


def is_void_status(*values: Any) -> bool:
    text = " ".join(str(v or "") for v in values).upper()
    void_tokens = (
        "RET", "RETIRED", "RETIREMENT", "SCR", "SCRATCH", "WALKOVER", "WO",
        "ABANDON", "CANCEL", "CANCELED", "CANCELLED", "VOID", "POSTPONED",
    )
    return any(token in text for token in void_tokens)


def result_from_winner(row: Dict[str, Any], winner: str, status: str) -> Tuple[str, Optional[float]]:
    if is_void_status(status, winner, row.get("score"), row.get("final_score")):
        return "VOID", 0.0
    if winner:
        if normalize_name(winner) == normalize_name(pick_name(row)):
            odds = pick_odds(row)
            return "WON", round((odds or 1.0) - 1.0, 4) if odds else None
        return "LOST", -1.0
    explicit = str(row.get("result") or row.get("result_status") or "").upper()
    if explicit in {"WON", "WIN"}:
        odds = pick_odds(row)
        return "WON", round((odds or 1.0) - 1.0, 4) if odds else None
    if explicit in {"LOST", "LOSS"}:
        return "LOST", -1.0
    if explicit == "VOID":
        return "VOID", 0.0
    if status in {"cancelled", "canceled", "postponed", "walkover", "retired", "abandoned"}:
        return "VOID", 0.0
    return "PENDING", None


def preserve_existing(out: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> None:
    if not existing:
        return
    for key in (
        "winner", "score", "final_score", "actual_sets", "actual_games", "actual_tiebreak",
        "source", "result_source", "status", "result_status", "result", "units",
    ):
        if existing.get(key) not in (None, "") and out.get(key) in (None, ""):
            out[key] = existing.get(key)


def evaluate_row(
    row: Dict[str, Any],
    model: str,
    run_date: str,
    source_snapshot: str,
    fetch_api: bool,
    cache: Dict[int, Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = dict(row)
    preserve_existing(out, existing)

    status = snapshot_status(row)
    winner = snapshot_winner(row) or str(out.get("winner") or "").strip()
    score, actual_sets, actual_games, actual_tiebreak = snapshot_score(row)

    if out.get("score") and not score:
        score = str(out.get("score"))
    if out.get("actual_sets") is not None and actual_sets is None:
        actual_sets = int(as_float(out.get("actual_sets"), 0) or 0)
    if out.get("actual_games") is not None and actual_games is None:
        actual_games = int(as_float(out.get("actual_games"), 0) or 0)
    if out.get("actual_tiebreak") is not None:
        actual_tiebreak = bool(out.get("actual_tiebreak"))

    event_fetch_status = "NOT_REQUESTED"
    if fetch_api:
        eid = event_id(row)
        if eid is not None:
            event, event_fetch_status = fetch_event_detail(eid, cache)
            if event:
                status = status_from_obj(event.get("status"))
                winner = winner_from_event(event) or winner
                event_score, event_sets, event_games, event_tb = score_from_event(event)
                score = event_score or score
                actual_sets = event_sets if event_sets is not None else actual_sets
                actual_games = event_games if event_games is not None else actual_games
                actual_tiebreak = event_tb
        else:
            event_fetch_status = "NO_EVENT_ID"

    result, units = result_from_winner({**out, "winner": winner, "score": score, "status": status}, winner, status)
    projected_sets = as_float(out.get("ta_projected_sets") or out.get("thinq_projected_sets") or out.get("projected_sets"), None)
    projected_games = as_float(out.get("ta_projected_games") or out.get("thinq_projected_games") or out.get("projected_games"), None)
    games_error = round(actual_games - projected_games, 2) if actual_games is not None and projected_games is not None else None
    sets_hit = round(projected_sets) == actual_sets if actual_sets is not None and projected_sets is not None else None

    out.update({
        "date": row_date(out, run_date),
        "model": model,
        "source_snapshot": source_snapshot,
        "match_id": out.get("match_id") or out.get("event_id") or out.get("id"),
        "pick": pick_name(out),
        "opponent": opponent_name(out),
        "pick_odds": pick_odds(out),
        "opponent_odds": opponent_odds(out),
        "corq_probability": probability(out),
        "status": result,
        "result_status": result,
        "result": result,
        "winner": winner,
        "score": score,
        "final_score": score,
        "units": units,
        "actual_sets": actual_sets,
        "actual_games": actual_games,
        "actual_tiebreak": actual_tiebreak,
        "sets_hit": sets_hit,
        "games_error": games_error,
        "tags": flags(out),
        "event_fetch_status": event_fetch_status,
        "match_identity": match_identity(out),
        "side_identity": side_identity(out),
    })

    out["sets_games"] = {
        "projected_sets": projected_sets,
        "projected_games": projected_games,
        "actual_sets": actual_sets,
        "actual_games": actual_games,
        "sets_hit": sets_hit,
        "games_error": games_error,
        "actual_tiebreak": actual_tiebreak,
        "three_sets_probability": out.get("ta_decider_probability") or out.get("thinq_decider_probability"),
        "tie_break_probability": out.get("ta_tiebreak_probability") or out.get("thinq_tiebreak_probability"),
    }
    return out


def summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = sum(1 for r in rows if r.get("result") == "WON")
    lost = sum(1 for r in rows if r.get("result") == "LOST")
    pending = sum(1 for r in rows if r.get("result") == "PENDING")
    void = sum(1 for r in rows if r.get("result") == "VOID")
    settled = won + lost
    units = round(sum(float(r.get("units") or 0.0) for r in rows if r.get("units") is not None), 4)
    return {
        "picks": len(rows),
        "won": won,
        "lost": lost,
        "pending": pending,
        "void": void,
        "win_rate": round(won / settled, 4) if settled else None,
        "units": units,
        "roi": round(units / settled, 4) if settled else None,
    }


def write_model_results(model: str, rows: List[Dict[str, Any]], output_root: Path, run_date: str) -> None:
    year, month = run_date[:4], run_date[5:7]
    write_json(output_root / f"latest_results_{model}.json", rows)
    write_json(output_root / year / month / f"{run_date}_{model}.json", rows)


def rebuild_indexes(output_root: Path = RESULTS_DIR) -> None:
    years: List[str] = []
    latest_date: Optional[str] = None
    if not output_root.exists():
        return
    for year_dir in sorted([p for p in output_root.iterdir() if p.is_dir() and p.name.startswith("20")]):
        years.append(year_dir.name)
        months: List[str] = []
        for month_dir in sorted([p for p in year_dir.iterdir() if p.is_dir()]):
            months.append(month_dir.name)
            dates = sorted({p.name[:10] for p in month_dir.glob("20??-??-??_*.json")})
            if dates:
                latest_date = max(latest_date or dates[-1], dates[-1])
            write_json(month_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "month": month_dir.name, "dates": dates})
        write_json(year_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "months": months})
    write_json(output_root / "index.json", {
        "generated_at": now_iso(),
        "years": years,
        "latest_date": latest_date,
        "latest": {
            "corq": "latest_results_corq.json",
            "cloq": "latest_results_cloq.json",
            "audit": "latest_results_audit.json",
        },
    })




def local_yesterday(local_tz: str = "Europe/Bratislava") -> str:
    if ZoneInfo is not None:
        return (datetime.now(ZoneInfo(local_tz)).date() - timedelta(days=1)).isoformat()
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def row_start_datetime_utc(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("start_time_utc", "match_time_utc", "commence_time", "start_time", "match_time"):
        value = row.get(key)
        if not value:
            continue
        try:
            raw = str(value).strip()
            if re.match(r"^\d{10,13}$", raw):
                return datetime.fromtimestamp(int(raw[:10]), tz=timezone.utc)
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def should_fetch_result(row: Dict[str, Any], fetch_api: bool, settlement_grace_hours: float) -> bool:
    if not fetch_api:
        return False
    if settlement_grace_hours <= 0:
        return True
    start_dt = row_start_datetime_utc(row)
    if start_dt is None:
        return True
    return datetime.now(timezone.utc) >= start_dt + timedelta(hours=settlement_grace_hours)


def merge_rows_with_existing_for_settlement(source_rows: List[Dict[str, Any]], existing_rows: List[Dict[str, Any]], settle_date: str) -> List[Dict[str, Any]]:
    """Keep current source rows, plus existing rows for the settlement date.

    After midnight, latest snapshots can already be today's card while yesterday's
    pending bets still need settlement. This keeps yesterday's rows alive.
    """
    by_side: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in source_rows or []:
        key = side_identity(row)
        by_side[key] = row
        order.append(key)
    for row in existing_rows or []:
        if row_date(row, settle_date) != settle_date:
            continue
        key = side_identity(row)
        if key not in by_side:
            by_side[key] = row
            order.append(key)
    return [by_side[key] for key in order]

def lock_results_source_rows(model: str, source_rows: List[Dict[str, Any]], existing_rows: List[Dict[str, Any]], settle_date: str) -> Tuple[List[Dict[str, Any]], str]:
    """Keep result pick slates stable during build-results runs.

    The results workflow may update settlement fields on existing rows, but it
    must not replace the CorQ TOP7 picks with a newly generated latest snapshot.
    New pick slates are introduced by the pick-generation workflow, not by the
    results-settlement workflow.
    """
    if existing_rows:
        return existing_rows, "locked_existing_results"
    return source_rows, "source_snapshot_initial_seed"

def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR, fetch_api: bool = False, settle_date: Optional[str] = None, settlement_grace_hours: float = 0.0, local_tz: str = "Europe/Bratislava") -> Dict[str, Any]:
    corq_payload, corq_rows, corq_source = load_source_rows("corq")
    cloq_payload, cloq_rows, cloq_source = load_source_rows("cloq")
    audit_payload, audit_rows, audit_source = load_source_rows("audit")
    day = (settle_date or run_date or run_date_from_payload(corq_payload, cloq_payload, audit_payload))[:10]

    old_corq_rows = json_rows(read_json(output_root / "latest_results_corq.json", []))
    old_cloq_rows = json_rows(read_json(output_root / "latest_results_cloq.json", []))
    old_audit_rows = json_rows(read_json(output_root / "latest_results_audit.json", []))
    old_corq = existing_index(old_corq_rows)
    old_cloq = existing_index(old_cloq_rows)
    old_audit = existing_index(old_audit_rows)

    corq_rows, corq_lock_mode = lock_results_source_rows("corq", corq_rows, old_corq_rows, day)
    cloq_rows = merge_rows_with_existing_for_settlement(cloq_rows, old_cloq_rows, day)
    audit_rows = merge_rows_with_existing_for_settlement(audit_rows, old_audit_rows, day)

    cache: Dict[int, Dict[str, Any]] = {}
    corq_results = [evaluate_row(r, "corq", day, corq_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_corq.get(side_identity(r))) for r in corq_rows]
    cloq_results = [evaluate_row(r, "cloq", day, cloq_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_cloq.get(side_identity(r))) for r in cloq_rows]
    audit_deduped = dedupe_match_rows(audit_rows)
    audit_results = [evaluate_row(r, "audit", day, audit_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_audit.get(side_identity(r))) for r in audit_deduped]

    write_model_results("corq", corq_results, output_root, day)
    write_model_results("cloq", cloq_results, output_root, day)
    write_model_results("audit", audit_results, output_root, day)
    rebuild_indexes(output_root)

    manifest = {
        "generated_at": now_iso(),
        "date": day,
        "fetch_api": fetch_api,
        "settlement_grace_hours": settlement_grace_hours,
        "local_tz": local_tz,
        "corq_count": len(corq_results),
        "cloq_count": len(cloq_results),
        "audit_count": len(audit_results),
        "summary": {
            "corq": summary(corq_results),
            "cloq": summary(cloq_results),
            "audit": summary(audit_results),
        },
        "sources": {
            "corq": corq_source,
            "cloq": cloq_source,
            "audit": audit_source,
        },
        "locks": {
            "corq": corq_lock_mode,
        },
        "output_root": str(output_root),
    }
    write_json(output_root / "latest_results_manifest.json", manifest)
    return manifest


def build_results(output_root: str = "outputs", run_date: Optional[str] = None, fetch_api: bool = False, settle_date: Optional[str] = None, settlement_grace_hours: float = 0.0, local_tz: str = "Europe/Bratislava") -> Dict[str, Any]:
    return build_results_database(
        run_date=run_date,
        output_root=Path(output_root) / "results",
        fetch_api=fetch_api,
        settle_date=settle_date,
        settlement_grace_hours=settlement_grace_hours,
        local_tz=local_tz,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CorQ/CloQ/Audit results files")
    parser.add_argument("legacy_fetch_api", nargs="?", default=None, help="Backward-compatible true/false value")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", dest="run_date", default=None)
    parser.add_argument("--fetch-api", action="store_true")
    parser.add_argument("--settle-date", default=None, help="Explicit settlement date YYYY-MM-DD")
    parser.add_argument("--settle-yesterday", action="store_true", help="Evaluate yesterday in local timezone")
    parser.add_argument("--local-tz", default="Europe/Bratislava", help="Timezone used by --settle-yesterday")
    parser.add_argument("--settlement-grace-hours", type=float, default=0.0, help="Only fetch matches after start time plus this many hours")
    parser.add_argument("--sources", default="corq,cloq,audit", help="Backward-compatible no-op")
    args = parser.parse_args()
    legacy_fetch = str(args.legacy_fetch_api or "").strip().lower() in {"1", "true", "yes", "y", "on"}
    settle_date = args.settle_date
    if args.settle_yesterday and not settle_date:
        settle_date = local_yesterday(args.local_tz)
    manifest = build_results(
        output_root=args.output_root,
        run_date=args.run_date,
        fetch_api=(args.fetch_api or legacy_fetch),
        settle_date=settle_date,
        settlement_grace_hours=args.settlement_grace_hours,
        local_tz=args.local_tz,
    )
    print(manifest)


if __name__ == "__main__":
    main()
