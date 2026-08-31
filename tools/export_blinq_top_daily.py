"""Export verified CloQ and BlinQ daily snapshots for the BlinQ portal.

No selection is invented. CloQ requires cloq_selected + cloq_publishable.
BlinQ requires an already valid embedded BlinQ PREDICTION and explicit selection.
Results are read only from an optional settled snapshot.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INPUTS = (
    Path("outputs/cloq/latest_cloq.json"),
    Path("cloq/latest_cloq.json"),
    Path("latest_cloq.json"),
)
DEFAULT_RESULTS = Path("blinq/data/top_daily_results.json")
DEFAULT_OUTPUT = Path("blinq/data/top_daily_picks.json")


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def base(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(first(row, "event_id", "match_id", "id") or ""),
        "betting_day": row.get("betting_day"),
        "start_time": first(row, "match_start", "start_time"),
        "timezone": row.get("betting_day_timezone") or "Europe/Bratislava",
        "tour": first(row, "category", "level"),
        "tournament": row.get("tournament"),
        "surface": row.get("surface"),
        "player1": row.get("player1"),
        "player2": row.get("player2"),
    }


def cloq_item(row: dict[str, Any]) -> dict[str, Any]:
    item = base(row)
    item.update({
        "model": "CLOQ",
        "pick": first(row, "cloq_pick", "pick"),
        "opponent": first(row, "cloq_opponent", "opponent"),
        "pick_odds": first(row, "cloq_pick_odds", "pick_odds"),
        "probability": first(row, "cloq_primary_probability", "thinq_pick_probability"),
        "data_depth": row.get("cloq_data_depth"),
        "score": row.get("cloq_score"),
        "tier": first(row, "cloq_publish_tier", "cloq_decision"),
        "support_tags": list(row.get("cloq_support_tags") or []),
        "risk_tags": list(row.get("cloq_risk_tags") or []),
    })
    return item


def blinq_item(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = row.get("blinq") if isinstance(row.get("blinq"), dict) else {}
    status = str(first(payload, "prediction_status", "blinq_prediction_status") or first(row, "blinq_prediction_status") or "").upper()
    winner = first(payload, "winner", "blinq_winner") or first(row, "blinq_winner")
    selected = row.get("blinq_selected") is True or payload.get("selected") is True
    if status != "PREDICTION" or not winner or not selected:
        return None
    item = base(row)
    item.update({
        "model": "BLINQ",
        "pick": winner,
        "opponent": row.get("player2") if winner == row.get("player1") else row.get("player1"),
        "pick_odds": None,
        "probability": first(payload, "winner_probability", "blinq_probability") or row.get("blinq_probability"),
        "data_depth": first(payload, "data_depth", "blinq_data_depth"),
        "score": None,
        "tier": "BLINQ DAILY",
        "support_tags": list(payload.get("flags") or row.get("blinq_flags") or []),
        "risk_tags": [],
    })
    return item


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = item.get("event_id") or f"{item.get('player1')}|{item.get('player2')}|{item.get('start_time')}"
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def read_results(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "NO_RESULTS", "models": {"BLINQ": [], "CLOQ": []}, "summary": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {"status": "NO_RESULTS", "models": {"BLINQ": [], "CLOQ": []}, "summary": {}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.input or next((path for path in DEFAULT_INPUTS if path.is_file()), None)
    if source is None or not source.is_file():
        raise SystemExit("latest_cloq.json not found")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("CloQ snapshot must be a JSON array")
    rows = [row for row in raw if isinstance(row, dict)]

    cloq_rows = [row for row in rows if row.get("cloq_selected") is True and row.get("cloq_publishable") is True and row.get("cloq_pick")]
    cloq_rows.sort(key=lambda row: (int(row.get("cloq_rank") or 999999), str(row.get("match_start") or "")))
    cloq = dedupe([cloq_item(row) for row in cloq_rows])
    blinq = dedupe([item for row in rows if (item := blinq_item(row)) is not None])
    days = sorted({str(item["betting_day"]) for item in cloq + blinq if item.get("betting_day")})

    output = {
        "status": "OK" if cloq or blinq else "NO_SELECTIONS",
        "source": "VERIFIED_DAILY_SNAPSHOTS",
        "source_file": source.as_posix(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "betting_day": days[0] if len(days) == 1 else None,
        "timezone": "Europe/Bratislava",
        "models": {"BLINQ": blinq, "CLOQ": cloq},
        "counts": {"BLINQ": len(blinq), "CLOQ": len(cloq)},
        "results": read_results(args.results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Daily export: BlinQ={len(blinq)} CloQ={len(cloq)}")


if __name__ == "__main__":
    main()
