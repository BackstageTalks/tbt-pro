from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from .common import as_float, json_rows, pick_odds, read_json, write_json

DEFAULT_MODELS = ("corq", "cloq", "audit")
DECIDED_STATUSES = {"WON", "LOST"}
ALL_STATUSES = ("WON", "LOST", "VOID", "PENDING")


def _now_local(local_tz: str) -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(local_tz))
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _iso_day(value: Any) -> str:
    txt = str(value or "").strip()
    if len(txt) >= 10:
        candidate = txt[:10]
        try:
            datetime.fromisoformat(candidate)
            return candidate
        except Exception:
            return ""
    return ""


def row_day(row: Dict[str, Any]) -> str:
    for key in (
        "date",
        "betting_day",
        "snapshot_date",
        "snapshot_functional_day",
        "functional_day",
        "run_date",
        "match_date",
        "start_time_utc",
        "match_time_utc",
        "start_time",
        "match_time",
    ):
        day = _iso_day(row.get(key))
        if day:
            return day
    return ""


def default_end_day(local_tz: str = "Europe/Bratislava") -> str:
    """Return previous completed project betting day.

    The project uses a 06:00 -> 06:00 betting day. Before 06:00 local time,
    the current betting day is still the previous calendar day, so the previous
    completed betting day is two calendar days back. Otherwise it is yesterday.
    """
    now = _now_local(local_tz)
    current_betting_day = now.date() - timedelta(days=1) if now.hour < 6 else now.date()
    return (current_betting_day - timedelta(days=1)).isoformat()


def date_range(end_day: str, days: int) -> List[str]:
    days = max(int(days or 7), 1)
    end = datetime.fromisoformat(str(end_day)[:10]).date()
    start = end - timedelta(days=days - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def normalize_status(row: Dict[str, Any]) -> str:
    raw = str(
        row.get("result")
        or row.get("result_status")
        or row.get("settlement_status")
        or row.get("status")
        or "PENDING"
    ).strip().upper()

    if raw in {"WIN", "W", "HIT", "WON"}:
        return "WON"
    if raw in {"LOSS", "L", "MISS", "LOST"}:
        return "LOST"
    if raw in {"VOID", "PUSH", "CANCELLED", "CANCELED", "WALKOVER", "RETIRED"}:
        return "VOID"
    if raw in {"PENDING", "NOTSTARTED", "NOT_STARTED", "LIVE", "INPROGRESS", "IN_PROGRESS", "OPEN", ""}:
        return "PENDING"
    return "PENDING"


def units_for_row(row: Dict[str, Any], status: Optional[str] = None) -> float:
    status = status or normalize_status(row)
    for key in ("units", "profit_units", "pnl_units", "result_units", "settlement_units"):
        val = as_float(row.get(key), None)
        if val is not None:
            return float(val)

    odds = pick_odds(row) or 0.0
    if status == "WON" and odds > 1.0:
        return round(float(odds) - 1.0, 4)
    if status == "LOST":
        return -1.0
    return 0.0


def load_model_rows(results_root: Path, model: str) -> List[Dict[str, Any]]:
    candidates = [
        results_root / f"latest_results_{model}.json",
        results_root / f"latest_{model}_results.json",
    ]
    for path in candidates:
        rows = json_rows(read_json(path, []))
        if rows:
            return rows
    return []


def empty_bucket(day: str) -> Dict[str, Any]:
    return {
        "date": day,
        "picks": 0,
        "won": 0,
        "lost": 0,
        "void": 0,
        "pending": 0,
        "settled": 0,
        "units": 0.0,
        "win_rate": None,
        "roi": None,
    }


def summarize_rows(rows: Iterable[Dict[str, Any]], days: List[str]) -> Dict[str, Any]:
    day_set = set(days)
    by_day: Dict[str, Dict[str, Any]] = {day: empty_bucket(day) for day in days}
    totals = empty_bucket("TOTAL")

    for row in rows:
        day = row_day(row)
        if day not in day_set:
            continue

        status = normalize_status(row)
        units = units_for_row(row, status)

        bucket = by_day[day]
        for target in (bucket, totals):
            target["picks"] += 1
            if status == "WON":
                target["won"] += 1
            elif status == "LOST":
                target["lost"] += 1
            elif status == "VOID":
                target["void"] += 1
            else:
                target["pending"] += 1
            target["units"] = round(float(target["units"]) + units, 4)

    for bucket in list(by_day.values()) + [totals]:
        settled = int(bucket["won"] or 0) + int(bucket["lost"] or 0)
        bucket["settled"] = settled
        bucket["win_rate"] = round(bucket["won"] / settled, 4) if settled else None
        bucket["roi"] = round(bucket["units"] / settled, 4) if settled else None

    return {
        "totals": totals,
        "by_day": [by_day[day] for day in days],
    }


def fmt_pct(value: Any) -> str:
    num = as_float(value, None)
    if num is None:
        return "-"
    return f"{num * 100:.1f}%"


def fmt_units(value: Any) -> str:
    num = as_float(value, 0.0) or 0.0
    return f"{num:+.2f}u"


def build_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Weekly model stats")
    lines.append("")
    lines.append(f"Generated at: `{report.get('generated_at')}`")
    lines.append(f"Window: `{report.get('start_date')}` to `{report.get('end_date')}`")
    lines.append("")

    for model, payload in (report.get("models") or {}).items():
        totals = payload.get("totals") or {}
        lines.append(f"## {model.upper()}")
        lines.append("")
        lines.append(
            f"Picks: **{totals.get('picks', 0)}** | "
            f"W/L/V/P: **{totals.get('won', 0)}/{totals.get('lost', 0)}/{totals.get('void', 0)}/{totals.get('pending', 0)}** | "
            f"Units: **{fmt_units(totals.get('units'))}** | "
            f"Win rate: **{fmt_pct(totals.get('win_rate'))}** | "
            f"ROI: **{fmt_pct(totals.get('roi'))}**"
        )
        lines.append("")
        lines.append("| Date | Picks | W | L | V | P | Units | Win rate | ROI |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for day in payload.get("by_day") or []:
            lines.append(
                f"| {day.get('date')} | {day.get('picks', 0)} | {day.get('won', 0)} | "
                f"{day.get('lost', 0)} | {day.get('void', 0)} | {day.get('pending', 0)} | "
                f"{fmt_units(day.get('units'))} | {fmt_pct(day.get('win_rate'))} | {fmt_pct(day.get('roi'))} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_telegram_message(report: Dict[str, Any]) -> str:
    lines = [
        "📈 Weekly model stats",
        f"📅 {report.get('start_date')} -> {report.get('end_date')}",
        "",
    ]
    for model, payload in (report.get("models") or {}).items():
        totals = payload.get("totals") or {}
        lines.append(
            f"{model.upper()}: "
            f"✅{totals.get('won', 0)} ❌{totals.get('lost', 0)} ➖{totals.get('void', 0)} ⏳{totals.get('pending', 0)} | "
            f"{fmt_units(totals.get('units'))} | ROI {fmt_pct(totals.get('roi'))}"
        )
    if len(lines) == 3:
        lines.append("No model result rows found for this window.")
    return "\n".join(lines).rstrip() + "\n"


def build_weekly_stats(
    output_root: Path = Path("outputs"),
    days_count: int = 7,
    end_day: Optional[str] = None,
    local_tz: str = "Europe/Bratislava",
    models: Tuple[str, ...] = DEFAULT_MODELS,
) -> Dict[str, Any]:
    end_day = (end_day or default_end_day(local_tz))[:10]
    days = date_range(end_day, days_count)
    results_root = output_root / "results"

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "start_date": days[0],
        "end_date": days[-1],
        "days": days,
        "local_tz": local_tz,
        "source_root": str(results_root),
        "models": {},
    }

    for model in models:
        model = str(model or "").strip().lower()
        if not model:
            continue
        rows = load_model_rows(results_root, model)
        payload = summarize_rows(rows, days)
        payload["source_file"] = str(results_root / f"latest_results_{model}.json")
        payload["raw_rows"] = len(rows)
        report["models"][model] = payload

    return report


def write_report(report: Dict[str, Any], output_root: Path) -> Dict[str, str]:
    stats_dir = output_root / "model_stats"
    telegram_dir = output_root / "telegram"
    stats_dir.mkdir(parents=True, exist_ok=True)
    telegram_dir.mkdir(parents=True, exist_ok=True)

    json_path = stats_dir / "weekly_model_stats.json"
    md_path = stats_dir / "weekly_model_stats.md"
    tg_path = telegram_dir / "latest_weekly_model_stats_message.txt"

    write_json(json_path, report)
    md_path.write_text(build_markdown(report), encoding="utf-8")
    tg_path.write_text(build_telegram_message(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "telegram_message": str(tg_path),
    }


def parse_models(value: str) -> Tuple[str, ...]:
    items = [x.strip().lower() for x in str(value or "").split(",") if x.strip()]
    return tuple(items) if items else DEFAULT_MODELS


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly CorQ/CloQ/Audit model stats from real results JSON files.")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end-date", default=None, help="Last day in stats window, YYYY-MM-DD. Defaults to previous completed betting day.")
    parser.add_argument("--local-tz", default="Europe/Bratislava")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    args = parser.parse_args()

    output_root = Path(args.output_root)
    report = build_weekly_stats(
        output_root=output_root,
        days_count=args.days,
        end_day=args.end_date,
        local_tz=args.local_tz,
        models=parse_models(args.models),
    )
    outputs = write_report(report, output_root)

    print(json.dumps({"weekly_model_stats": report, "outputs": outputs}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
