"""Build value-first CloQ output from CorQ ALL rows.

Usage:
    python -m cloq.engine --input outputs/latest_all.json --output-root outputs

Outputs:
    outputs/cloq/latest_cloq.json
    outputs/latest_cloq.json
    outputs/cloq/latest_cloq_manifest.json

This engine reads only real upstream fields. It does not call APIs and does not
create synthetic odds, probabilities or value fields.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cloq.filters import annotate_cloq, cloq_score, match_identity

DEFAULT_TOP_N = 20


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "picks", "all", "data", "records"):
            value = obj.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def dedupe_best_by_match(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        key = match_identity(row)
        if key not in best:
            best[key] = row
            order.append(key)
            continue
        current_score = float(best[key].get("cloq_score") or -9999.0)
        new_score = float(row.get("cloq_score") or -9999.0)
        if new_score > current_score:
            best[key] = row
    return [best[key] for key in order]


def build_cloq_rows(all_rows: Iterable[Dict[str, Any]], top_n: int = DEFAULT_TOP_N) -> List[Dict[str, Any]]:
    annotated = [annotate_cloq(row) for row in all_rows if isinstance(row, dict)]
    publishable = [row for row in annotated if row.get("cloq_publishable") is True]
    publishable = dedupe_best_by_match(publishable)
    publishable = sorted(
        publishable,
        key=lambda row: (
            float(row.get("cloq_score") or -9999.0),
            float(row.get("cloq_value_delta_pp") or -9999.0),
            float(row.get("cloq_expected_value_pct") or -9999.0),
            float(row.get("cloq_corq_probability") or 0.0),
        ),
        reverse=True,
    )
    output = publishable[: max(int(top_n or DEFAULT_TOP_N), 1)]
    for idx, row in enumerate(output, start=1):
        row["cloq_rank"] = idx
        row["cloq_selected"] = True
        row["cloq_score"] = cloq_score(row)
    return output


def build_manifest(input_path: Path, output_rows: List[Dict[str, Any]], all_count: int, top_n: int) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    bucket_counts: Dict[str, int] = {}
    for row in output_rows:
        status = str(row.get("cloq_value_status") or "UNKNOWN")
        bucket = str(row.get("cloq_odds_gap_bucket") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    return {
        "model": "CLOQ_VALUE_FIRST_V3_HIGH_VALUE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "input_rows": all_count,
        "output_rows": len(output_rows),
        "top_n": top_n,
        "value_status_counts": status_counts,
        "odds_gap_bucket_counts": bucket_counts,
        "notes": [
            "Value is the primary CloQ signal. V3 requires a playable positive edge instead of neutral/slight value.",
            "Close odds are a soft bonus only: <=15% gets +3.0, <=25% gets +1.5, <=40% is neutral.",
            "No wide-odds penalty is applied in this version.",
            "No synthetic odds, probabilities or value values are generated.",
        ],
    }


def run(input_path: Optional[str] = None, output_root: str = "outputs", top_n: int = DEFAULT_TOP_N) -> Dict[str, Any]:
    root = Path(output_root)
    input_file = Path(input_path) if input_path else root / "latest_all.json"
    all_rows = json_rows(read_json(input_file, []))
    cloq_rows = build_cloq_rows(all_rows, top_n=top_n)

    cloq_dir = root / "cloq"
    latest_nested = cloq_dir / "latest_cloq.json"
    latest_flat = root / "latest_cloq.json"
    manifest_path = cloq_dir / "latest_cloq_manifest.json"

    write_json(latest_nested, cloq_rows)
    write_json(latest_flat, cloq_rows)
    manifest = build_manifest(input_file, cloq_rows, len(all_rows), top_n)
    write_json(manifest_path, manifest)
    return {
        "rows": len(cloq_rows),
        "input_rows": len(all_rows),
        "latest_cloq": str(latest_nested),
        "latest_cloq_flat": str(latest_flat),
        "manifest": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build value-first CloQ output")
    parser.add_argument("--input", dest="input_path", default=None, help="Input ALL JSON path, default outputs/latest_all.json")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="Number of CloQ rows to publish")
    args = parser.parse_args()
    result = run(input_path=args.input_path, output_root=args.output_root, top_n=args.top_n)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
