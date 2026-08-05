from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from .common import (
    as_float,
    dedupe_match_rows,
    flags,
    json_rows,
    match_identity,
    normalize_name,
    now_iso,
    opponent_name,
    opponent_odds,
    pick_name,
    pick_odds,
    probability,
    read_json,
    row_date,
    run_date_from_payload,
    side_identity,
    write_json,
)
from .provider import event_id, fetch_event_detail, score_from_event, status_from_obj, winner_from_event

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
RESULTS_DIR = OUTPUTS / "results"
SNAPSHOTS_DIR = OUTPUTS / "snapshots"


def existing_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {side_identity(row): row for row in rows if isinstance(row, dict)}


def source_candidates(kind: str) -> List[Path]:
    if kind == "corq":
        return [
            SNAPSHOTS_DIR / "latest_corq_top7_snapshot.json",
            OUTPUTS / "latest_top7.json",
        ]
    if kind == "cloq":
        return [
            SNAPSHOTS_DIR / "latest_cloq_snapshot.json",
            OUTPUTS / "cloq" / "latest_cloq.json",
            OUTPUTS / "latest_cloq.json",
        ]
    return [
        SNAPSHOTS_DIR / "latest_all_audit_snapshot.json",
        OUTPUTS / "latest_audit.json",
        OUTPUTS / "latest_all.json",
    ]


def load_source_rows(kind: str) -> Tuple[Any, List[Dict[str, Any]], str]:
    for path in source_candidates(kind):
        payload = read_json(path, None)
        rows = json_rows(payload)
        if rows:
            return payload, rows, str(path)
    return {}, [], ""


def snapshot_status(row: Dict[str, Any]) -> str:
    raw = row.get("status") or row.get("status_type") or row.get("match_status_type") or row.get("event_status")
    if not raw and isinstance(row.get("raw"), dict):
        raw = ((row.get("raw") or {}).get("status") or {}).get("type")
    return status_from_obj(raw)


def snapshot_winner(row: Dict[str, Any]) -> str:
    winner = row.get("winner") or row.get("match_winner")
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if not winner and raw:
        winner = winner_from_event(raw)
    return str(winner or "").strip()


def snapshot_score(row: Dict[str, Any]) -> Tuple[str, Optional[int], Optional[int], bool]:
    for key in ("score", "result_score", "final_score"):
        if row.get(key):
            return str(row[key]), None, None, False
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if raw:
        return score_from_event(raw)
    return "", None, None, False


def is_void_status(*values: Any) -> bool:
    text = " ".join(str(v or "") for v in values).upper()
    void_tokens = (
        "RET", "RETIRED", "RETIREMENT", "SCR", "SCRATCH", "WALKOVER", "WO",
        "ABANDON", "CANCEL", "CANCELED", "CANCELLED", "VOID", "POSTPONED",
    )
    return any(token in text for token in void_tokens)


def result_from_winner(row: Dict[str, Any], winner: str, status: str) -> Tuple[str, Optional[float]]:
    if is_void_status(status, winner, row.get("score"), row.get("final_score")):
        return "VOID", 0.0
    if winner:
        if normalize_name(winner) == normalize_name(pick_name(row)):
            odds = pick_odds(row)
            return "WON", round((odds or 1.0) - 1.0, 4) if odds else None
        return "LOST", -1.0
    explicit = str(row.get("result") or row.get("result_status") or "").upper()
    if explicit in {"WON", "WIN"}:
        odds = pick_odds(row)
        return "WON", round((odds or 1.0) - 1.0, 4) if odds else None
    if explicit in {"LOST", "LOSS"}:
        return "LOST", -1.0
    if explicit == "VOID":
        return "VOID", 0.0
    if status in {"cancelled", "canceled", "postponed", "walkover", "retired", "abandoned"}:
        return "VOID", 0.0
    return "PENDING", None


def preserve_existing(out: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> None:
    if not existing:
        return
    for key in (
        "winner", "score", "final_score", "actual_sets", "actual_games", "actual_tiebreak",
        "source", "result_source", "status", "result_status", "result", "units",
    ):
        if existing.get(key) not in (None, "") and out.get(key) in (None, ""):
            out[key] = existing.get(key)



# ---------------------------------------------------------------------------
# Results prediction snapshot helpers
# ---------------------------------------------------------------------------
def first_value(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first non-empty value from a row, supporting dotted paths."""
    for key in keys:
        cur: Any = row
        ok = True
        for part in str(key).split('.'):
            if isinstance(cur, dict) and part in cur:
                cur = cur.get(part)
            else:
                ok = False
                break
        if ok and cur not in (None, "", "—", "-"):
            return cur
    return default


def pct_to_float(value: Any) -> Optional[float]:
    val = as_float(value, None)
    if val is None:
        return None
    return val / 100.0 if abs(val) > 1.5 else val


def pct_points(value: Any) -> Optional[float]:
    val = as_float(value, None)
    if val is None:
        return None
    return val * 100.0 if abs(val) <= 1.5 else val


def bool_hit_from_ou(selection: Any, actual: Optional[float]) -> Optional[bool]:
    if actual is None:
        return None
    text = str(selection or "").strip().upper().replace(" ", "")
    if not text:
        return None
    m = re.search(r"([OU])\s*([0-9]+(?:[\.,][0-9]+)?)", text)
    if not m:
        return None
    side = m.group(1)
    line = as_float(m.group(2).replace(',', '.'), None)
    if line is None:
        return None
    if side == "O":
        return actual > line
    if side == "U":
        return actual < line
    return None


def hit_label(value: Optional[bool]) -> str:
    if value is True:
        return "HIT"
    if value is False:
        return "MISS"
    return "PENDING"


def fmt_record_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, "", "—", "-"):
        return None
    return value


def extract_actual_match_stats(event: Optional[Dict[str, Any]], pick: str, opponent: str) -> Dict[str, Any]:
    """Best-effort extraction of actual aces/DF from event detail.

    TennisApi sometimes exposes post-match event statistics in different nested
    shapes. This parser is intentionally conservative: if it cannot map a stat
    to both sides, it returns None instead of fabricating values.
    """
    out = {
        "actual_pick_aces": None,
        "actual_opponent_aces": None,
        "actual_total_aces": None,
        "actual_pick_df": None,
        "actual_opponent_df": None,
        "actual_total_df": None,
        "actual_stats_source": "UNAVAILABLE",
    }
    if not isinstance(event, dict):
        return out

    def side_name(side: str) -> str:
        team = event.get('homeTeam') if side == 'home' else event.get('awayTeam')
        if isinstance(team, dict):
            return str(team.get('name') or team.get('shortName') or '').strip()
        return ''

    side_for_pick = None
    if normalize_name(side_name('home')) == normalize_name(pick):
        side_for_pick = 'home'
    elif normalize_name(side_name('away')) == normalize_name(pick):
        side_for_pick = 'away'
    if not side_for_pick:
        return out
    side_for_opp = 'away' if side_for_pick == 'home' else 'home'

    stat_pairs: Dict[str, Dict[str, Optional[float]]] = {
        'aces': {'home': None, 'away': None},
        'df': {'home': None, 'away': None},
    }

    def classify_stat_name(name: Any) -> Optional[str]:
        n = str(name or '').strip().lower().replace('_', ' ')
        if 'double' in n and 'fault' in n:
            return 'df'
        if n in {'df', 'double faults', 'double fault'}:
            return 'df'
        if 'ace' in n or n == 'aces':
            return 'aces'
        return None

    def parse_node(obj: Any) -> None:
        if isinstance(obj, dict):
            stat_kind = classify_stat_name(obj.get('name') or obj.get('stat') or obj.get('label') or obj.get('type'))
            if stat_kind:
                home_val = first_value(obj, 'home', 'homeValue', 'homeTeamValue', 'valueHome', 'homeStat')
                away_val = first_value(obj, 'away', 'awayValue', 'awayTeamValue', 'valueAway', 'awayStat')
                if home_val is not None or away_val is not None:
                    stat_pairs[stat_kind]['home'] = as_float(home_val, None)
                    stat_pairs[stat_kind]['away'] = as_float(away_val, None)
                # Some APIs use values arrays.
                values = obj.get('values') or obj.get('statistics')
                if isinstance(values, list) and len(values) >= 2:
                    stat_pairs[stat_kind]['home'] = as_float(values[0].get('value') if isinstance(values[0], dict) else values[0], None)
                    stat_pairs[stat_kind]['away'] = as_float(values[1].get('value') if isinstance(values[1], dict) else values[1], None)
            for value in obj.values():
                parse_node(value)
        elif isinstance(obj, list):
            for value in obj:
                parse_node(value)

    for key in ('statistics', 'eventStatistics', 'playerStatistics', 'matchStatistics', 'stats'):
        parse_node(event.get(key))

    for kind in ('aces', 'df'):
        pick_val = stat_pairs[kind].get(side_for_pick)
        opp_val = stat_pairs[kind].get(side_for_opp)
        if pick_val is not None:
            out[f'actual_pick_{"aces" if kind == "aces" else "df"}'] = pick_val
        if opp_val is not None:
            out[f'actual_opponent_{"aces" if kind == "aces" else "df"}'] = opp_val
        if pick_val is not None and opp_val is not None:
            out[f'actual_total_{"aces" if kind == "aces" else "df"}'] = pick_val + opp_val
            out['actual_stats_source'] = 'EVENT_DETAIL_STATS'
    return out


def prediction_snapshot_from_row(out: Dict[str, Any]) -> Dict[str, Any]:
    """Store the prediction exactly as it was published for later audit."""
    return {
        "corq": {
            "probability": probability(out),
            "raw_model_probability": first_value(out, 'corq_raw_model_probability', 'thinq_pick_probability'),
            "calibrated_probability": first_value(out, 'corq_calibrated_probability', 'corq_probability'),
            "market_adjustment_pp": first_value(out, 'corq_market_adjustment_pp', 'market_adjustment_pp'),
        },
        "mmx": {
            "thinq_weight": first_value(out, 'corq_thinq_weight', 'thinq_weight', 'model_mix_thinq_weight'),
            "marq_weight": first_value(out, 'corq_marq_weight', 'marq_weight', 'model_mix_marq_weight'),
            "thinq_input_pp": first_value(out, 'corq_thinq_input_pp', 'thinq_input_pp'),
            "marq_input_pp": first_value(out, 'corq_marq_input_pp', 'marq_input_pp'),
        },
        "thinq": {
            "pick_probability": first_value(out, 'thinq_pick_probability', 'top7_thinq_pick_probability', 'thinq_probability_layer.pick_probability'),
            "data_confidence": first_value(out, 'thinq_data_confidence', 'thinq_confidence', 'confidence'),
            "edge": first_value(out, 'pick_thinq_edge', 'top7_pick_thinq_edge', 'thinq_edge'),
            "form_data_depth": first_value(out, 'form_data_depth', 'form_confidence'),
            "recent_form_source": first_value(out, 'recent_form_source', 'recent_form.source'),
            "recent_form_freshness_status": first_value(out, 'recent_form_freshness_status', 'recent_form.freshness_status'),
        },
        "marq": {
            "pick_probability": first_value(out, 'marq_crowd_pick_pct', 'marq_pick_probability', 'corq_market_probability'),
            "opponent_probability": first_value(out, 'marq_crowd_opponent_pct', 'marq_opponent_probability'),
            "edge_pct": first_value(out, 'marq_edge_pct', 'marq_edge'),
            "range": first_value(out, 'marq_internal_range', 'marq_move_range', 'move_range'),
            "move": first_value(out, 'marq_internal_move_signal', 'marq_move_signal', 'market_move'),
            "clv_pp": first_value(out, 'marq_internal_clv_pp', 'marq_clv_pct'),
            "final": first_value(out, 'marq_final', 'marq_market_final', 'market_final'),
            "source": first_value(out, 'marq_source', 'marq_market_source'),
            "quality_signal": first_value(out, 'marq_quality_signal'),
        },
        "elo_h2h_form": {
            "overall_elo_edge": first_value(out, 'thinq_overall_elo_edge', 'overall_elo_edge'),
            "surface_elo_edge": first_value(out, 'thinq_surface_elo_edge', 'surface_elo_edge'),
            "h2h_raw_edge": first_value(out, 'thinq_h2h_raw_edge', 'h2h_raw_edge'),
            "h2h_effective_edge": first_value(out, 'thinq_h2h_effective_edge', 'h2h_effective_edge', 'h2h_edge'),
            "h2h_total_matches": first_value(out, 'thinq_h2h_total_matches', 'h2h_total_matches'),
            "same_surface_h2h_matches": first_value(out, 'thinq_h2h_same_surface_matches', 'same_surface_h2h_matches'),
            "recent_form_edge": first_value(out, 'recent_form_edge', 'short_form_edge'),
            "surface_recent_form_edge": first_value(out, 'surface_recent_form_edge'),
            "opponent_quality_edge": first_value(out, 'opponent_quality_edge'),
        },
        "sets_games": {
            "projected_sets": first_value(out, 'ta_projected_sets', 'thinq_projected_sets', 'projected_sets'),
            "projected_games": first_value(out, 'ta_projected_games', 'thinq_projected_games', 'projected_games'),
            "sets_selection": first_value(out, 'sets_selection', 'sets_display'),
            "sets_probability": first_value(out, 'sets_probability', 'sets_probability_pct'),
            "sets_line": first_value(out, 'sets_line'),
            "games_selection": first_value(out, 'games_selection', 'games_display'),
            "games_probability": first_value(out, 'games_probability', 'games_probability_pct'),
            "games_line": first_value(out, 'games_line'),
            "tb_probability": first_value(out, 'tb_probability', 'tiebreak_probability', 'ta_tiebreak_probability', 'thinq_tiebreak_probability'),
            "market_source": first_value(out, 'sets_games_market_source', 'sets_model_source'),
            "raw_market_count": first_value(out, 'sets_games_raw_market_count'),
            "data_depth": first_value(out, 'sets_games_data_depth', 's_data_depth', 'stat_data_depth'),
        },
        "aces_df": {
            "aces_pick_selection": first_value(out, 'pick_aces_selection'),
            "aces_opponent_selection": first_value(out, 'opponent_aces_selection'),
            "aces_total_selection": first_value(out, 'total_aces_selection'),
            "aces_pick_projection": first_value(out, 'pick_aces_projection'),
            "aces_opponent_projection": first_value(out, 'opponent_aces_projection'),
            "aces_total_projection": first_value(out, 'total_aces_projection'),
            "aces_pick_line_source": first_value(out, 'pick_aces_line_source'),
            "aces_opponent_line_source": first_value(out, 'opponent_aces_line_source'),
            "aces_total_line_source": first_value(out, 'total_aces_line_source'),
            "df_pick_selection": first_value(out, 'pick_df_selection'),
            "df_opponent_selection": first_value(out, 'opponent_df_selection'),
            "df_total_selection": first_value(out, 'total_df_selection'),
            "df_pick_projection": first_value(out, 'pick_df_projection'),
            "df_opponent_projection": first_value(out, 'opponent_df_projection'),
            "df_total_projection": first_value(out, 'total_df_projection'),
            "df_pick_line_source": first_value(out, 'pick_df_line_source'),
            "df_opponent_line_source": first_value(out, 'opponent_df_line_source'),
            "df_total_line_source": first_value(out, 'total_df_line_source'),
            "serve_stats_source": first_value(out, 'api_serve_stats_source', 'serve_stats_source'),
        },
    }


def evaluate_row(
    row: Dict[str, Any],
    model: str,
    run_date: str,
    source_snapshot: str,
    fetch_api: bool,
    cache: Dict[int, Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
    local_tz: str = "Europe/Bratislava",
) -> Dict[str, Any]:
    out = dict(row)
    preserve_existing(out, existing)

    status = snapshot_status(row)
    winner = snapshot_winner(row) or str(out.get("winner") or "").strip()
    score, actual_sets, actual_games, actual_tiebreak = snapshot_score(row)
    event: Optional[Dict[str, Any]] = None

    if out.get("score") and not score:
        score = str(out.get("score"))
    if out.get("actual_sets") is not None and actual_sets is None:
        actual_sets = int(as_float(out.get("actual_sets"), 0) or 0)
    if out.get("actual_games") is not None and actual_games is None:
        actual_games = int(as_float(out.get("actual_games"), 0) or 0)
    if out.get("actual_tiebreak") is not None:
        actual_tiebreak = bool(out.get("actual_tiebreak"))

    event_fetch_status = "NOT_REQUESTED"
    if fetch_api:
        eid = event_id(row)
        if eid is not None:
            event, event_fetch_status = fetch_event_detail(eid, cache)
            if event:
                status = status_from_obj(event.get("status"))
                winner = winner_from_event(event) or winner
                event_score, event_sets, event_games, event_tb = score_from_event(event)
                score = event_score or score
                actual_sets = event_sets if event_sets is not None else actual_sets
                actual_games = event_games if event_games is not None else actual_games
                actual_tiebreak = event_tb
        else:
            event_fetch_status = "NO_EVENT_ID"

    result, units = result_from_winner({**out, "winner": winner, "score": score, "status": status}, winner, status)
    projected_sets = as_float(first_value(out, "ta_projected_sets", "thinq_projected_sets", "projected_sets"), None)
    projected_games = as_float(first_value(out, "ta_projected_games", "thinq_projected_games", "projected_games"), None)
    games_error = round(actual_games - projected_games, 2) if actual_games is not None and projected_games is not None else None
    sets_hit_projection = round(projected_sets) == actual_sets if actual_sets is not None and projected_sets is not None else None

    sets_selection = first_value(out, "sets_selection", "sets_display")
    games_selection = first_value(out, "games_selection", "games_display")
    tb_probability = first_value(out, "tb_probability", "tiebreak_probability", "ta_tiebreak_probability", "thinq_tiebreak_probability")
    sets_ou_hit = bool_hit_from_ou(sets_selection, actual_sets)
    games_ou_hit = bool_hit_from_ou(games_selection, actual_games)
    tb_projected_hit = None
    tb_prob_num = pct_to_float(tb_probability)
    if actual_tiebreak is not None and tb_prob_num is not None:
        # We treat TB >= 50% as the model calling a tiebreak.
        tb_projected_hit = (tb_prob_num >= 0.5) == bool(actual_tiebreak)

    actual_stats = extract_actual_match_stats(event, pick_name(out), opponent_name(out))
    out.update(actual_stats)
    aces_total_hit = None
    df_total_hit = None
    if actual_stats.get("actual_total_aces") is not None:
        aces_total_hit = bool_hit_from_ou(first_value(out, "total_aces_selection"), actual_stats.get("actual_total_aces"))
    if actual_stats.get("actual_total_df") is not None:
        df_total_hit = bool_hit_from_ou(first_value(out, "total_df_selection"), actual_stats.get("actual_total_df"))

    prediction_snapshot = prediction_snapshot_from_row(out)

    out.update({
        "date": result_row_date(out, run_date, local_tz),
        "model": model,
        "source_snapshot": source_snapshot,
        "snapshot_source": first_value(out, "snapshot_source", default=("CORQ_DAILY" if model == "corq" else model.upper())),
        "snapshot_type": first_value(out, "snapshot_type", default=("DAILY_CORQ_SNAPSHOT" if model == "corq" else f"DAILY_{model.upper()}_SNAPSHOT")),
        "snapshot_functional_day": first_value(out, "snapshot_functional_day", "functional_day", "betting_day", "snapshot_date", default=result_row_date(out, run_date, local_tz)),
        "snapshot_date": first_value(out, "snapshot_date", "betting_day", default=result_row_date(out, run_date, local_tz)),
        "betting_day": first_value(out, "betting_day", "snapshot_date", "functional_day", "snapshot_functional_day", default=result_row_date(out, run_date, local_tz)),
        "betting_day_start_local": first_value(out, "betting_day_start_local"),
        "betting_day_end_local": first_value(out, "betting_day_end_local"),
        "snapshot_run_time": first_value(out, "snapshot_run_time", "snapshot_created_at_utc", default=now_iso()),
        "match_id": out.get("match_id") or out.get("event_id") or out.get("id"),
        "pick": pick_name(out),
        "opponent": opponent_name(out),
        "pick_odds": pick_odds(out),
        "opponent_odds": opponent_odds(out),
        "corq_probability": probability(out),
        "thinq_pick_probability": first_value(out, "thinq_pick_probability", "top7_thinq_pick_probability", "thinq_probability_layer.pick_probability"),
        "thinq_data_confidence": first_value(out, "thinq_data_confidence", "thinq_confidence", "confidence"),
        "mmx_thinq_weight": first_value(out, "corq_thinq_weight", "thinq_weight", "model_mix_thinq_weight"),
        "mmx_marq_weight": first_value(out, "corq_marq_weight", "marq_weight", "model_mix_marq_weight"),
        "marq_pick_probability": first_value(out, "marq_crowd_pick_pct", "marq_pick_probability", "corq_market_probability"),
        "marq_edge_pct": first_value(out, "marq_edge_pct", "marq_edge"),
        "marq_move": first_value(out, "marq_internal_move_signal", "marq_move_signal", "market_move"),
        "marq_range": first_value(out, "marq_internal_range", "marq_move_range", "move_range"),
        "marq_clv_pp": first_value(out, "marq_internal_clv_pp", "marq_clv_pct"),
        "status": result,
        "result_status": result,
        "result": result,
        "winner": winner,
        "score": score,
        "final_score": score,
        "units": units,
        "actual_sets": actual_sets,
        "actual_games": actual_games,
        "actual_tiebreak": actual_tiebreak,
        "sets_hit": sets_hit_projection,
        "sets_ou_hit": sets_ou_hit,
        "games_ou_hit": games_ou_hit,
        "tb_hit": tb_projected_hit,
        "total_aces_hit": aces_total_hit,
        "total_df_hit": df_total_hit,
        "games_error": games_error,
        "tags": flags(out),
        "event_fetch_status": event_fetch_status,
        "match_identity": match_identity(out),
        "side_identity": side_identity(out),
        "snapshot_id": first_value(out, "snapshot_id", default=f"{('CORQ_DAILY' if model == 'corq' else model.upper())}:{result_row_date(out, run_date, local_tz)}:{side_identity(out)}"),
        "source_filter": first_value(out, "source_filter", default=("CorQ" if model == "corq" else model.upper())),
        "prediction_snapshot": prediction_snapshot,
    })

    out["sets_games"] = {
        "projected_sets": projected_sets,
        "projected_games": projected_games,
        "sets_selection": sets_selection,
        "sets_probability": first_value(out, "sets_probability", "sets_probability_pct"),
        "sets_line": first_value(out, "sets_line"),
        "games_selection": games_selection,
        "games_probability": first_value(out, "games_probability", "games_probability_pct"),
        "games_line": first_value(out, "games_line"),
        "actual_sets": actual_sets,
        "actual_games": actual_games,
        "sets_projection_hit": sets_hit_projection,
        "sets_ou_hit": sets_ou_hit,
        "games_ou_hit": games_ou_hit,
        "games_error": games_error,
        "actual_tiebreak": actual_tiebreak,
        "tb_probability": tb_probability,
        "tb_hit": tb_projected_hit,
        "three_sets_probability": out.get("ta_decider_probability") or out.get("thinq_decider_probability"),
        "tie_break_probability": tb_probability,
        "market_source": first_value(out, "sets_games_market_source", "sets_model_source"),
        "raw_market_count": first_value(out, "sets_games_raw_market_count"),
    }
    out["aces_df"] = {
        "aces_pick_selection": first_value(out, "pick_aces_selection"),
        "aces_opponent_selection": first_value(out, "opponent_aces_selection"),
        "aces_total_selection": first_value(out, "total_aces_selection"),
        "aces_pick_projection": first_value(out, "pick_aces_projection"),
        "aces_opponent_projection": first_value(out, "opponent_aces_projection"),
        "aces_total_projection": first_value(out, "total_aces_projection"),
        "actual_pick_aces": actual_stats.get("actual_pick_aces"),
        "actual_opponent_aces": actual_stats.get("actual_opponent_aces"),
        "actual_total_aces": actual_stats.get("actual_total_aces"),
        "total_aces_hit": aces_total_hit,
        "df_pick_selection": first_value(out, "pick_df_selection"),
        "df_opponent_selection": first_value(out, "opponent_df_selection"),
        "df_total_selection": first_value(out, "total_df_selection"),
        "df_pick_projection": first_value(out, "pick_df_projection"),
        "df_opponent_projection": first_value(out, "opponent_df_projection"),
        "df_total_projection": first_value(out, "total_df_projection"),
        "actual_pick_df": actual_stats.get("actual_pick_df"),
        "actual_opponent_df": actual_stats.get("actual_opponent_df"),
        "actual_total_df": actual_stats.get("actual_total_df"),
        "total_df_hit": df_total_hit,
        "actual_stats_source": actual_stats.get("actual_stats_source"),
    }
    return out


def summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = sum(1 for r in rows if r.get("result") == "WON")
    lost = sum(1 for r in rows if r.get("result") == "LOST")
    pending = sum(1 for r in rows if r.get("result") == "PENDING")
    void = sum(1 for r in rows if r.get("result") == "VOID")
    settled = won + lost
    units = round(sum(float(r.get("units") or 0.0) for r in rows if r.get("units") is not None), 4)
    return {
        "picks": len(rows),
        "won": won,
        "lost": lost,
        "pending": pending,
        "void": void,
        "win_rate": round(won / settled, 4) if settled else None,
        "units": units,
        "roi": round(units / settled, 4) if settled else None,
    }


def write_model_results(model: str, rows: List[Dict[str, Any]], output_root: Path, run_date: str) -> None:
    write_json(output_root / f"latest_results_{model}.json", rows)
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows or []:
        row_day = str(row.get("date") or run_date)[:10]
        if not re.match(r"^20\d{2}-\d{2}-\d{2}$", row_day):
            row_day = run_date
        by_date.setdefault(row_day, []).append(row)
    if not by_date:
        by_date[run_date] = []
    for row_day, day_rows in by_date.items():
        year, month = row_day[:4], row_day[5:7]
        write_json(output_root / year / month / f"{row_day}_{model}.json", day_rows)


def rebuild_indexes(output_root: Path = RESULTS_DIR) -> None:
    years: List[str] = []
    latest_date: Optional[str] = None
    if not output_root.exists():
        return
    for year_dir in sorted([p for p in output_root.iterdir() if p.is_dir() and p.name.startswith("20")]):
        years.append(year_dir.name)
        months: List[str] = []
        for month_dir in sorted([p for p in year_dir.iterdir() if p.is_dir()]):
            months.append(month_dir.name)
            dates = sorted({p.name[:10] for p in month_dir.glob("20??-??-??_*.json")})
            if dates:
                latest_date = max(latest_date or dates[-1], dates[-1])
            write_json(month_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "month": month_dir.name, "dates": dates})
        write_json(year_dir / "index.json", {"generated_at": now_iso(), "year": year_dir.name, "months": months})
    write_json(output_root / "index.json", {
        "generated_at": now_iso(),
        "years": years,
        "latest_date": latest_date,
        "latest": {
            "corq": "latest_results_corq.json",
            "cloq": "latest_results_cloq.json",
            "audit": "latest_results_audit.json",
        },
    })




def local_yesterday(local_tz: str = "Europe/Bratislava") -> str:
    """Return the previous completed betting day in local time.

    Betting day is 06:00 -> 06:00. If called before 06:00, today's current
    betting day is still yesterday, so the previous completed betting day is
    two calendar dates back.
    """
    if ZoneInfo is not None:
        now_local = datetime.now(ZoneInfo(local_tz))
    else:
        now_local = datetime.now(timezone.utc)
    current_betting_day = now_local.date() - timedelta(days=1) if now_local.hour < FUNCTIONAL_DAY_START_HOUR else now_local.date()
    return (current_betting_day - timedelta(days=1)).isoformat()


FUNCTIONAL_DAY_START_HOUR = 6


def functional_day_for_datetime(dt: Optional[datetime], local_tz: str = "Europe/Bratislava") -> str:
    """Return the tennis functional day for a datetime.

    The project betting day runs 06:00 -> 05:59 Europe/Bratislava. A match at
    03:00 local time belongs to the previous functional day.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if ZoneInfo is not None:
            local_dt = dt.astimezone(ZoneInfo(local_tz))
        else:
            local_dt = dt.astimezone(timezone.utc)
    except Exception:
        local_dt = datetime.now(timezone.utc)
    day = local_dt.date()
    if local_dt.hour < FUNCTIONAL_DAY_START_HOUR:
        day = day - timedelta(days=1)
    return day.isoformat()


def functional_day_now(local_tz: str = "Europe/Bratislava") -> str:
    return functional_day_for_datetime(datetime.now(timezone.utc), local_tz)


def row_start_datetime_utc(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("start_time_utc", "match_time_utc", "commence_time", "start_time", "match_time"):
        value = row.get(key)
        if not value:
            continue
        try:
            raw = str(value).strip()
            if re.match(r"^\d{10,13}$", raw):
                return datetime.fromtimestamp(int(raw[:10]), tz=timezone.utc)
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def result_row_date(row: Dict[str, Any], default_date: str, local_tz: str = "Europe/Bratislava") -> str:
    existing_day = row.get("betting_day") or row.get("snapshot_date") or row.get("functional_day") or row.get("snapshot_functional_day")
    if existing_day:
        return str(existing_day)[:10]
    start_dt = row_start_datetime_utc(row)
    if start_dt is not None:
        return functional_day_for_datetime(start_dt, local_tz)
    explicit = row_date(row, "")
    if explicit:
        try:
            dt = datetime.fromisoformat(str(explicit)[:10] + "T12:00:00+00:00")
            return functional_day_for_datetime(dt, local_tz)
        except Exception:
            return str(explicit)[:10]
    return default_date


def should_fetch_result(row: Dict[str, Any], fetch_api: bool, settlement_grace_hours: float) -> bool:
    if not fetch_api:
        return False
    if settlement_grace_hours <= 0:
        return True
    start_dt = row_start_datetime_utc(row)
    if start_dt is None:
        return True
    return datetime.now(timezone.utc) >= start_dt + timedelta(hours=settlement_grace_hours)


def merge_rows_with_existing_for_settlement(source_rows: List[Dict[str, Any]], existing_rows: List[Dict[str, Any]], settle_date: str) -> List[Dict[str, Any]]:
    """Keep current source rows, plus existing rows for the settlement date.

    After midnight, latest snapshots can already be today's card while yesterday's
    pending bets still need settlement. This keeps yesterday's rows alive.
    """
    by_side: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in source_rows or []:
        key = side_identity(row)
        by_side[key] = row
        order.append(key)
    for row in existing_rows or []:
        if row_date(row, settle_date) != settle_date:
            continue
        key = side_identity(row)
        if key not in by_side:
            by_side[key] = row
            order.append(key)
    return [by_side[key] for key in order]

def merge_current_source_with_existing_results(
    model: str,
    source_rows: List[Dict[str, Any]],
    existing_rows: List[Dict[str, Any]],
    settle_date: str,
) -> Tuple[List[Dict[str, Any]], str]:
    """Merge current source rows with the historical Results ledger.

    Results are a ledger, not a live re-computation of whatever latest_top7.json
    currently contains. If a row already has a prediction_snapshot, the old row
    wins for the same side identity and only settlement fields are updated later.
    This keeps the daily CorQ snapshot immutable for long-term yield/ROI audits.
    """
    existing_by_side: Dict[str, Dict[str, Any]] = {side_identity(r): r for r in existing_rows or [] if isinstance(r, dict)}
    by_side: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    preserved_existing_dupes = 0
    inserted_source = 0
    for row in source_rows or []:
        key = side_identity(row)
        if key not in by_side:
            order.append(key)
        existing_row = existing_by_side.get(key)
        if existing_row and existing_row.get("prediction_snapshot"):
            by_side[key] = existing_row
            preserved_existing_dupes += 1
        else:
            by_side[key] = row
            inserted_source += 1

    added_existing = 0
    for row in existing_rows or []:
        key = side_identity(row)
        if key in by_side:
            continue
        by_side[key] = row
        order.append(key)
        added_existing += 1

    if source_rows and existing_rows:
        mode = f"immutable_ledger_source_plus_existing:{inserted_source}+existing:{added_existing}+preserved:{preserved_existing_dupes}"
    elif source_rows:
        mode = "source_snapshot_initial_seed"
    elif existing_rows:
        mode = "existing_results_only_no_source_rows"
    else:
        mode = "empty_no_source_or_existing"
    return [by_side[key] for key in order], mode


def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR, fetch_api: bool = False, settle_date: Optional[str] = None, settlement_grace_hours: float = 0.0, local_tz: str = "Europe/Bratislava") -> Dict[str, Any]:
    corq_payload, corq_rows, corq_source = load_source_rows("corq")
    cloq_payload, cloq_rows, cloq_source = load_source_rows("cloq")
    audit_payload, audit_rows, audit_source = load_source_rows("audit")
    if settle_date:
        day = str(settle_date)[:10]
    elif run_date:
        day = str(run_date)[:10]
    else:
        day = functional_day_now(local_tz)

    old_corq_rows = json_rows(read_json(output_root / "latest_results_corq.json", []))
    old_cloq_rows = json_rows(read_json(output_root / "latest_results_cloq.json", []))
    old_audit_rows = json_rows(read_json(output_root / "latest_results_audit.json", []))
    old_corq = existing_index(old_corq_rows)
    old_cloq = existing_index(old_cloq_rows)
    old_audit = existing_index(old_audit_rows)

    corq_rows, corq_lock_mode = merge_current_source_with_existing_results("corq", corq_rows, old_corq_rows, day)
    cloq_rows, cloq_lock_mode = merge_current_source_with_existing_results("cloq", cloq_rows, old_cloq_rows, day)
    audit_rows, audit_lock_mode = merge_current_source_with_existing_results("audit", audit_rows, old_audit_rows, day)

    cache: Dict[int, Dict[str, Any]] = {}
    corq_results = [evaluate_row(r, "corq", day, corq_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_corq.get(side_identity(r)), local_tz) for r in corq_rows]
    cloq_results = [evaluate_row(r, "cloq", day, cloq_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_cloq.get(side_identity(r)), local_tz) for r in cloq_rows]
    audit_deduped = dedupe_match_rows(audit_rows)
    audit_results = [evaluate_row(r, "audit", day, audit_source, should_fetch_result(r, fetch_api, settlement_grace_hours), cache, old_audit.get(side_identity(r)), local_tz) for r in audit_deduped]

    write_model_results("corq", corq_results, output_root, day)
    write_model_results("cloq", cloq_results, output_root, day)
    write_model_results("audit", audit_results, output_root, day)
    rebuild_indexes(output_root)

    manifest = {
        "generated_at": now_iso(),
        "date": day,
        "fetch_api": fetch_api,
        "settlement_grace_hours": settlement_grace_hours,
        "local_tz": local_tz,
        "corq_count": len(corq_results),
        "cloq_count": len(cloq_results),
        "audit_count": len(audit_results),
        "summary": {
            "corq": summary(corq_results),
            "cloq": summary(cloq_results),
            "audit": summary(audit_results),
        },
        "summary_by_snapshot_source": {
            "CORQ_DAILY": summary([r for r in corq_results if str(r.get("snapshot_source") or "") == "CORQ_DAILY"]),
        },
        "sources": {
            "corq": corq_source,
            "cloq": cloq_source,
            "audit": audit_source,
        },
        "locks": {
            "corq": corq_lock_mode,
            "cloq": cloq_lock_mode,
            "audit": audit_lock_mode,
        },
        "output_root": str(output_root),
    }
    write_json(output_root / "latest_results_manifest.json", manifest)
    return manifest


def build_results(output_root: str = "outputs", run_date: Optional[str] = None, fetch_api: bool = False, settle_date: Optional[str] = None, settlement_grace_hours: float = 0.0, local_tz: str = "Europe/Bratislava") -> Dict[str, Any]:
    return build_results_database(
        run_date=run_date,
        output_root=Path(output_root) / "results",
        fetch_api=fetch_api,
        settle_date=settle_date,
        settlement_grace_hours=settlement_grace_hours,
        local_tz=local_tz,
    )


# ---------------------------------------------------------------------------
# Telegram CorQ daily snapshot result list
# ---------------------------------------------------------------------------
def _format_tg_day(day: str) -> str:
    try:
        return datetime.fromisoformat(str(day)[:10]).strftime("%d.%m.%y")
    except Exception:
        return str(day or "")[:10]


def _result_status(row: Dict[str, Any]) -> str:
    raw = str(row.get("result") or row.get("result_status") or row.get("status") or "PENDING").upper().strip()
    if raw == "WIN":
        return "WON"
    if raw == "LOSS":
        return "LOST"
    if raw not in {"WON", "LOST", "VOID", "PENDING"}:
        return "PENDING"
    return raw


def _result_icon(status: str) -> str:
    return {
        "WON": "✅",
        "LOST": "❌",
        "VOID": "➖",
        "PENDING": "⏳",
    }.get(status, "⏳")


def _short_tg_name(name: Any) -> str:
    clean = " ".join(str(name or "").split()).strip()
    if not clean:
        return "—"
    parts = clean.split()
    return parts[-1] if len(parts) > 1 else parts[0]


def _fmt_tg_odds(value: Any) -> str:
    num = as_float(value, None)
    return f"{num:.2f}" if num is not None and num > 1.0 else "—"


def _fmt_tg_units(value: Any, status: str) -> str:
    if status == "PENDING":
        return ""
    num = as_float(value, None)
    if num is None:
        return ""
    return f" | {num:+.2f}u"


def _fmt_tg_score(row: Dict[str, Any], status: str) -> str:
    if status == "PENDING":
        return "Pending"
    if status == "VOID":
        score = str(row.get("final_score") or row.get("score") or "VOID").strip()
        return score if score else "VOID"
    score = str(row.get("final_score") or row.get("score") or "").strip()
    winner = str(row.get("winner") or "").strip()
    if score:
        return score
    if winner:
        return f"Winner: {_short_tg_name(winner)}"
    return status.title()


def _fmt_tg_time(row: Dict[str, Any]) -> str:
    for key in ("match_start", "start_time", "start_time_utc", "match_time_utc", "match_time"):
        raw = row.get(key)
        if not raw:
            continue
        try:
            txt = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(txt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if ZoneInfo is not None:
                dt = dt.astimezone(ZoneInfo("Europe/Bratislava"))
            return dt.strftime("%H:%M")
        except Exception:
            pass
    txt = str(row.get("time") or "").strip()
    if txt:
        m = re.search(r"(\d{1,2}:\d{2})", txt)
        if m:
            return m.group(1)
    return "—"


def _tg_row_sort_key(row: Dict[str, Any]) -> Tuple[int, int, str]:
    for key in ("snapshot_rank", "top7_rank", "top7_sort_rank", "corq_rank", "rank"):
        val = as_float(row.get(key), None)
        if val is not None:
            return (0, int(val), str(row.get("match_id") or row.get("id") or ""))
    return (1, 999, str(row.get("match_id") or row.get("id") or ""))


def corq_snapshot_rows_for_day(rows: List[Dict[str, Any]], day: str) -> List[Dict[str, Any]]:
    target = str(day or "")[:10]
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        model = str(row.get("model") or "").lower()
        source = str(row.get("snapshot_source") or row.get("source_filter") or "").upper()
        row_day = str(row.get("betting_day") or row.get("snapshot_date") or row.get("snapshot_functional_day") or row.get("functional_day") or row.get("date") or "")[:10]
        if target and row_day != target:
            continue
        if model == "corq" or source in {"CORQ_DAILY", "CORQ"}:
            out.append(row)
    return sorted(out, key=_tg_row_sort_key)


def build_corq_tg_summary(rows: List[Dict[str, Any]], day: str) -> Dict[str, Any]:
    selected = corq_snapshot_rows_for_day(rows, day)
    won = sum(1 for r in selected if _result_status(r) == "WON")
    lost = sum(1 for r in selected if _result_status(r) == "LOST")
    void = sum(1 for r in selected if _result_status(r) == "VOID")
    pending = sum(1 for r in selected if _result_status(r) == "PENDING")
    settled = won + lost
    units = round(sum(float(r.get("units") or 0.0) for r in selected if r.get("units") is not None), 4)
    roi = round(units / settled, 4) if settled else None
    return {
        "date": str(day)[:10],
        "display_date": _format_tg_day(day),
        "count": len(selected),
        "won": won,
        "lost": lost,
        "void": void,
        "pending": pending,
        "settled": settled,
        "units": units,
        "roi": roi,
        "rows": selected,
    }


def format_corq_tg_summary_message(summary_obj: Dict[str, Any]) -> str:
    day = summary_obj.get("display_date") or _format_tg_day(str(summary_obj.get("date") or ""))
    rows = [r for r in summary_obj.get("rows") or [] if isinstance(r, dict)]
    units = float(summary_obj.get("units") or 0.0)
    roi = summary_obj.get("roi")
    roi_txt = "ROI —" if roi is None else f"ROI {float(roi) * 100:+.1f}%"
    lines = [f"📊 CorQ RESULTS | {day}", ""]
    if not rows:
        lines.append("No previous CorQ snapshot rows found.")
        return "\n".join(lines)
    for idx, row in enumerate(rows, 1):
        status = _result_status(row)
        icon = _result_icon(status)
        pick = _short_tg_name(pick_name(row))
        opp = _short_tg_name(opponent_name(row))
        odds = _fmt_tg_odds(pick_odds(row))
        time_txt = _fmt_tg_time(row)
        score_txt = _fmt_tg_score(row, status)
        unit_txt = _fmt_tg_units(row.get("units"), status)
        lines.append(f"{idx}. {icon} {pick} | {time_txt} | {odds} | vs {opp} | {score_txt}{unit_txt}")
    lines.extend([
        "",
        f"✅{int(summary_obj.get('won') or 0)} "
        f"❌{int(summary_obj.get('lost') or 0)} "
        f"➖{int(summary_obj.get('void') or 0)} "
        f"⏳{int(summary_obj.get('pending') or 0)} | "
        f"{units:+.2f}u | {roi_txt}",
    ])
    return "\n".join(lines)


def write_corq_tg_summary(day: str, output_root: Path = OUTPUTS) -> Dict[str, Any]:
    results_rows = json_rows(read_json(RESULTS_DIR / "latest_results_corq.json", []))
    summary_obj = build_corq_tg_summary(results_rows, day)
    message = format_corq_tg_summary_message(summary_obj)
    telegram_dir = Path(output_root) / "telegram"
    telegram_dir.mkdir(parents=True, exist_ok=True)
    json_summary = dict(summary_obj)
    json_summary["rows"] = [
        {
            "match_id": r.get("match_id") or r.get("event_id") or r.get("id"),
            "pick": pick_name(r),
            "opponent": opponent_name(r),
            "pick_odds": pick_odds(r),
            "status": _result_status(r),
            "icon": _result_icon(_result_status(r)),
            "score": r.get("final_score") or r.get("score"),
            "winner": r.get("winner"),
            "units": r.get("units"),
            "snapshot_rank": r.get("snapshot_rank") or r.get("top7_rank") or r.get("corq_rank"),
        }
        for r in summary_obj.get("rows") or []
    ]
    write_json(telegram_dir / "latest_corq_results_summary.json", json_summary)
    (telegram_dir / "latest_tg_results_message.txt").write_text(message, encoding="utf-8")
    return {**json_summary, "message": message, "output": str(telegram_dir / "latest_tg_results_message.txt")}

def main() -> None:
    parser = argparse.ArgumentParser(description="Build CorQ/CloQ/Audit results files")
    parser.add_argument("legacy_fetch_api", nargs="?", default=None, help="Backward-compatible true/false value")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", dest="run_date", default=None)
    parser.add_argument("--fetch-api", action="store_true")
    parser.add_argument("--settle-date", default=None, help="Explicit settlement date YYYY-MM-DD")
    parser.add_argument("--settle-yesterday", action="store_true", help="Evaluate yesterday in local timezone")
    parser.add_argument("--local-tz", default="Europe/Bratislava", help="Timezone used by --settle-yesterday")
    parser.add_argument("--settlement-grace-hours", type=float, default=0.0, help="Only fetch matches after start time plus this many hours")
    parser.add_argument("--sources", default="corq,cloq,audit", help="Backward-compatible no-op")
    parser.add_argument("--write-tg-summary", action="store_true", help="Write previous CorQ snapshot Telegram result list with per-match status icons")
    parser.add_argument("--tg-summary-date", default=None, help="CorQ snapshot date to summarize for Telegram YYYY-MM-DD")
    parser.add_argument("--telegram-output-root", default=None, help="Output root for outputs/telegram; defaults to --output-root")
    args = parser.parse_args()
    legacy_fetch = str(args.legacy_fetch_api or "").strip().lower() in {"1", "true", "yes", "y", "on"}
    settle_date = args.settle_date
    if args.settle_yesterday and not settle_date:
        settle_date = local_yesterday(args.local_tz)
    manifest = build_results(
        output_root=args.output_root,
        run_date=args.run_date,
        fetch_api=(args.fetch_api or legacy_fetch),
        settle_date=settle_date,
        settlement_grace_hours=args.settlement_grace_hours,
        local_tz=args.local_tz,
    )
    if args.write_tg_summary:
        tg_day = args.tg_summary_date or settle_date or local_yesterday(args.local_tz)
        tg_output_root = Path(args.telegram_output_root or args.output_root)
        tg_summary = write_corq_tg_summary(tg_day, tg_output_root)
        print({"telegram_corq_results_summary": tg_summary})
    print(manifest)


if __name__ == "__main__":
    main()
