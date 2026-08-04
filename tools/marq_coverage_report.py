from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

MODEL_VERSION = "2026-08-04-marq-coverage-report-v1"


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[marq-report] failed to read {path}: {exc}")
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "data", "picks", "cloq", "records", "results"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-", "N/A", "NA", "None", "null"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def pct(part: int, total: int) -> float:
    return round((part / total * 100.0), 2) if total else 0.0


def first_present(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if "." in key:
            cur: Any = row
            ok = True
            for part in key.split("."):
                if not isinstance(cur, dict):
                    ok = False
                    break
                cur = cur.get(part)
            if ok and cur not in (None, "", "—", "-"):
                return cur
        else:
            val = row.get(key)
            if val not in (None, "", "—", "-"):
                return val
    return None


def pick_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "pick", "cloq_pick", "player", "player1", "home") or "—")


def opponent_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "opponent", "opp", "player2", "away") or "—")


def row_identity(row: Dict[str, Any]) -> str:
    return str(first_present(row, "event_id", "match_id", "id", "match_key") or f"{pick_name(row)} vs {opponent_name(row)}")


def clean_bucket(value: Any, default: str = "MISSING") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "nan", "unknown", "—", "-"}:
        return default
    return text


def endpoint_name(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "marq_endpoint_name", "odds_endpoint_name", "provider_odds_endpoint_name"), "NO_ENDPOINT")


def data_status(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "marq_v2_data_status", "marq_data_status", "marq_source_quality"), "NO_DATA_STATUS")


def confidence(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "marq_v2_confidence", "marq_confidence"), "NO_CONFIDENCE")


def movement_status(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "marq_v2_movement_status", "marq_movement_status"), "NO_MOVEMENT_STATUS")


def quality_tier(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "corq_marq_quality_tier"), "NO_TIER")


def source_policy(row: Dict[str, Any]) -> str:
    return clean_bucket(first_present(row, "marq_source_policy", "marq_source"), "NO_SOURCE_POLICY")


def value_status(row: Dict[str, Any]) -> str:
    vd = as_float(first_present(row, "marq_v2_value_delta_pp", "corq_value_delta_pp", "value_delta_pp"))
    ev = as_float(first_present(row, "marq_v2_expected_value_pct", "expected_value_pct", "ev_pct"))
    if vd is None and ev is None:
        return "VALUE_UNKNOWN"
    if (vd is not None and vd >= 3.0) or (ev is not None and ev >= 4.0):
        return "VALUE_STRONG"
    if (vd is not None and vd >= 0.5) or (ev is not None and ev >= 1.0):
        return "VALUE_PLAYABLE"
    if (vd is not None and vd <= -3.0) or (ev is not None and ev <= -4.0):
        return "NO_VALUE"
    return "VALUE_NEUTRAL"


def numeric_stats(values: Iterable[Any]) -> Dict[str, Optional[float]]:
    nums = [as_float(x) for x in values]
    nums = [x for x in nums if x is not None]
    if not nums:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(nums),
        "avg": round(mean(nums), 4),
        "min": round(min(nums), 4),
        "max": round(max(nums), 4),
    }


def summarize_attempts(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    endpoint_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    total_attempts = 0
    for row in rows:
        attempts = first_present(row, "provider_odds_endpoint_attempts", "odds_attempts")
        if isinstance(attempts, list):
            total_attempts += len(attempts)
            for item in attempts:
                if isinstance(item, dict):
                    endpoint_counts[str(item.get("endpoint_name") or "unknown")] += 1
                    status = item.get("status_code") if item.get("status_code") is not None else item.get("note")
                    status_counts[str(status or "UNKNOWN")] += 1
                elif isinstance(item, str):
                    text = item.strip()
                    if not text:
                        continue
                    endpoint_counts[text.split(":", 1)[0]] += 1
                    status_counts[text.split(":")[-1] if ":" in text else "STRING_ATTEMPT"] += 1
    return {
        "total_attempts": total_attempts,
        "endpoint_counts": dict(endpoint_counts.most_common()),
        "status_counts": dict(status_counts.most_common()),
    }


def sample_rows(rows: List[Dict[str, Any]], predicate, limit: int = 12) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        try:
            if not predicate(row):
                continue
        except Exception:
            continue
        out.append({
            "identity": row_identity(row),
            "pick": pick_name(row),
            "opponent": opponent_name(row),
            "odds": first_present(row, "pick_odds", "odds"),
            "endpoint": endpoint_name(row),
            "data_status": data_status(row),
            "confidence": confidence(row),
            "movement_status": movement_status(row),
            "tier": quality_tier(row),
            "market_weight": first_present(row, "corq_market_weight"),
            "value_delta_pp": first_present(row, "marq_v2_value_delta_pp", "corq_value_delta_pp", "value_delta_pp"),
            "expected_value_pct": first_present(row, "marq_v2_expected_value_pct", "expected_value_pct", "ev_pct"),
            "fallback_reason": first_present(row, "marq_fallback_reason"),
        })
        if len(out) >= limit:
            break
    return out


def summarize_rows(rows: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    total = len(rows)
    endpoint_counts = Counter(endpoint_name(row) for row in rows)
    data_counts = Counter(data_status(row) for row in rows)
    confidence_counts = Counter(confidence(row) for row in rows)
    movement_counts = Counter(movement_status(row) for row in rows)
    tier_counts = Counter(quality_tier(row) for row in rows)
    value_counts = Counter(value_status(row) for row in rows)
    source_counts = Counter(source_policy(row) for row in rows)

    weights = [first_present(row, "corq_market_weight") for row in rows]
    value_delta = [first_present(row, "marq_v2_value_delta_pp", "corq_value_delta_pp", "value_delta_pp") for row in rows]
    ev_values = [first_present(row, "marq_v2_expected_value_pct", "expected_value_pct", "ev_pct") for row in rows]

    high = tier_counts.get("HIGH", 0)
    medium = tier_counts.get("MEDIUM_CURRENT_ONLY", 0)
    thin = tier_counts.get("THIN_FALLBACK", 0)
    no_marq = tier_counts.get("NO_MARQ", 0) + tier_counts.get("NO_TIER", 0)

    return {
        "label": label,
        "total_rows": total,
        "coverage_pct": {
            "high_marq": pct(high, total),
            "medium_current_only": pct(medium, total),
            "thin_fallback": pct(thin, total),
            "no_or_unknown_marq": pct(no_marq, total),
            "usable_marq_high_or_medium": pct(high + medium, total),
        },
        "endpoint_counts": dict(endpoint_counts.most_common()),
        "data_status_counts": dict(data_counts.most_common()),
        "confidence_counts": dict(confidence_counts.most_common()),
        "movement_status_counts": dict(movement_counts.most_common()),
        "quality_tier_counts": dict(tier_counts.most_common()),
        "value_status_counts": dict(value_counts.most_common()),
        "source_policy_counts": dict(source_counts.most_common()),
        "market_weight_stats": numeric_stats(weights),
        "value_delta_pp_stats": numeric_stats(value_delta),
        "expected_value_pct_stats": numeric_stats(ev_values),
        "samples": {
            "thin_fallback": sample_rows(rows, lambda r: quality_tier(r) == "THIN_FALLBACK" or "THIN" in data_status(r).upper()),
            "no_marq_or_unknown": sample_rows(rows, lambda r: quality_tier(r) in {"NO_MARQ", "NO_TIER"}),
            "current_only": sample_rows(rows, lambda r: "CURRENT_ONLY" in movement_status(r).upper()),
            "real_opening": sample_rows(rows, lambda r: "REAL_OPENING" in movement_status(r).upper()),
            "no_value": sample_rows(rows, lambda r: value_status(r) == "NO_VALUE"),
            "value_strong": sample_rows(rows, lambda r: value_status(r) == "VALUE_STRONG"),
        },
        "attempt_summary": summarize_attempts(rows),
    }


def md_counts(title: str, counts: Dict[str, Any], total: int) -> List[str]:
    lines = [f"### {title}", ""]
    if not counts:
        return lines + ["No data.", ""]
    for key, value in counts.items():
        lines.append(f"- {key}: {value} ({pct(int(value), total)}%)")
    lines.append("")
    return lines


def render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# MarQ API Coverage Report",
        "",
        f"Generated UTC: {report.get('generated_at_utc')}",
        f"Model: {report.get('model_version')}",
        "",
    ]
    sections = report.get("sections") if isinstance(report.get("sections"), dict) else {}
    for label, section in sections.items():
        total = int(section.get("total_rows") or 0)
        lines.extend([f"## {label}", "", f"Rows: {total}", ""])
        coverage = section.get("coverage_pct") or {}
        lines.extend([
            "### Coverage",
            "",
            f"- High MarQ: {coverage.get('high_marq', 0)}%",
            f"- Medium current-only: {coverage.get('medium_current_only', 0)}%",
            f"- Thin fallback: {coverage.get('thin_fallback', 0)}%",
            f"- No/unknown MarQ: {coverage.get('no_or_unknown_marq', 0)}%",
            f"- Usable High+Medium: {coverage.get('usable_marq_high_or_medium', 0)}%",
            "",
        ])
        for title, key in (
            ("Endpoints", "endpoint_counts"),
            ("Quality tiers", "quality_tier_counts"),
            ("Data status", "data_status_counts"),
            ("Movement status", "movement_status_counts"),
            ("Value status", "value_status_counts"),
        ):
            lines.extend(md_counts(title, section.get(key) or {}, total))
        lines.extend([
            "### Numeric stats",
            "",
            f"- CorQ market weight: `{section.get('market_weight_stats')}`",
            f"- Value delta pp: `{section.get('value_delta_pp_stats')}`",
            f"- Expected value pct: `{section.get('expected_value_pct_stats')}`",
            "",
        ])
    lines.extend([
        "## Notes",
        "",
        "- HIGH should represent exact TennisApi odds with real opening/current movement data.",
        "- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.",
        "- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.",
        "- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.",
        "",
    ])
    return "\n".join(lines)


def build_report(output_root: str = "outputs") -> Dict[str, Any]:
    root = Path(output_root)
    all_rows = json_rows(read_json(root / "latest_all.json", []))
    top7_rows = json_rows(read_json(root / "latest_top7.json", []))
    cloq_rows = json_rows(read_json(root / "cloq" / "latest_cloq.json", []))
    if not cloq_rows:
        cloq_rows = json_rows(read_json(root / "latest_cloq.json", []))

    report = {
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_paths": {
            "all": str(root / "latest_all.json"),
            "top7": str(root / "latest_top7.json"),
            "cloq": str(root / "cloq" / "latest_cloq.json"),
        },
        "sections": {
            "all_audit": summarize_rows(all_rows, "all_audit"),
            "corq_top7": summarize_rows(top7_rows, "corq_top7"),
            "cloq": summarize_rows(cloq_rows, "cloq"),
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MarQ API coverage report from generated outputs")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    args = parser.parse_args()

    root = Path(args.output_root)
    report = build_report(args.output_root)
    out_dir = root / "marq"
    json_path = out_dir / "marq_api_coverage_report.json"
    md_path = out_dir / "marq_api_coverage_report.md"
    write_json(json_path, report)
    write_text(md_path, render_markdown(report))
    print(f"[marq-report] wrote {json_path}")
    print(f"[marq-report] wrote {md_path}")


if __name__ == "__main__":
    main()
