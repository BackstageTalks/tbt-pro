from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
RESULTS_DIR = OUTPUTS / "results"
SNAPSHOTS_DIR = OUTPUTS / "snapshots"


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[results_db] failed to read {path}: {exc}")
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "picks", "cloq", "records", "results", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def pick_name(row: Dict[str, Any]) -> str:
    return str(row.get("pick") or row.get("cloq_pick") or row.get("player") or row.get("player1") or row.get("home") or "").strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(row.get("opponent") or row.get("opp") or row.get("player2") or row.get("away") or "").strip()


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "cloq_pick_odds", "selected_odds", "odds_decimal", "decimal_odds", "odds"):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return val
    return None


def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability", "cloq_probability"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def run_date_from_payload(*payloads: Any) -> str:
    for payload in payloads:
        if isinstance(payload, dict):
            for key in ("run_date", "snapshot_date", "date", "generated_for", "updated_at", "generated_at"):
                value = payload.get(key)
                if value:
                    txt = str(value)[:10]
                    if re.match(r"^20\d{2}-\d{2}-\d{2}$", txt):
                        return txt
    return date.today().isoformat()


def row_date(row: Dict[str, Any], default: str) -> str:
    for key in ("date", "snapshot_date", "run_date", "match_date"):
        value = row.get(key)
        if value:
            txt = str(value)[:10]
            if re.match(r"^20\d{2}-\d{2}-\d{2}$", txt):
                return txt
    return default


def match_identity(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_id", "match_id", "custom_id", "customId", "id"):
        value = row.get(key)
        if value:
            return f"id:{value}"
    names = sorted([normalize_name(pick_name(row)), normalize_name(opponent_name(row))])
    t = str(row.get("start_time") or row.get("match_time") or row.get("start_time_utc") or "")[:16]
    return "pair:" + "|".join(names) + "|" + t


def side_identity(row: Dict[str, Any]) -> str:
    return match_identity(row) + "|pick:" + normalize_name(pick_name(row))


def result_status_text(row: Dict[str, Any]) -> str:
    return str(row.get("result") or row.get("result_status") or row.get("status") or row.get("match_status") or "").upper()


def is_void_status(row: Dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("result", "result_status", "status", "match_status", "event_status", "score", "final_score", "reason")
    ).upper()
    void_tokens = ("RET", "RETIRED", "RETIREMENT", "SCR", "SCRATCH", "WALKOVER", "WO", "ABANDON", "CANCEL", "CANCELED", "CANCELLED", "VOID")
    return any(token in text for token in void_tokens)


def parse_tennis_score_sets(score: Any) -> List[Tuple[int, int]]:
    text = str(score or "").strip()
    if not text:
        return []
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    pairs: List[Tuple[int, int]] = []
    for a, b in re.findall(r"(\d{1,2})\s*[-:]\s*(\d{1,2})", text):
        try:
            pairs.append((int(a), int(b)))
        except Exception:
            continue
    return pairs


def tennis_set_is_complete(a: int, b: int) -> bool:
    hi = max(a, b)
    lo = min(a, b)
    diff = abs(a - b)
    if hi < 6:
        return False
    if hi == 6:
        return diff >= 2
    if hi == 7:
        return lo in {5, 6}
    return diff >= 2


def score_indicates_unfinished_tennis_match(score: Any) -> bool:
    sets = parse_tennis_score_sets(score)
    if not sets:
        return False
    home_sets = 0
    away_sets = 0
    for a, b in sets:
        if not tennis_set_is_complete(a, b):
            return True
        if a > b:
            home_sets += 1
        elif b > a:
            away_sets += 1
    return max(home_sets, away_sets) < 2


def infer_result(row: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[float]]:
    merged = dict(row)
    if existing:
        merged.update({k: v for k, v in existing.items() if v not in (None, "")})

    winner = str(merged.get("winner") or "").strip()
    score = merged.get("score") or merged.get("final_score")

    # VOID must have priority over explicit/winner-based settlement.
    if is_void_status(merged) or (winner and score_indicates_unfinished_tennis_match(score)):
        return "VOID", 0.0

    explicit = result_status_text(merged)
    if explicit in {"WON", "WIN"}:
        odds = pick_odds(merged)
        return "WON", round((odds or 1.0) - 1.0, 2)
    if explicit in {"LOST", "LOSS"}:
        return "LOST", -1.0
    if explicit == "VOID":
        return "VOID", 0.0
    if winner:
        if normalize_name(winner) == normalize_name(pick_name(merged)):
            odds = pick_odds(merged)
            return "WON", round((odds or 1.0) - 1.0, 2)
        return "LOST", -1.0
    return "PENDING", None

def row_score(row: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
    publish = 1.0 if row.get("top7_publishable") or row.get("eligible_for_top7") else 0.0
    return (
        publish,
        as_float(row.get("corq_adjusted_score"), 0.0) or 0.0,
        as_float(probability(row), 0.0) or 0.0,
        as_float(row.get("stat_data_depth") or row.get("pick_data_depth"), 0.0) or 0.0,
        as_float(pick_odds(row), 0.0) or 0.0,
    )


def dedupe_match_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        key = match_identity(row)
        if key not in by_key:
            by_key[key] = row
            order.append(key)
        else:
            if row_score(row) > row_score(by_key[key]):
                by_key[key] = row
    return [by_key[k] for k in order]


def existing_index(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        out[side_identity(row)] = row
    return out


def enrich_result_row(row: Dict[str, Any], model: str, default_date: str, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = dict(row)
    if existing:
        # Preserve fetched result fields from previous run, but do not overwrite current model fields unless missing.
        for key in ("winner", "score", "final_score", "actual_sets", "actual_games", "actual_tiebreak", "source", "result_source"):
            if existing.get(key) not in (None, "") and out.get(key) in (None, ""):
                out[key] = existing.get(key)
        if existing.get("status") not in (None, "") and out.get("status") in (None, ""):
            out["status"] = existing.get("status")
    status, units = infer_result(out, existing=existing)
    out["date"] = row_date(out, default_date)
    out["model"] = model
    out["result_status"] = status
    out["status"] = status
    out["units"] = units
    out["match_identity"] = match_identity(out)
    out["side_identity"] = side_identity(out)
    out.setdefault("pick", pick_name(out))
    out.setdefault("opponent", opponent_name(out))
    return out


def load_source_rows(kind: str) -> Tuple[Any, List[Dict[str, Any]]]:
    if kind == "corq":
        for path in (SNAPSHOTS_DIR / "latest_corq_top7_snapshot.json", OUTPUTS / "latest_top7.json"):
            payload = read_json(path, None)
            rows = json_rows(payload)
            if rows:
                return payload, rows
    if kind == "cloq":
        for path in (SNAPSHOTS_DIR / "latest_cloq_snapshot.json", OUTPUTS / "latest_cloq.json"):
            payload = read_json(path, None)
            rows = json_rows(payload)
            if rows:
                return payload, rows
    if kind == "audit":
        for path in (SNAPSHOTS_DIR / "latest_all_audit_snapshot.json", OUTPUTS / "latest_audit.json"):
            payload = read_json(path, None)
            rows = json_rows(payload)
            if rows:
                return payload, rows
    return {}, []


def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR) -> Dict[str, Any]:
    corq_payload, corq_rows = load_source_rows("corq")
    cloq_payload, cloq_rows = load_source_rows("cloq")
    audit_payload, audit_rows = load_source_rows("audit")
    day = run_date or run_date_from_payload(corq_payload, cloq_payload, audit_payload)

    old_corq = existing_index(json_rows(read_json(output_root / "latest_results_corq.json", [])))
    old_cloq = existing_index(json_rows(read_json(output_root / "latest_results_cloq.json", [])))
    old_audit = existing_index(json_rows(read_json(output_root / "latest_results_audit.json", [])))

    corq_results = [enrich_result_row(r, "corq", day, old_corq.get(side_identity(r))) for r in corq_rows]
    cloq_results = [enrich_result_row(r, "cloq", day, old_cloq.get(side_identity(r))) for r in cloq_rows]
    audit_deduped = dedupe_match_rows(audit_rows)
    audit_results = [enrich_result_row(r, "audit", day, old_audit.get(side_identity(r))) for r in audit_deduped]

    year, month = day[:4], day[5:7]
    month_dir = output_root / year / month

    write_json(output_root / "latest_results_corq.json", corq_results)
    write_json(output_root / "latest_results_cloq.json", cloq_results)
    write_json(output_root / "latest_results_audit.json", audit_results)

    write_json(month_dir / f"{day}_corq.json", corq_results)
    write_json(month_dir / f"{day}_cloq.json", cloq_results)
    write_json(month_dir / f"{day}_audit.json", audit_results)

    rebuild_indexes(output_root)
    return {
        "generated_at": now_iso(),
        "date": day,
        "corq_count": len(corq_results),
        "cloq_count": len(cloq_results),
        "audit_count": len(audit_results),
        "output_root": str(output_root),
    }


def rebuild_indexes(output_root: Path = RESULTS_DIR) -> None:
    years: List[str] = []
    latest_date: Optional[str] = None
    for year_dir in sorted([p for p in output_root.iterdir() if p.is_dir() and re.match(r"^20\d{2}$", p.name)]):
        years.append(year_dir.name)
        months: List[str] = []
        for month_dir in sorted([p for p in year_dir.iterdir() if p.is_dir() and re.match(r"^\d{2}$", p.name)]):
            months.append(month_dir.name)
            dates = sorted({p.name[:10] for p in month_dir.glob("20??-??-??_*.json")})
            if dates:
                latest_date = max(latest_date or dates[-1], dates[-1])
            write_json(month_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "month": month_dir.name, "dates": dates})
        write_json(year_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "months": months})
    write_json(
        output_root / "index.json",
        {
            "generated_at": now_iso(),
            "years": years,
            "latest_date": latest_date,
            "latest": {
                "corq": "latest_results_corq.json",
                "cloq": "latest_results_cloq.json",
                "audit": "latest_results_audit.json",
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build persistent CorQ/CloQ/Audit results database")
    parser.add_argument("--date", dest="run_date", default=None, help="Run date YYYY-MM-DD")
    parser.add_argument("--output-root", default=str(RESULTS_DIR), help="Results output root")
    args = parser.parse_args()
    manifest = build_results_database(run_date=args.run_date, output_root=Path(args.output_root))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
