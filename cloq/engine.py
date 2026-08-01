from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .filters import CloQConfig, DEFAULT_CONFIG, FILTER_VERSION, config_to_dict, filter_cloq_rows


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _row_key(row: Dict[str, Any]) -> str:
    for key in ("event_id", "match_id", "id"):
        value = row.get(key)
        if value is not None:
            return f"id:{value}"
    p1 = str(row.get("player1") or row.get("pick") or "").strip().lower()
    p2 = str(row.get("player2") or row.get("opponent") or "").strip().lower()
    start = str(row.get("match_start") or row.get("start_time") or "")
    return f"fallback:{p1}:{p2}:{start}"


def load_source_rows(outputs_dir: Path) -> List[Dict[str, Any]]:
    """Load CorQ source rows without duplicating latest_top7 rows."""
    all_rows = _read_json(outputs_dir / "latest_all.json", [])
    top7_rows = _read_json(outputs_dir / "latest_top7.json", [])
    if not isinstance(all_rows, list):
        all_rows = []
    if not isinstance(top7_rows, list):
        top7_rows = []

    merged: Dict[str, Dict[str, Any]] = {}
    for row in all_rows:
        if isinstance(row, dict):
            merged[_row_key(row)] = dict(row)
    # Top7 can contain fields added later in pipeline. Merge over all rows.
    for row in top7_rows:
        if isinstance(row, dict):
            key = _row_key(row)
            base = merged.get(key, {})
            base.update(row)
            merged[key] = base
    return list(merged.values())


def build_manifest(source_rows: List[Dict[str, Any]], passed: List[Dict[str, Any]], rejected: List[Dict[str, Any]], config: CloQConfig) -> Dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()

    for row in rejected:
        for reason in row.get("cloq_reasons") or []:
            reason_counts[str(reason)] += 1
    for row in passed + rejected:
        for warning in row.get("cloq_warnings") or []:
            warning_counts[str(warning)] += 1
        for tag in row.get("cloq_tags") or []:
            tag_counts[str(tag)] += 1

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_rows": len(source_rows),
        "passed_rows": len(passed),
        "rejected_rows": len(rejected),
        "filter_version": FILTER_VERSION,
        "config": config_to_dict(config),
        "reason_counts": dict(reason_counts.most_common()),
        "warning_counts": dict(warning_counts.most_common()),
        "tag_counts": dict(tag_counts.most_common()),
    }


def run(outputs_dir: Path, config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    source_rows = load_source_rows(outputs_dir)
    passed, rejected = filter_cloq_rows(source_rows, config)
    manifest = build_manifest(source_rows, passed, rejected, config)

    _write_json(outputs_dir / "latest_cloq.json", passed)
    _write_json(outputs_dir / "latest_cloq_rejected.json", rejected)
    _write_json(outputs_dir / "latest_cloq_manifest.json", manifest)
    return manifest


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate CloQ close-odds shortlist outputs.")
    parser.add_argument("--outputs-dir", default="outputs", help="Directory containing latest_all.json/latest_top7.json")
    args = parser.parse_args(argv)

    manifest = run(Path(args.outputs_dir), DEFAULT_CONFIG)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
