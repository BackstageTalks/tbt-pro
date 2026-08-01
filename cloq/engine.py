"""CloQ engine.

Builds CloQ close-odds shortlist from CorQ output JSON files.
Inputs:
  outputs/latest_all.json
  outputs/latest_top7.json
Outputs:
  outputs/latest_cloq.json
  outputs/latest_cloq_rejected.json
  outputs/latest_cloq_manifest.json

This module is intentionally tolerant to small API changes in cloq.filters:
filter_cloq_rows may return either (passed, rejected) or
(passed, rejected, extra_manifest). The engine normalizes both shapes.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from cloq.filters import (
    DEFAULT_CONFIG,
    FILTER_VERSION,
    config_to_dict,
    filter_cloq_rows,
)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _row_key(row: Dict[str, Any]) -> str:
    for key in ("match_id", "event_id", "id"):
        value = row.get(key)
        if value not in (None, ""):
            return f"id:{value}"
    p1 = str(row.get("player1") or row.get("home_player") or "").strip().lower()
    p2 = str(row.get("player2") or row.get("away_player") or "").strip().lower()
    start = str(row.get("match_start") or row.get("start_time") or "").strip()
    return f"match:{p1}|{p2}|{start}"


def _normalize_rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("rows", "matches", "items", "data"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    return []


def load_source_rows(outputs_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load inputs and return de-duplicated candidate rows.

    latest_all is preferred as the broad candidate source. latest_top7 is
    merged in as a safety net so Top7-only fields are not lost if latest_all
    is missing or partial.
    """
    latest_all_path = outputs_dir / "latest_all.json"
    latest_top7_path = outputs_dir / "latest_top7.json"

    latest_all = _normalize_rows(_read_json(latest_all_path, []))
    latest_top7 = _normalize_rows(_read_json(latest_top7_path, []))

    merged: Dict[str, Dict[str, Any]] = {}
    for row in latest_all:
        merged[_row_key(row)] = dict(row)
    for row in latest_top7:
        key = _row_key(row)
        if key in merged:
            # Preserve latest_all as base, but fill any missing fields from Top7.
            base = merged[key]
            for k, v in row.items():
                if base.get(k) in (None, "", [], {}):
                    base[k] = v
        else:
            merged[key] = dict(row)

    rows = list(merged.values())
    meta = {
        "latest_all_path": str(latest_all_path),
        "latest_top7_path": str(latest_top7_path),
        "latest_all_rows": len(latest_all),
        "latest_top7_rows": len(latest_top7),
        "source_rows": len(rows),
    }
    return rows, meta


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _count_many(rows: Iterable[Dict[str, Any]], field_names: Iterable[str]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for field in field_names:
            for item in _as_list(row.get(field)):
                if item not in (None, ""):
                    counter[str(item)] += 1
    return dict(counter)


def _normalize_filter_result(result: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Accept both 2-item and 3-item filter return shapes."""
    extra: Dict[str, Any] = {}
    if isinstance(result, tuple):
        if len(result) == 2:
            passed, rejected = result
        elif len(result) >= 3:
            passed, rejected, extra_candidate = result[0], result[1], result[2]
            if isinstance(extra_candidate, dict):
                extra = dict(extra_candidate)
            else:
                extra = {"filter_extra": extra_candidate}
        else:
            passed, rejected = [], []
    elif isinstance(result, dict):
        passed = result.get("passed") or result.get("passed_rows") or []
        rejected = result.get("rejected") or result.get("rejected_rows") or []
        extra = {k: v for k, v in result.items() if k not in {"passed", "passed_rows", "rejected", "rejected_rows"}}
    else:
        passed, rejected = [], []

    passed_rows = [x for x in passed if isinstance(x, dict)] if isinstance(passed, list) else []
    rejected_rows = [x for x in rejected if isinstance(x, dict)] if isinstance(rejected, list) else []
    return passed_rows, rejected_rows, extra


def build_manifest(
    rows: List[Dict[str, Any]],
    passed: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    source_meta: Dict[str, Any],
    filter_extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_rows": len(rows),
        "passed_rows": len(passed),
        "rejected_rows": len(rejected),
        "filter_version": FILTER_VERSION,
        "config": config_to_dict(DEFAULT_CONFIG),
        "source_meta": source_meta,
        "reason_counts": _count_many(rejected, ("cloq_reasons", "cloq_reject_reasons", "cloq_hard_reject_reasons")),
        "warning_counts": _count_many(passed + rejected, ("cloq_warnings",)),
        "tag_counts": _count_many(passed + rejected, ("cloq_tags",)),
    }
    if filter_extra:
        # Do not let extra override core counts accidentally, but keep it for audit.
        manifest["filter_extra"] = filter_extra
    return manifest


def run(outputs_dir: Path, config: Any = DEFAULT_CONFIG) -> Dict[str, Any]:
    rows, source_meta = load_source_rows(outputs_dir)
    result = filter_cloq_rows(rows, config)
    passed, rejected, extra = _normalize_filter_result(result)

    # Sort passed rows by score descending, then CorQ descending as a stable fallback.
    def score_key(row: Dict[str, Any]) -> Tuple[float, float]:
        cloq_score = row.get("cloq_score")
        corq = row.get("cloq_corq_probability") or row.get("corq_probability") or row.get("corq")
        try:
            s1 = float(cloq_score)
        except Exception:
            s1 = 0.0
        try:
            s2 = float(corq)
        except Exception:
            s2 = 0.0
        return (s1, s2)

    passed = sorted(passed, key=score_key, reverse=True)
    rejected = sorted(rejected, key=score_key, reverse=True)

    manifest = build_manifest(rows, passed, rejected, source_meta, extra)

    _write_json(outputs_dir / "latest_cloq.json", passed)
    _write_json(outputs_dir / "latest_cloq_rejected.json", rejected)
    _write_json(outputs_dir / "latest_cloq_manifest.json", manifest)
    return manifest


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate CloQ close-odds shortlist outputs.")
    parser.add_argument("--outputs-dir", default="outputs", help="Directory containing latest_all/latest_top7 JSON files.")
    args = parser.parse_args(argv)

    outputs_dir = Path(args.outputs_dir)
    manifest = run(outputs_dir, DEFAULT_CONFIG)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
