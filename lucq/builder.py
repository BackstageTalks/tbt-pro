"""LucQ API PRO-only daily analytics builder.

LucQ uses only real API PRO exact-event odds, previous completed singles matches,
and API PRO serve statistics. Missing inputs remain None and render as N/A.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import fetch_daily_matches_with_odds
from thinq.service import _build_previous_matches_shape, build_api_pro_serve_stats_context

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
LUCQ_VERSION = "LUCQ_API_PRO_ANALYTICS_V1"
SOURCE_POLICY = "API_PRO_ONLY"
GAMES_LINE = 22.5
SETS_LINE = 2.5


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _positive_float(value: Any) -> Optional[float]:
    number = _float(value)
    return number if number is not None and number > 0 else None


def _no_vig(odds_1: Any, odds_2: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    first = _positive_float(odds_1)
    second = _positive_float(odds_2)
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


def _first(match: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = match.get(key)
        if value not in (None, ""):
            return value
    return None


def _mean(values: List[Any], digits: int = 4) -> Optional[float]:
    numbers = [_float(value) for value in values]
    valid = [value for value in numbers if value is not None]
    return round(sum(valid) / len(valid), digits) if valid else None


def _side_selection(prefix: str, line: float, over_probability: Optional[float]) -> Tuple[Optional[str], Optional[float]]:
    if over_probability is None:
        return None, None
    probability = max(0.0, min(1.0, over_probability))
    if probability >= 0.5:
        return f"O{line:.1f}", round(probability, 4)
    return f"U{line:.1f}", round(1.0 - probability, 4)


def _data_quality(pick_shape: Dict[str, Any], opponent_shape: Dict[str, Any], serve: Dict[str, Any]) -> Tuple[str, float]:
    pick_sample = int(pick_shape.get("sample") or 0)
    opponent_sample = int(opponent_shape.get("sample") or 0)
    shape_depth = min(pick_sample, opponent_sample) / 12.0
    shape_depth = max(0.0, min(1.0, shape_depth))
    serve_ok = serve.get("api_serve_stats_status") == "OK"
    score = round((0.75 * shape_depth) + (0.25 if serve_ok else 0.0), 4)
    label = "GOOD" if score >= 0.75 else "PARTIAL" if score >= 0.40 else "LOW"
    return label, score


def _start_sort_value(row: Dict[str, Any]) -> str:
    return str(row.get("match_start") or row.get("start_time") or "9999-12-31T23:59:59+00:00")


def build_lucq_rows(run_date: str) -> List[Dict[str, Any]]:
    matches = fetch_daily_matches_with_odds(_target_datetime(run_date))
    rows: List[Dict[str, Any]] = []

    for match in matches:
        probability_1, probability_2, overround = _no_vig(match.get("odds_player1"), match.get("odds_player2"))
        if probability_1 is None or probability_2 is None:
            continue
        endpoint = str(match.get("odds_endpoint") or "")
        if "/api/tennis/event/" not in endpoint:
            continue

        player1 = match.get("player1")
        player2 = match.get("player2")
        player1_id = _first(match, "player1_id", "home_team_id", "home_id", "player1Id")
        player2_id = _first(match, "player2_id", "away_team_id", "away_id", "player2Id")
        if probability_1 >= probability_2:
            pick_side, pick, opponent = "HOME", player1, player2
            pick_id, opponent_id = player1_id, player2_id
            pick_odds, opponent_odds = _positive_float(match.get("odds_player1")), _positive_float(match.get("odds_player2"))
            winner_probability = probability_1
        else:
            pick_side, pick, opponent = "AWAY", player2, player1
            pick_id, opponent_id = player2_id, player1_id
            pick_odds, opponent_odds = _positive_float(match.get("odds_player2")), _positive_float(match.get("odds_player1"))
            winner_probability = probability_2

        surface = match.get("surface")
        start = match.get("match_start") or match.get("start_time")
        pick_shape = _build_previous_matches_shape(pick_id, surface, as_of_date=start)
        opponent_shape = _build_previous_matches_shape(opponent_id, surface, as_of_date=start)

        projected_sets = _mean([pick_shape.get("average_sets"), opponent_shape.get("average_sets")], 2)
        projected_games = _mean([pick_shape.get("average_games"), opponent_shape.get("average_games")], 1)
        decider_probability = _mean([pick_shape.get("decider_match_rate"), opponent_shape.get("decider_match_rate")])
        games_over_probability = _mean([pick_shape.get("games_over_22_5_rate"), opponent_shape.get("games_over_22_5_rate")])
        tiebreak_probability = _mean([pick_shape.get("tiebreak_match_rate"), opponent_shape.get("tiebreak_match_rate")])
        sets_selection, sets_probability = _side_selection("sets", SETS_LINE, decider_probability)
        games_selection, games_probability = _side_selection("games", GAMES_LINE, games_over_probability)

        serve = build_api_pro_serve_stats_context(
            pick_player_id=pick_id,
            opponent_player_id=opponent_id,
            surface=surface,
            projected_games=projected_games,
            as_of_date=start,
        )
        quality_label, quality_score = _data_quality(pick_shape, opponent_shape, serve)

        row = {
            "model": "LucQ",
            "layer": "LucQ",
            "lucq_version": LUCQ_VERSION,
            "source": "API PRO",
            "data_source": "API PRO",
            "source_policy": SOURCE_POLICY,
            "event_id": _first(match, "event_id", "match_id", "id"),
            "match_id": _first(match, "match_id", "event_id", "id"),
            "player1": player1,
            "player2": player2,
            "player1_id": player1_id,
            "player2_id": player2_id,
            "pick": pick,
            "opponent": opponent,
            "pick_side": pick_side,
            "pick_player_id": pick_id,
            "opponent_player_id": opponent_id,
            "pick_odds": pick_odds,
            "opponent_odds": opponent_odds,
            "odds_player1": _positive_float(match.get("odds_player1")),
            "odds_player2": _positive_float(match.get("odds_player2")),
            "lucq_probability": winner_probability,
            "lucq_probability_pct": round(winner_probability * 100.0, 1),
            "projected_sets": projected_sets,
            "sets_line": SETS_LINE,
            "sets_selection": sets_selection,
            "sets_probability": sets_probability,
            "projected_games": projected_games,
            "games_line": GAMES_LINE,
            "games_selection": games_selection,
            "games_probability": games_probability,
            "tb_probability": tiebreak_probability,
            "tiebreak_probability": tiebreak_probability,
            "pick_aces_projection": serve.get("pick_aces_projection"),
            "opponent_aces_projection": serve.get("opponent_aces_projection"),
            "total_aces_projection": serve.get("total_aces_projection"),
            "pick_df_projection": serve.get("pick_df_projection"),
            "opponent_df_projection": serve.get("opponent_df_projection"),
            "total_df_projection": serve.get("total_df_projection"),
            "aces_status": serve.get("aces_status"),
            "df_status": serve.get("df_status"),
            "lucq_data_quality": quality_label,
            "lucq_data_quality_score": quality_score,
            "pick_shape_sample": pick_shape.get("sample"),
            "opponent_shape_sample": opponent_shape.get("sample"),
            "pick_shape_scope": pick_shape.get("scope"),
            "opponent_shape_scope": opponent_shape.get("scope"),
            "shape_source": "API_PRO_GET_PREVIOUS_PLAYER_MATCHES",
            "serve_source": serve.get("api_serve_stats_source"),
            "serve_status": serve.get("api_serve_stats_status"),
            "surface": surface,
            "tournament": match.get("tournament"),
            "category": match.get("category"),
            "best_of": match.get("best_of"),
            "match_start": start,
            "start_time": start,
            "status": match.get("status_type"),
            "betting_day": match.get("betting_day") or run_date,
            "odds_endpoint": endpoint,
            "overround": overround,
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
        "row_count": len(rows),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LucQ API PRO analytics output")
    parser.add_argument("--date", required=True, help="Betting day YYYY-MM-DD")
    parser.add_argument("--output", default="outputs/lucq/latest_lucq.json")
    args = parser.parse_args()
    rows = build_lucq_rows(args.date)
    output = write_output(rows, args.output, args.date)
    print(f"LUCQ OUTPUT: {output} rows={len(rows)}")


if __name__ == "__main__":
    main()
