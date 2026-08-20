"""LucQ API PRO-only daily builder.

LucQ is a standalone public data layer and does not read other project-layer outputs. The first
version calculates match-side LucQ probability only from exact-event TennisAPI
PRO winner odds after removing the two-way overround. No other project layer is
read and no missing value is fabricated.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import fetch_daily_matches_with_odds

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
LUCQ_VERSION = "LUCQ_API_PRO_NO_VIG_V2"
SOURCE_POLICY = "API_PRO_ONLY"


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if number > 0 else None
    except Exception:
        return None


def _no_vig(odds_1: Any, odds_2: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    first = _float(odds_1)
    second = _float(odds_2)
    if first is None or second is None or first <= 1.0 or second <= 1.0:
        return None, None, None
    raw_1 = 1.0 / first
    raw_2 = 1.0 / second
    total = raw_1 + raw_2
    if total <= 0:
        return None, None, None
    return round(raw_1 / total, 6), round(raw_2 / total, 6), round(total, 6)


def _target_datetime(run_date: str) -> datetime:
    day = datetime.strptime(run_date, "%Y-%m-%d").date()
    return datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ)


def _start_sort_value(row: Dict[str, Any]) -> str:
    return str(row.get("match_start") or row.get("start_time") or "9999-12-31T23:59:59+00:00")


def build_lucq_rows(run_date: str) -> List[Dict[str, Any]]:
    matches = fetch_daily_matches_with_odds(_target_datetime(run_date))
    rows: List[Dict[str, Any]] = []

    for match in matches:
        probability_1, probability_2, overround = _no_vig(
            match.get("odds_player1"),
            match.get("odds_player2"),
        )
        if probability_1 is None or probability_2 is None:
            continue
        # Exact-event API PRO odds are already oriented to player1/player2 by
        # corq_rapidapi_client. Some valid numeric 1/2 payloads do not set the
        # optional odds_labels_confirmed flag, so that flag must not remove a
        # real and complete exact-event odds pair.
        endpoint = str(match.get("odds_endpoint") or "")
        if "/api/tennis/event/" not in endpoint:
            continue

        if probability_1 >= probability_2:
            pick_side = "HOME"
            pick = match.get("player1")
            opponent = match.get("player2")
            pick_odds = _float(match.get("odds_player1"))
            opponent_odds = _float(match.get("odds_player2"))
            probability = probability_1
        else:
            pick_side = "AWAY"
            pick = match.get("player2")
            opponent = match.get("player1")
            pick_odds = _float(match.get("odds_player2"))
            opponent_odds = _float(match.get("odds_player1"))
            probability = probability_2

        row = {
            "model": "LucQ",
            "layer": "LucQ",
            "lucq_version": LUCQ_VERSION,
            "source": "API PRO exact-event winner odds",
            "data_source": "API PRO",
            "probability_source": "API PRO two-way no-vig calculation",
            "source_policy": SOURCE_POLICY,
            "event_id": match.get("event_id") or match.get("match_id") or match.get("id"),
            "match_id": match.get("match_id") or match.get("event_id") or match.get("id"),
            "player1": match.get("player1"),
            "player2": match.get("player2"),
            "pick": pick,
            "opponent": opponent,
            "pick_side": pick_side,
            "pick_odds": pick_odds,
            "opponent_odds": opponent_odds,
            "odds_player1": _float(match.get("odds_player1")),
            "odds_player2": _float(match.get("odds_player2")),
            "lucq_probability": probability,
            "lucq_probability_pct": round(probability * 100.0, 1),
            "lucq_selection": f"{pick} to win",
            "lucq_market": "Match winner",
            "lucq_line": pick_odds,
            "lucq_status": "OK",
            "overround": overround,
            "surface": match.get("surface"),
            "tournament": match.get("tournament"),
            "category": match.get("category"),
            "best_of": match.get("best_of"),
            "match_start": match.get("match_start") or match.get("start_time"),
            "start_time": match.get("start_time") or match.get("match_start"),
            "status": match.get("status_type"),
            "betting_day": match.get("betting_day") or run_date,
            "betting_day_start_local": match.get("betting_day_start_local"),
            "betting_day_end_local": match.get("betting_day_end_local"),
            "odds_endpoint": match.get("odds_endpoint"),
            "odds_matching_direction": match.get("odds_matching_direction"),
            "odds_labels_confirmed": bool(match.get("odds_labels_confirmed")),
            "lucq_orientation_policy": "EXACT_EVENT_PLAYER1_PLAYER2",
            "lucq_real_line": True,
            "lucq_top10_enabled": False,
        }
        rows.append(row)

    rows.sort(key=lambda row: (-float(row["lucq_probability"]), _start_sort_value(row)))
    for index, row in enumerate(rows, start=1):
        row["lucq_rank"] = index
    return rows


def write_output(rows: List[Dict[str, Any]], output_path: str, run_date: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "LucQ",
        "layer": "LucQ",
        "version": LUCQ_VERSION,
        "source": "API PRO",
        "source_policy": SOURCE_POLICY,
        "run_date": run_date,
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "sort": "lucq_probability_desc_then_match_time_asc",
        "top10_picks_enabled": False,
        "row_count": len(rows),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LucQ API PRO-only output")
    parser.add_argument("--date", required=True, help="Betting day YYYY-MM-DD")
    parser.add_argument("--output", default="outputs/lucq/latest_lucq.json")
    args = parser.parse_args()
    rows = build_lucq_rows(args.date)
    output = write_output(rows, args.output, args.date)
    print(f"LUCQ OUTPUT: {output} rows={len(rows)}")


if __name__ == "__main__":
    main()
