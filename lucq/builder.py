"""LucQ API PRO-only daily analytics builder.

LucQ uses only real API PRO exact-event odds, previous completed singles matches,
and API PRO serve statistics. Missing inputs remain None and render as N/A.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import fetch_daily_matches_with_odds
from thinq.service import (
    _as_of_timestamp,
    _completed_singles_score_shape,
    _fetch_previous_player_matches,
    _surface_bucket,
    build_api_pro_serve_stats_context,
)

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


def _smoothed_rate(successes: int, sample: int) -> Optional[float]:
    """Beta(1,1) smoothing over real observations; avoids false 0%/100%."""
    if sample <= 0:
        return None
    return round((int(successes) + 1.0) / (int(sample) + 2.0), 4)


def _target_datetime(run_date: str) -> datetime:
    day = datetime.strptime(run_date, "%Y-%m-%d").date()
    return datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ)


def _first(match: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = match.get(key)
        if value not in (None, ""):
            return value
    return None




def _nested_entity_id(value: Any) -> Optional[int]:
    if not isinstance(value, dict):
        return None
    for key in ("id", "teamId", "team_id", "playerId", "player_id"):
        raw = value.get(key)
        try:
            if raw not in (None, ""):
                return int(raw)
        except Exception:
            continue
    info = value.get("playerTeamInfo")
    if isinstance(info, dict):
        try:
            raw = info.get("id")
            return int(raw) if raw not in (None, "") else None
        except Exception:
            return None
    return None


def _player_ids(match: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    first = _first(match, "player1_id", "home_team_id", "home_id", "player1Id")
    second = _first(match, "player2_id", "away_team_id", "away_id", "player2Id")
    try:
        first_id = int(first) if first not in (None, "") else None
    except Exception:
        first_id = None
    try:
        second_id = int(second) if second not in (None, "") else None
    except Exception:
        second_id = None
    raw = match.get("raw") if isinstance(match.get("raw"), dict) else {}
    if first_id is None:
        first_id = _nested_entity_id(raw.get("homeTeam") or raw.get("home") or raw.get("player1"))
    if second_id is None:
        second_id = _nested_entity_id(raw.get("awayTeam") or raw.get("away") or raw.get("player2"))
    return first_id, second_id


def _build_real_shape(player_id: Any, surface: Any, as_of_date: Any, best_of: int) -> Dict[str, Any]:
    if player_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "sample": 0, "scope": "none"}
    requested_surface = _surface_bucket(surface)
    as_of_ts = _as_of_timestamp(as_of_date)
    events: List[Dict[str, Any]] = []
    page_results: List[Dict[str, Any]] = []
    for page in range(2):
        result = _fetch_previous_player_matches(player_id, page=page, force_refresh=False)
        page_results.append(result)
        events.extend(item for item in result.get("events", []) if isinstance(item, dict))
        if result.get("status") != "OK" or not result.get("has_next_page"):
            break
        shapes_now = [shape for shape in (_completed_singles_score_shape(event, as_of_ts=as_of_ts) for event in events) if isinstance(shape, dict)]
        surface_count = sum(1 for shape in shapes_now if shape.get("surface") == requested_surface and requested_surface != "Unknown")
        if len(shapes_now) >= 20 and surface_count >= 8:
            break
    shapes = [shape for shape in (_completed_singles_score_shape(event, as_of_ts=as_of_ts) for event in events) if isinstance(shape, dict)]
    shapes.sort(key=lambda item: int(item.get("start_timestamp") or 0), reverse=True)
    surface_shapes = [shape for shape in shapes if shape.get("surface") == requested_surface and requested_surface != "Unknown"]
    selected = surface_shapes[:12]
    scope = "surface"
    if len(selected) < 3:
        selected = shapes[:12]
        scope = "overall"
    sample = len(selected)
    status = "OK" if sample >= 3 else "LOW_SAMPLE" if sample else "NO_DATA"
    if not sample:
        return {"status": status, "sample": 0, "scope": scope, "raw_events": len(events), "pages_fetched": len(page_results)}
    average_sets = round(sum(float(item["sets"]) for item in selected) / sample, 2)
    average_games = round(sum(float(item["games"]) for item in selected) / sample, 2)
    tb_successes = sum(1 for item in selected if int(item.get("tiebreak_sets") or 0) > 0)
    if int(best_of or 3) == 5:
        sets_over_successes = sum(1 for item in selected if int(item.get("sets") or 0) >= 4)
    else:
        sets_over_successes = sum(1 for item in selected if int(item.get("sets") or 0) >= 3)
    games_over_successes = sum(1 for item in selected if float(item.get("games") or 0) > GAMES_LINE)
    # All probabilities remain calculations from real observed matches. Beta(1,1)
    # smoothing only prevents a small sample from being displayed as certain 0/100%.
    tb_rate = _smoothed_rate(tb_successes, sample)
    over_sets_rate = _smoothed_rate(sets_over_successes, sample)
    games_over_rate = _smoothed_rate(games_over_successes, sample)
    return {
        "status": status,
        "sample": sample,
        "scope": scope,
        "average_sets": average_sets if status == "OK" else None,
        "average_games": average_games if status == "OK" else None,
        "tiebreak_match_rate": tb_rate if status == "OK" else None,
        "decider_match_rate": over_sets_rate if status == "OK" else None,
        "games_over_22_5_rate": games_over_rate if status == "OK" else None,
        "raw_events": len(events),
        "pages_fetched": len(page_results),
        "api_statuses": [item.get("status") for item in page_results],
    }

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
    # LucQ displays current API PRO ranks in the first box. Missing rank stays (X).
    os.environ.setdefault("TENNISAPI_ATTACH_RANKINGS", "1")
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
        player1_id, player2_id = _player_ids(match)
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
        best_of = int(match.get("best_of") or 3)
        pick_shape = _build_real_shape(pick_id, surface, start, best_of)
        opponent_shape = _build_real_shape(opponent_id, surface, start, best_of)

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
            "player1_api_rank": match.get("player1_api_rank"),
            "player2_api_rank": match.get("player2_api_rank"),
            "pick_api_rank": match.get("player1_api_rank") if pick_side == "HOME" else match.get("player2_api_rank"),
            "opponent_api_rank": match.get("player2_api_rank") if pick_side == "HOME" else match.get("player1_api_rank"),
            "pick_api_rank_points": match.get("player1_api_rank_points") if pick_side == "HOME" else match.get("player2_api_rank_points"),
            "opponent_api_rank_points": match.get("player2_api_rank_points") if pick_side == "HOME" else match.get("player1_api_rank_points"),
            "pick_odds": pick_odds,
            "opponent_odds": opponent_odds,
            "odds_player1": _positive_float(match.get("odds_player1")),
            "odds_player2": _positive_float(match.get("odds_player2")),
            "winner_probability": winner_probability,
            "winner_probability_pct": round(winner_probability * 100.0, 1),
            "lucq_probability": None,
            "lucq_probability_pct": None,
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
            "best_of": best_of,
            "match_start": start,
            "start_time": start,
            "status": match.get("status_type"),
            "betting_day": match.get("betting_day") or run_date,
            "odds_endpoint": endpoint,
            "overround": overround,
        }

        # LucQ probability is statistical, not match-winner probability.
        # It is the strongest available confidence among Sets, Games and TB.
        statistical_probabilities = [
            value for value in (
                sets_probability,
                games_probability,
                max(tiebreak_probability, 1.0 - tiebreak_probability) if tiebreak_probability is not None else None,
            )
            if value is not None
        ]
        lucq_probability = max(statistical_probabilities) if statistical_probabilities else None
        row["lucq_probability"] = round(lucq_probability, 6) if lucq_probability is not None else None
        row["lucq_probability_pct"] = round(lucq_probability * 100.0, 1) if lucq_probability is not None else None

        # The LucQ page owns its evaluation box. Actual values are populated by
        # the LucQ settlement step when the event is finished. Until then each
        # evaluable market is PENDING; projections without a real line remain
        # PROJECTION_ONLY and are never presented as WON/LOST.
        row.update({
            "lucq_result_status": "PENDING",
            "sets_result_status": "PENDING" if sets_selection else "N/A",
            "games_result_status": "PENDING" if games_selection else "N/A",
            "tb_selection": "YES" if tiebreak_probability is not None and tiebreak_probability >= 0.5 else "NO" if tiebreak_probability is not None else None,
            "tb_result_status": "PENDING" if tiebreak_probability is not None else "N/A",
            "aces_result_status": "PROJECTION_ONLY" if serve.get("total_aces_projection") is not None else "N/A",
            "df_result_status": "PROJECTION_ONLY" if serve.get("total_df_projection") is not None else "N/A",
            "actual_sets": None,
            "actual_games": None,
            "actual_tiebreak": None,
            "actual_pick_aces": None,
            "actual_opponent_aces": None,
            "actual_total_aces": None,
            "actual_pick_df": None,
            "actual_opponent_df": None,
            "actual_total_df": None,
        })
        rows.append(row)

    rows.sort(key=lambda row: (-(float(row.get("lucq_probability") or 0.0)), _start_sort_value(row)))
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
