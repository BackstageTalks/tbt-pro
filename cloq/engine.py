"""Build clean value-first CloQ output from CorQ ALL rows.

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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cloq.filters import (
    MODEL_VERSION,
    annotate_cloq,
    cloq_score,
    match_identity,
)

DEFAULT_TOP_N = 7
DEFAULT_MIN_PUBLISH_ROWS = 3


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


def _num(value: Any, default: float = -9999.0) -> float:
    try:
        if value in (None, "", "—", "-", "N/A"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def _has_any(row: Dict[str, Any], names: Iterable[str]) -> bool:
    values = set(str(x) for x in (row.get("cloq_reject_reasons") or [])) | set(str(x) for x in (row.get("cloq_risk_tags") or []))
    return any(name in values for name in names)


def _backup_tier(row: Dict[str, Any]) -> str:
    """Classify non-clean CloQ rows that can still be published as best-available picks.

    This does not invent data. It only relaxes the hard clean filter into clearly
    labelled tiers so CloQ can publish up to a small card even when no perfectly
    clean value exists.
    """
    odds = _num(row.get("cloq_pick_odds"), 0.0)
    vd = _num(row.get("cloq_value_delta_pp"), -9999.0)
    ev = _num(row.get("cloq_expected_value_pct"), -9999.0)
    reasons = set(str(x) for x in (row.get("cloq_reject_reasons") or []))

    hard_blocks = {
        "REJECT_CLOQ_STATUS_NOT_PREMATCH",
        "REJECT_CLOQ_DOUBLES",
        "REJECT_CLOQ_MISSING_PICK_ODDS",
        "REJECT_CLOQ_MISSING_CORQ_PROBABILITY",
        "REJECT_CLOQ_MISSING_VALUE_DATA",
        "REJECT_CLOQ_ODDS_UNDER_1_70",
        "REJECT_CLOQ_ODDS_OVER_3_00",
        "REJECT_CLOQ_MARKET_AGAINST_PICK",
        "REJECT_CLOQ_NEGATIVE_THINQ_EDGE",
        "REJECT_CLOQ_LOW_DATA_DEPTH",
        "REJECT_CLOQ_LOW_THINQ_CONFIDENCE",
    }
    if reasons & hard_blocks:
        return ""
    if not (1.70 <= odds <= 3.00):
        return ""

    # Tier B: playable value, no strong-opponent conflict.
    if not _has_any(row, {"OPP_STRONG", "STRENGTH_CONFLICT", "REJECT_CLOQ_OPP_STRONG", "REJECT_CLOQ_STRENGTH_CONFLICT"}):
        if vd >= 2.0 or ev >= 2.0:
            return "CLOQ_PLAYABLE_BACKUP"

    # Tier C: risk-labelled fallback. Must have stronger value to compensate,
    # and it stays explicitly marked as risk, not clean.
    if vd >= 4.0 or ev >= 5.0:
        return "CLOQ_RISK_BACKUP"
    return ""


def _publish_sort_key(row: Dict[str, Any]) -> tuple:
    tier = str(row.get("cloq_publish_tier") or "")
    tier_rank = {
        "CLOQ_CLEAN": 3,
        "CLOQ_CLEAN_HIGH_VALUE": 3,
        "CLOQ_PLAYABLE_BACKUP": 2,
        "CLOQ_RISK_BACKUP": 1,
    }.get(tier, 0)
    return (
        tier_rank,
        float(row.get("cloq_score") or -9999.0),
        _num(row.get("cloq_value_delta_pp")),
        _num(row.get("cloq_expected_value_pct")),
        _num(row.get("cloq_pick_odds"), 0.0),
    )


def build_cloq_rows(all_rows: Iterable[Dict[str, Any]], top_n: int = DEFAULT_TOP_N, min_publish_rows: int = DEFAULT_MIN_PUBLISH_ROWS) -> List[Dict[str, Any]]:
    annotated = [annotate_cloq(row) for row in all_rows if isinstance(row, dict)]

    clean: List[Dict[str, Any]] = []
    backups: List[Dict[str, Any]] = []
    for row in annotated:
        row = dict(row)
        if row.get("cloq_publishable") is True:
            row["cloq_publish_tier"] = str(row.get("cloq_decision") or "CLOQ_CLEAN")
            row["cloq_original_publishable"] = True
            clean.append(row)
            continue
        tier = _backup_tier(row)
        if tier:
            row["cloq_publish_tier"] = tier
            row["cloq_original_publishable"] = False
            row["cloq_publishable"] = True
            row["cloq_selected_reason"] = "best_available_value_backup_not_clean"
            # Keep the original reject reasons for transparency, but move them to
            # slot-level warnings so the UI/log can show why the row is not clean.
            row["cloq_backup_warning_reasons"] = list(row.get("cloq_reject_reasons") or [])
            row["cloq_score"] = max(cloq_score(row), 0.0)
            backups.append(row)

    clean = sorted(dedupe_best_by_match(clean), key=_publish_sort_key, reverse=True)
    output = clean[: max(int(top_n or DEFAULT_TOP_N), 0)]

    if len(output) < min_publish_rows:
        existing_matches = {match_identity(row) for row in output}
        backup_sorted = sorted(dedupe_best_by_match(backups), key=_publish_sort_key, reverse=True)
        for row in backup_sorted:
            if len(output) >= min_publish_rows or len(output) >= max(int(top_n or DEFAULT_TOP_N), 0):
                break
            if match_identity(row) in existing_matches:
                continue
            output.append(row)
            existing_matches.add(match_identity(row))

    output = sorted(output, key=_publish_sort_key, reverse=True)[: max(int(top_n or DEFAULT_TOP_N), 0)]
    for idx, row in enumerate(output, start=1):
        row["cloq_rank"] = idx
        row["cloq_selected"] = True
        row["cloq_score"] = cloq_score(row) if row.get("cloq_original_publishable") is True else row.get("cloq_score")
    return output


def build_cloq_audit_rows(all_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    annotated = []
    for row in all_rows:
        if not isinstance(row, dict):
            continue
        item = annotate_cloq(row)
        if item.get("cloq_publishable") is True:
            item["cloq_publish_tier"] = str(item.get("cloq_decision") or "CLOQ_CLEAN")
            item["cloq_original_publishable"] = True
        else:
            tier = _backup_tier(item)
            if tier:
                item["cloq_publish_tier"] = tier
                item["cloq_original_publishable"] = False
        annotated.append(item)
    return sorted(
        annotated,
        key=lambda row: (
            bool(row.get("cloq_publish_tier")),
            _publish_sort_key(row),
        ),
        reverse=True,
    )


def build_manifest(input_path: Path, output_rows: List[Dict[str, Any]], audit_rows: List[Dict[str, Any]], all_count: int, top_n: int, min_publish_rows: int = DEFAULT_MIN_PUBLISH_ROWS) -> Dict[str, Any]:
    value_status_counts = Counter(str(row.get("cloq_value_status") or "UNKNOWN") for row in audit_rows)
    decision_counts = Counter(str(row.get("cloq_decision") or "UNKNOWN") for row in audit_rows)
    publish_tier_counts = Counter(str(row.get("cloq_publish_tier") or "NOT_PUBLISHABLE") for row in audit_rows)
    reject_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    for row in audit_rows:
        reject_counts.update(row.get("cloq_reject_reasons") or [])
        risk_counts.update(row.get("cloq_risk_tags") or [])
        support_counts.update(row.get("cloq_support_tags") or [])
    return {
        "model": MODEL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "input_rows": all_count,
        "audit_rows": len(audit_rows),
        "output_rows": len(output_rows),
        "top_n": top_n,
        "min_publish_rows": min_publish_rows,
        "policy": {
            "odds_min": 1.70,
            "odds_preferred_max": 2.40,
            "odds_max": 3.00,
            "min_value_delta_pp": 3.00,
            "min_expected_value_pct": 3.00,
            "opp_strong": "hard_reject",
            "market_against_pick": "hard_reject",
            "forced_count": "min_3_best_available_with_explicit_tier_labels",
        },
        "decision_counts": dict(decision_counts),
        "publish_tier_counts": dict(publish_tier_counts),
        "value_status_counts": dict(value_status_counts),
        "reject_reason_counts": dict(reject_counts),
        "risk_tag_counts": dict(risk_counts),
        "support_tag_counts": dict(support_counts),
        "notes": [
            "CloQ is value-first: publishable rows need odds >=1.70 and value_delta >=3pp or EV >=3%.",
            "Opp strong and strength conflict are hard rejects for clean CloQ.",
            "Market against pick is a hard reject; market with pick is a score bonus.",
            "Clean CloQ remains strict, but the published card can fill up to 3 best-available value backups with explicit tier labels.",
            "No synthetic odds, probabilities or value values are generated.",
        ],
    }


def run(input_path: Optional[str] = None, output_root: str = "outputs", top_n: int = DEFAULT_TOP_N, min_publish_rows: int = DEFAULT_MIN_PUBLISH_ROWS) -> Dict[str, Any]:
    root = Path(output_root)
    input_file = Path(input_path) if input_path else root / "latest_all.json"
    all_rows = json_rows(read_json(input_file, []))
    audit_rows = build_cloq_audit_rows(all_rows)
    cloq_rows = build_cloq_rows(all_rows, top_n=top_n, min_publish_rows=min_publish_rows)
    cloq_dir = root / "cloq"
    latest_nested = cloq_dir / "latest_cloq.json"
    latest_flat = root / "latest_cloq.json"
    audit_path = cloq_dir / "latest_cloq_audit.json"
    manifest_path = cloq_dir / "latest_cloq_manifest.json"
    write_json(latest_nested, cloq_rows)
    write_json(latest_flat, cloq_rows)
    write_json(audit_path, audit_rows)
    manifest = build_manifest(input_file, cloq_rows, audit_rows, len(all_rows), top_n, min_publish_rows=min_publish_rows)
    write_json(manifest_path, manifest)
    return {
        "rows": len(cloq_rows),
        "audit_rows": len(audit_rows),
        "input_rows": len(all_rows),
        "min_publish_rows": min_publish_rows,
        "latest_cloq": str(latest_nested),
        "latest_cloq_flat": str(latest_flat),
        "latest_cloq_audit": str(audit_path),
        "manifest": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clean value-first CloQ output")
    parser.add_argument("--input", dest="input_path", default=None, help="Input ALL JSON path, default outputs/latest_all.json")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="Maximum number of CloQ rows to publish")
    parser.add_argument("--min-publish-rows", type=int, default=DEFAULT_MIN_PUBLISH_ROWS, help="Minimum best-available CloQ rows to publish if enough real candidates exist")
    args = parser.parse_args()
    result = run(input_path=args.input_path, output_root=args.output_root, top_n=args.top_n, min_publish_rows=args.min_publish_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
