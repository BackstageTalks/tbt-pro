from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR, fetch_api: bool = False) -> Dict[str, Any]:
    corq_payload, corq_rows, corq_source = load_source_rows("corq")
    cloq_payload, cloq_rows, cloq_source = load_source_rows("cloq")
    audit_payload, audit_rows, audit_source = load_source_rows("audit")
    day = (run_date or run_date_from_payload(corq_payload, cloq_payload, audit_payload))[:10]

    old_corq = existing_index(json_rows(read_json(output_root / "latest_results_corq.json", [])))
    old_cloq = existing_index(json_rows(read_json(output_root / "latest_results_cloq.json", [])))
    old_audit = existing_index(json_rows(read_json(output_root / "latest_results_audit.json", [])))

    cache: Dict[int, Dict[str, Any]] = {}
    corq_results = [evaluate_row(r, "corq", day, corq_source, fetch_api, cache, old_corq.get(side_identity(r))) for r in corq_rows]
    cloq_results = [evaluate_row(r, "cloq", day, cloq_source, fetch_api, cache, old_cloq.get(side_identity(r))) for r in cloq_rows]
    audit_deduped = dedupe_match_rows(audit_rows)
    audit_results = [evaluate_row(r, "audit", day, audit_source, fetch_api, cache, old_audit.get(side_identity(r))) for r in audit_deduped]

    write_model_results("corq", corq_results, output_root, day)
    write_model_results("cloq", cloq_results, output_root, day)
    write_model_results("audit", audit_results, output_root, day)
    rebuild_indexes(output_root)

    manifest = {
        "generated_at": now_iso(),
        "date": day,
        "fetch_api": fetch_api,
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
        "output_root": str(output_root),
    }
    write_json(output_root / "latest_results_manifest.json", manifest)
    return manifest


def build_results(output_root: str = "outputs", run_date: Optional[str] = None, fetch_api: bool = False) -> Dict[str, Any]:
    return build_results_database(run_date=run_date, output_root=Path(output_root) / "results", fetch_api=fetch_api)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CorQ/CloQ/Audit results files")
    parser.add_argument("legacy_fetch_api", nargs="?", default=None, help="Backward-compatible true/false value")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", dest="run_date", default=None)
    parser.add_argument("--fetch-api", action="store_true")
    parser.add_argument("--sources", default="corq,cloq,audit", help="Backward-compatible no-op")
    args = parser.parse_args()
    legacy_fetch = str(args.legacy_fetch_api or "").strip().lower() in {"1", "true", "yes", "y", "on"}
    manifest = build_results(output_root=args.output_root, run_date=args.run_date, fetch_api=(args.fetch_api or legacy_fetch))
    print(manifest)


if __name__ == "__main__":
    main()
