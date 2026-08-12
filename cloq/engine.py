"""Build CloQ high-odds data-covered output from CorQ ALL rows.

CloQ scans the full CorQ ALL/Audit pool, but excludes matches that are already
selected by CorQ TOP7 so that the two public feeds do not duplicate the same
match. The exclusion is match-level, not player-level.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from cloq.filters import MODEL_VERSION, annotate_cloq, match_identity

DEFAULT_TOP_N = 10


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


def load_corq_overlap_keys(output_root: Path) -> Set[str]:
    """Return match identity keys already covered by CorQ.

    Primary source is outputs/latest_top7.json because it represents the current
    runtime CorQ selection. This avoids CloQ publishing the same match. The
    daily immutable snapshot is also checked as a safety net when latest_top7 is
    absent or stale, but empty files naturally contribute no keys.
    """
    paths = [
        output_root / "latest_top7.json",
        output_root / "snapshots" / "latest_corq_top7_snapshot.json",
    ]
    keys: Set[str] = set()
    for path in paths:
        rows = json_rows(read_json(path, []))
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = match_identity(row)
            if key:
                keys.add(str(key))
    return keys


def mark_corq_overlaps(rows: Iterable[Dict[str, Any]], corq_match_keys: Set[str]) -> List[Dict[str, Any]]:
    """Annotate CloQ rows and mark matches already present in CorQ TOP7.

    The row remains visible in CloQ audit, but it is removed from the public
    CloQ output. This keeps the model transparent while avoiding duplicate
    public picks.
    """
    annotated: List[Dict[str, Any]] = []
    for base_row in rows:
        if not isinstance(base_row, dict):
            continue
        row = annotate_cloq(base_row)
        key = str(match_identity(row) or "")
        if key and key in corq_match_keys:
            original_publishable = bool(row.get("cloq_publishable"))
            row["cloq_original_publishable_before_corq_overlap"] = original_publishable
            row["cloq_excluded_by_corq_overlap"] = True
            row["cloq_corq_overlap_match_key"] = key
            row["cloq_corq_overlap_reason"] = "CLOQ_SKIP_ALREADY_IN_CORQ"
            row["cloq_publishable"] = False
            row["cloq_decision"] = "CLOQ_REJECTED_CORQ_OVERLAP"
            reject_reasons = list(row.get("cloq_reject_reasons") or [])
            if "CLOQ_SKIP_ALREADY_IN_CORQ" not in reject_reasons:
                reject_reasons.append("CLOQ_SKIP_ALREADY_IN_CORQ")
            row["cloq_reject_reasons"] = reject_reasons
            risk_tags = list(row.get("cloq_risk_tags") or [])
            if "CORQ_OVERLAP" not in risk_tags:
                risk_tags.append("CORQ_OVERLAP")
            row["cloq_risk_tags"] = risk_tags
        else:
            row.setdefault("cloq_excluded_by_corq_overlap", False)
        annotated.append(row)
    return annotated


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


def _num(value: Any, default: float = -9999.0) -> float:
    try:
        if value in (None, "", "—", "-", "N/A"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def _sort_key(row: Dict[str, Any]) -> tuple:
    bucket = str(row.get("cloq_price_bucket") or "")
    bucket_rank = {
        "EXTENDED_1_90_2_20": 4,
        "PRIME_1_70_1_90": 3,
        "HIGH_VARIANCE_2_20_2_50": 2,
    }.get(bucket, 0)
    return (
        _num(row.get("cloq_score")),
        bucket_rank,
        _num(row.get("cloq_primary_probability"), 0.0),
        _num(row.get("cloq_model_gap_pp")),
        _num(row.get("cloq_evidence_score")),
        _num(row.get("cloq_data_depth"), 0.0),
        _num(row.get("cloq_pick_odds"), 0.0),
    )


def build_cloq_rows(
    all_rows: Iterable[Dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
    corq_match_keys: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    annotated = mark_corq_overlaps(all_rows, corq_match_keys or set())
    publishable = [row for row in annotated if row.get("cloq_publishable") is True]
    publishable = sorted(dedupe_best_by_match(publishable), key=_sort_key, reverse=True)
    output = publishable[: max(int(top_n or DEFAULT_TOP_N), 0)]
    for idx, row in enumerate(output, start=1):
        row["cloq_rank"] = idx
        row["cloq_selected"] = True
        row["cloq_publish_tier"] = str(row.get("cloq_decision") or "CLOQ_SELECTED")
        row["cloq_selected_reason"] = "top_high_odds_data_covered_candidate_excluding_corq_overlap"
    return output


def build_cloq_audit_rows(
    all_rows: Iterable[Dict[str, Any]],
    corq_match_keys: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    annotated = mark_corq_overlaps(all_rows, corq_match_keys or set())
    return sorted(annotated, key=lambda row: (bool(row.get("cloq_publishable")), _sort_key(row)), reverse=True)


def build_manifest(
    input_path: Path,
    output_rows: List[Dict[str, Any]],
    audit_rows: List[Dict[str, Any]],
    all_count: int,
    top_n: int,
    corq_overlap_keys: Set[str],
) -> Dict[str, Any]:
    decision_counts = Counter(str(row.get("cloq_decision") or "UNKNOWN") for row in audit_rows)
    tier_counts = Counter(str(row.get("cloq_publish_tier") or "NOT_SELECTED") for row in output_rows)
    reject_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    bucket_counts = Counter(str(row.get("cloq_price_bucket") or "UNKNOWN") for row in audit_rows)
    corq_overlap_count = 0
    corq_overlap_publishable_before_count = 0
    for row in audit_rows:
        reject_counts.update(row.get("cloq_reject_reasons") or [])
        risk_counts.update(row.get("cloq_risk_tags") or [])
        support_counts.update(row.get("cloq_support_tags") or [])
        if row.get("cloq_excluded_by_corq_overlap"):
            corq_overlap_count += 1
            if row.get("cloq_original_publishable_before_corq_overlap"):
                corq_overlap_publishable_before_count += 1
    return {
        "model": MODEL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "input_rows": all_count,
        "audit_rows": len(audit_rows),
        "output_rows": len(output_rows),
        "top_n": top_n,
        "corq_overlap": {
            "enabled": True,
            "source_paths": [
                "outputs/latest_top7.json",
                "outputs/snapshots/latest_corq_top7_snapshot.json",
            ],
            "corq_match_key_count": len(corq_overlap_keys),
            "audit_rows_excluded_by_corq_overlap": corq_overlap_count,
            "publishable_rows_excluded_by_corq_overlap": corq_overlap_publishable_before_count,
            "policy": "CloQ excludes matches already covered by CorQ TOP7/snapshot.",
        },
        "policy": {
            "concept": "Top higher-odds data-covered winner candidates, excluding CorQ overlap.",
            "min_odds": 1.70,
            "max_odds": 2.50,
            "odds_bands": {
                "1.70-1.90": "prime",
                "1.90-2.20": "extended",
                "2.20-2.50": "high_variance_requires_more_support",
            },
            "required_minimum": "pick/opponent/odds/prematch/non-doubles/primary probability >= 50%/reasonable depth or support",
            "primary_probability": "ThinQ when available, otherwise CorQ",
            "marq_policy": "MarQ probability or market read is used for support/risk, but missing MarQ is not allowed to create synthetic data.",
            "underdog_policy": "Allowed only with stronger model/depth/support; otherwise rejected as random underdog.",
            "no_fake_data": True,
            "forced_count": False,
        },
        "selected_tier_counts": dict(tier_counts),
        "decision_counts": dict(decision_counts),
        "price_bucket_counts": dict(bucket_counts),
        "reject_reason_counts": dict(reject_counts),
        "risk_tag_counts": dict(risk_counts),
        "support_tag_counts": dict(support_counts),
        "notes": [
            "CloQ scans the full ALL pool, not only CorQ TOP7.",
            "CloQ targets odds >= 1.70 and <= 2.50.",
            "Higher odds require stronger model/depth/support scoring.",
            "Rows without required core data are rejected with explicit reasons.",
            "Matches already in CorQ are visible in audit but excluded from public CloQ output.",
        ],
    }


def run(input_path: Optional[str] = None, output_root: str = "outputs", top_n: int = DEFAULT_TOP_N) -> Dict[str, Any]:
    root = Path(output_root)
    input_file = Path(input_path) if input_path else root / "latest_all.json"
    all_rows = json_rows(read_json(input_file, []))
    corq_overlap_keys = load_corq_overlap_keys(root)
    audit_rows = build_cloq_audit_rows(all_rows, corq_match_keys=corq_overlap_keys)
    cloq_rows = build_cloq_rows(all_rows, top_n=top_n, corq_match_keys=corq_overlap_keys)

    cloq_dir = root / "cloq"
    latest_nested = cloq_dir / "latest_cloq.json"
    latest_flat = root / "latest_cloq.json"
    audit_path = cloq_dir / "latest_cloq_audit.json"
    manifest_path = cloq_dir / "latest_cloq_manifest.json"
    write_json(latest_nested, cloq_rows)
    write_json(latest_flat, cloq_rows)
    write_json(audit_path, audit_rows)
    write_json(manifest_path, build_manifest(input_file, cloq_rows, audit_rows, len(all_rows), top_n, corq_overlap_keys))
    return {
        "rows": len(cloq_rows),
        "audit_rows": len(audit_rows),
        "input_rows": len(all_rows),
        "corq_overlap_match_keys": len(corq_overlap_keys),
        "latest_cloq": str(latest_nested),
        "latest_cloq_flat": str(latest_flat),
        "latest_cloq_audit": str(audit_path),
        "manifest": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CloQ high-odds data-covered output")
    parser.add_argument("--input", dest="input_path", default=None, help="Input ALL JSON path, default outputs/latest_all.json")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="Maximum number of CloQ rows to publish")
    args = parser.parse_args()
    result = run(input_path=args.input_path, output_root=args.output_root, top_n=args.top_n)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
