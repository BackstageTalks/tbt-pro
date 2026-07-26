from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

OUTPUT_ROOT = Path("outputs")


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("rows", "items", "top7", "all", "results"):
            if isinstance(value.get(key), list):
                return [x for x in value[key] if isinstance(x, dict)]
    return []


def _norm_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def _prob(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_estimated_win_probability", "corq_probability", "win_probability", "corq_score"):
        v = _num(row.get(key), None)
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    return None


def _odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "odds", "selected_odds"):
        v = _num(row.get(key), None)
        if v is not None:
            return v
    return None


def _status(row: Dict[str, Any]) -> str:
    raw = row.get("status") or row.get("status_type") or row.get("match_status_type")
    if not raw and isinstance(row.get("raw"), dict):
        raw = ((row.get("raw") or {}).get("status") or {}).get("type")
    return str(raw or "").strip().lower().replace(" ", "_")


def _winner(row: Dict[str, Any]) -> str:
    winner = row.get("winner") or row.get("match_winner")
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if not winner and raw:
        winner_code = raw.get("winnerCode")
        if winner_code == 1 and isinstance(raw.get("homeTeam"), dict):
            winner = raw["homeTeam"].get("name")
        elif winner_code == 2 and isinstance(raw.get("awayTeam"), dict):
            winner = raw["awayTeam"].get("name")
    return str(winner or "").strip()


def _score(row: Dict[str, Any]) -> str:
    for key in ("score", "result_score", "final_score"):
        if row.get(key):
            return str(row[key])
    return ""


def _flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("flags", "corq_risk_flags", "corq_warning_flags", "thinq_flags", "top7_quality_reject_reasons"):
        value = row.get(key)
        if isinstance(value, list):
            out.extend(str(x) for x in value if x)
        elif value:
            out.append(str(value))
    return sorted(set(out))


def _evaluate_row(row: Dict[str, Any], source_snapshot: str, run_date: str) -> Dict[str, Any]:
    pick = str(row.get("pick") or row.get("player") or "").strip()
    opponent = str(row.get("opponent") or row.get("opp") or "").strip()
    winner = _winner(row)
    status = _status(row)
    odds = _odds(row)

    result = "PENDING"
    units: Optional[float] = None
    if status in {"finished", "ended", "complete", "completed"} or winner:
        if winner and _norm_name(winner) == _norm_name(pick):
            result = "WON"
            units = round((odds or 1.0) - 1.0, 4) if odds else None
        elif winner:
            result = "LOST"
            units = -1.0
    elif status in {"cancelled", "canceled", "postponed", "walkover", "retired"}:
        result = "VOID"
        units = 0.0

    return {
        "date": run_date,
        "source_snapshot": source_snapshot,
        "match_id": row.get("match_id") or row.get("event_id") or row.get("id"),
        "custom_id": row.get("event_custom_id") or row.get("customId"),
        "pick": pick,
        "opponent": opponent,
        "pick_odds": odds,
        "opponent_odds": row.get("opponent_odds") or row.get("opp_odds"),
        "corq_probability": _prob(row),
        "thinq_confidence": row.get("thinq_confidence") or row.get("thinq_probability_confidence"),
        "pick_thinq_edge": row.get("top7_pick_thinq_edge") or row.get("pick_thinq_edge") or row.get("thinq_edge"),
        "stat_data_depth": row.get("stat_data_depth") or row.get("pick_data_depth"),
        "form_data_depth": row.get("form_data_depth") or row.get("thinq_form_confidence"),
        "status": status or "unknown",
        "winner": winner,
        "score": _score(row),
        "result": result,
        "units": units,
        "tags": _flags(row),
        "sets_games": {
            "projected_sets": row.get("thinq_projected_sets"),
            "projected_games": row.get("thinq_projected_games"),
            "three_sets_probability": row.get("thinq_decider_probability"),
            "tie_break_probability": row.get("thinq_tiebreak_probability"),
        },
        "raw_snapshot_row": row,
    }


def _summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
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


def build_results(output_root: str = "outputs", run_date: Optional[str] = None) -> Dict[str, Any]:
    root = Path(output_root)
    day = (run_date or date.today().isoformat())[:10]
    year = day[:4]

    corq_snapshot = _as_list(_load_json(root / "snapshots" / "latest_corq_top7_snapshot.json", []))
    all_snapshot = _as_list(_load_json(root / "snapshots" / "latest_all_audit_snapshot.json", []))
    if not corq_snapshot:
        corq_snapshot = _as_list(_load_json(root / "latest_top7.json", []))
    if not all_snapshot:
        all_snapshot = _as_list(_load_json(root / "latest_all.json", []))

    corq_results = [_evaluate_row(r, "CORQ_TOP7", day) for r in corq_snapshot]
    all_results = [_evaluate_row(r, "ALL_AUDIT", day) for r in all_snapshot]

    corq_payload = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "section": "CorQ TOP7 Results",
        "summary": _summary(corq_results),
        "rows": corq_results,
    }
    all_payload = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "section": "ALL Results Audit",
        "summary": _summary(all_results),
        "rows": all_results,
    }

    corq_dir = root / "results" / "corq" / year
    all_dir = root / "results" / "all" / year
    corq_dir.mkdir(parents=True, exist_ok=True)
    all_dir.mkdir(parents=True, exist_ok=True)
    (corq_dir / f"results_corq_{day}.json").write_text(json.dumps(corq_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (all_dir / f"results_all_{day}.json").write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "results" / "latest_results_corq.json").write_text(json.dumps(corq_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "results" / "latest_results_all.json").write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"corq": corq_payload, "all": all_payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CorQ/ALL results foundation JSON files.")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", dest="run_date", default=None)
    args = parser.parse_args()
    payload = build_results(output_root=args.output_root, run_date=args.run_date)
    print("Results foundation built:", payload["corq"]["summary"], payload["all"]["summary"])


if __name__ == "__main__":
    main()
