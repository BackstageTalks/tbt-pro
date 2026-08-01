"""CloQ engine.

Reads CorQ prediction outputs, applies close-odds quality filters, and writes
an auditable CloQ output. Independent from main TOP7 selection.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from .filters import CloQConfig, evaluate_cloq_row
except Exception:
    from cloq.filters import CloQConfig, evaluate_cloq_row


def _load_json(path: Path) -> Any:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "matches", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _dedupe_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = (
            row.get("match_id") or row.get("event_id") or row.get("id"),
            row.get("pick"),
            row.get("opponent"),
            row.get("match_start") or row.get("start_time"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def build_cloq(outputs_dir: Path = Path("outputs"), config: CloQConfig = CloQConfig()) -> Dict[str, Any]:
    latest_all = _rows_from_payload(_load_json(outputs_dir / "latest_all.json"))
    latest_top7 = _rows_from_payload(_load_json(outputs_dir / "latest_top7.json"))
    source_rows = _dedupe_rows([*latest_all, *latest_top7])

    evaluated = [evaluate_cloq_row(row, config=config) for row in source_rows]
    passed = [row for row in evaluated if row.get("cloq_passed")]
    rejected = [row for row in evaluated if not row.get("cloq_passed")]
    passed.sort(key=lambda row: (row.get("cloq_score") or 0.0, row.get("corq_calibrated_probability") or 0.0), reverse=True)
    rejected.sort(key=lambda row: (row.get("cloq_score") or 0.0), reverse=True)

    reason_counts: Dict[str, int] = {}
    warning_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    for row in evaluated:
        for reason in row.get("cloq_reasons") or []:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for warning in row.get("cloq_warnings") or []:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
        for tag in row.get("cloq_tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_rows": len(source_rows),
        "passed_rows": len(passed),
        "rejected_rows": len(rejected),
        "filter_version": "CLOQ_FILTER_V1",
        "config": config.__dict__,
        "reason_counts": reason_counts,
        "warning_counts": warning_counts,
        "tag_counts": tag_counts,
    }
    return {"rows": passed, "rejected_rows": rejected, "manifest": manifest}


def write_cloq(outputs_dir: Path = Path("outputs"), config: CloQConfig = CloQConfig()) -> Dict[str, Any]:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    built = build_cloq(outputs_dir=outputs_dir, config=config)
    (outputs_dir / "latest_cloq.json").write_text(json.dumps(built["rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs_dir / "latest_cloq_rejected.json").write_text(json.dumps(built["rejected_rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs_dir / "latest_cloq_manifest.json").write_text(json.dumps(built["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
    return built["manifest"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CloQ close-odds output from CorQ predictions")
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument("--min-odds", type=float, default=1.70)
    parser.add_argument("--max-odds", type=float, default=2.60)
    parser.add_argument("--min-gap", type=float, default=0.10)
    parser.add_argument("--max-gap", type=float, default=0.25)
    parser.add_argument("--min-corq", type=float, default=0.55)
    parser.add_argument("--min-thinq", type=float, default=0.55)
    parser.add_argument("--min-marq", type=float, default=0.50)
    parser.add_argument("--min-form-depth", type=float, default=0.60)
    parser.add_argument("--min-stats-depth", type=float, default=0.40)
    args = parser.parse_args()
    config = CloQConfig(
        min_odds=args.min_odds,
        max_odds=args.max_odds,
        min_odd_gap_pct=args.min_gap,
        max_odd_gap_pct=args.max_gap,
        min_corq_probability=args.min_corq,
        min_thinq_probability=args.min_thinq,
        min_marq_probability=args.min_marq,
        min_form_depth=args.min_form_depth,
        min_stats_depth=args.min_stats_depth,
    )
    manifest = write_cloq(outputs_dir=Path(args.outputs_dir), config=config)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
