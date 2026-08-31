"""Export verified selected CloQ picks for the BlinQ Top daily picks modal."""
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
DEFAULT_OUTPUT = Path("blinq/data/top_daily_picks.json")


def first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def compact_pick(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(first_value(row, "event_id", "match_id", "id") or ""),
        "betting_day": row.get("betting_day"),
        "start_time": first_value(row, "match_start", "start_time"),
        "timezone": row.get("betting_day_timezone") or "Europe/Bratislava",
        "tour": first_value(row, "category", "level"),
        "tournament": row.get("tournament"),
        "surface": row.get("surface"),
        "player1": row.get("player1"),
        "player2": row.get("player2"),
        "pick": first_value(row, "cloq_pick", "pick"),
        "opponent": first_value(row, "cloq_opponent", "opponent"),
        "pick_odds": first_value(row, "cloq_pick_odds", "pick_odds"),
        "probability": first_value(row, "cloq_primary_probability", "thinq_pick_probability"),
        "data_depth": row.get("cloq_data_depth"),
        "score": row.get("cloq_score"),
        "tier": first_value(row, "cloq_publish_tier", "cloq_decision"),
        "support_tags": list(row.get("cloq_support_tags") or []),
        "risk_tags": list(row.get("cloq_risk_tags") or []),
        "model_version": row.get("cloq_model_version"),
    }


def load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("CloQ snapshot must be a JSON array")
    return [row for row in payload if isinstance(row, dict)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.input
    if source is None:
        source = next((path for path in DEFAULT_INPUTS if path.is_file()), None)
    if source is None or not source.is_file():
        raise SystemExit("latest_cloq.json not found")

    rows = load_rows(source)
    selected = [
        row for row in rows
        if row.get("cloq_selected") is True
        and row.get("cloq_publishable") is True
        and row.get("cloq_pick")
        and row.get("event_id") is not None
    ]
    selected.sort(key=lambda row: (int(row.get("cloq_rank") or 999999), str(row.get("match_start") or "")))

    seen: set[str] = set()
    picks: list[dict[str, Any]] = []
    for row in selected:
        item = compact_pick(row)
        if not item["event_id"] or item["event_id"] in seen:
            continue
        seen.add(item["event_id"])
        picks.append(item)

    days = sorted({str(item["betting_day"]) for item in picks if item.get("betting_day")})
    output = {
        "status": "OK" if picks else "NO_SELECTIONS",
        "source": "CLOQ_SELECTED_SNAPSHOT",
        "source_file": source.as_posix(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "betting_day": days[0] if len(days) == 1 else None,
        "timezone": "Europe/Bratislava",
        "count": len(picks),
        "picks": picks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Top daily picks exported: {len(picks)} from {source}")


if __name__ == "__main__":
    main()
