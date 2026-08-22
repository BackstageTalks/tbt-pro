"""CORQ ranking and TOP7 selection.

Single canonical implementation. ThinQ/CorQ probabilities are consumed as-is:
- no pair re-normalization,
- NO_PREDICTION never enters TOP7,
- only technical conditions are hard rejects,
- data/risk/value signals affect ordering and remain auditable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TOP_N_DEFAULT = 7
BRATISLAVA_TZ = "Europe/Bratislava"
TOP7_MODEL_VERSION = "CORQ_TOP7_CANONICAL_V12_SYMMETRY"
MIN_PICK_ODDS = 1.40
MIN_FINAL_PROBABILITY = 0.50
SYMMETRY_TOLERANCE = 0.0001

OPEN_STATUS_TYPES = {"notstarted", "not_started", "scheduled", "open", "prematch", "pre-match", "upcoming"}
BLOCKED_STATUS_TYPES = {
    "finished", "ended", "complete", "completed", "inprogress", "in_progress", "live", "started",
    "cancelled", "canceled", "postponed", "retired", "walkover", "interrupted", "suspended",
}
CONFIRMED_ODDS_DIRECTIONS = {
    "DIRECT_BY_NUMERIC_OUTCOME", "REVERSED_BY_NUMERIC_OUTCOME",
    "DIRECT_TO_MATCH_PLAYERS", "REVERSED_TO_MATCH_PLAYERS",
}


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "-", "—", "None", "null"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def _prob(value: Any, default: float = 0.0) -> float:
    number = _as_float(value)
    if number is None:
        return default
    if abs(number) > 1.5:
        number /= 100.0
    return max(0.0, min(1.0, number))


def _nested(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first(row: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _match_datetime(row: Dict[str, Any]) -> Optional[datetime]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for value in (
        row.get("match_start"), row.get("start_time"), row.get("start_time_utc"),
        row.get("match_time_utc"), row.get("scheduled_at"), row.get("startTimestamp"),
        row.get("start_timestamp"), raw.get("startTimestamp"), raw.get("start_time"),
    ):
        dt = _parse_datetime(value)
        if dt is not None:
            return dt
    return None


def _functional_day(dt: datetime) -> str:
    if ZoneInfo is None:
        local = dt.astimezone(timezone.utc)
    else:
        local = dt.astimezone(ZoneInfo(BRATISLAVA_TZ))
    day = local.date() - timedelta(days=1) if local.hour < 6 else local.date()
    return day.isoformat()


def _run_day() -> str:
    explicit = os.getenv("CORQ_RUN_DATE") or os.getenv("RUN_DATE") or os.getenv("GITHUB_RUN_DATE")
    if explicit:
        return str(explicit)[:10]
    now = datetime.now(timezone.utc)
    return _functional_day(now)


def is_today_match(row: Dict[str, Any]) -> bool:
    explicit = row.get("betting_day") or row.get("snapshot_functional_day") or row.get("functional_day")
    if explicit:
        return str(explicit)[:10] == _run_day()
    dt = _match_datetime(row)
    return True if dt is None else _functional_day(dt) == _run_day()


def status_type(row: Dict[str, Any]) -> str:
    value = _first(row, ("status_type", "match_status_type", "status"), "")
    if isinstance(value, dict):
        value = value.get("type") or value.get("description")
    if not value:
        value = _nested(row, "raw", "status", "type")
    return str(value or "").strip().lower().replace(" ", "_")


def is_notstarted(row: Dict[str, Any]) -> bool:
    status = status_type(row)
    if status in BLOCKED_STATUS_TYPES:
        return False
    if status in OPEN_STATUS_TYPES:
        return True
    code = _first(row, ("status_code", "match_status_code"), _nested(row, "raw", "status", "code"))
    return str(code) == "0" and status not in BLOCKED_STATUS_TYPES


def side_valid(row: Dict[str, Any]) -> bool:
    audit = row.get("side_audit")
    if isinstance(audit, dict) and "side_valid" in audit:
        return bool(audit.get("side_valid"))
    return bool(row.get("side_valid", True))


def is_doubles(row: Dict[str, Any]) -> bool:
    if row.get("is_doubles") is True:
        return True
    value = _first(row, ("match_type", "type", "event_type"), "")
    return "double" in str(value).lower()


def pick_odds_value(row: Dict[str, Any]) -> Optional[float]:
    value = _first(row, ("pick_odds", "odds", "odds_player1", "home_odds", "p1_odds", "price1"))
    odds = _as_float(value)
    return odds if odds is not None and odds > 1.0 else None


def odds_available(row: Dict[str, Any]) -> bool:
    return pick_odds_value(row) is not None


def odds_orientation_extreme_risk(row: Dict[str, Any]) -> bool:
    direction = str(row.get("odds_matching_direction") or "")
    if direction in CONFIRMED_ODDS_DIRECTIONS or row.get("odds_labels_confirmed") is True:
        return False
    gap = _as_float(row.get("odds_gap_pct"), 0.0) or 0.0
    return gap >= 1.50


def corq_probability(row: Dict[str, Any]) -> float:
    value = _first(row, (
        "corq_probability", "corq_estimated_win_probability", "corq_calibrated_probability",
        "probability", "win_probability", "corq_score",
    ))
    return _prob(value, 0.0)


def thinq_pick_probability(row: Dict[str, Any]) -> float:
    value = _first(row, ("thinq_pick_probability", "thinq_probability"))
    if value is None:
        value = _nested(row, "thinq", "thinq_probability_layer", "pick_probability")
    if value is None:
        value = _nested(row, "thinq_probability_layer", "pick_probability")
    return _prob(value, 0.0)


def thinq_confidence(row: Dict[str, Any]) -> float:
    value = _first(row, ("thinq_data_confidence", "thinq_probability_confidence", "thinq_confidence"))
    if value is None:
        value = _nested(row, "thinq", "confidence")
    return _prob(value, 0.0)


def form_data_depth(row: Dict[str, Any]) -> float:
    value = _first(row, ("form_data_depth", "thinq_form_confidence"))
    if value is None:
        value = _nested(row, "thinq", "recent_form", "form_data_depth")
    return _prob(value, 0.0)


def pick_data_depth(row: Dict[str, Any]) -> float:
    form = form_data_depth(row)
    confidence = thinq_confidence(row)
    h2h_sample = _as_float(_first(row, ("thinq_h2h_total_matches", "h2h_total_matches")), 0.0) or 0.0
    h2h_depth = min(h2h_sample / 5.0, 1.0)
    elo_ok = str(_first(row, ("thinq_elo_status",), _nested(row, "thinq", "elo", "status")) or "").upper() == "OK"
    return round(max(0.0, min(1.0, 0.45 * confidence + 0.40 * form + 0.10 * h2h_depth + 0.05 * float(elo_ok))), 6)


def pick_thinq_edge(row: Dict[str, Any]) -> float:
    probability = thinq_pick_probability(row)
    return round(probability - 0.50, 6)


def prediction_status(row: Dict[str, Any]) -> str:
    status = _first(row, ("corq_prediction_status", "thinq_prediction_status"))
    if status is None:
        status = _nested(row, "thinq", "thinq_probability_layer", "prediction_status")
    if status is None:
        status = _nested(row, "thinq_probability_layer", "prediction_status")
    return str(status or "PREDICTION").upper()


def no_prediction(row: Dict[str, Any]) -> bool:
    if prediction_status(row) == "NO_PREDICTION":
        return True
    winner = _first(row, ("corq_winner", "thinq_winner"))
    return corq_probability(row) == 0.50 and thinq_pick_probability(row) == 0.50 and winner is None


def _match_key(row: Dict[str, Any]) -> str:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for value in (
        row.get("match_key"), row.get("event_key"), row.get("event_id"), row.get("match_id"),
        row.get("id"), raw.get("id"), raw.get("customId"), row.get("event_custom_id"),
    ):
        if value not in (None, ""):
            return f"event:{value}"
    player1 = str(row.get("player1") or row.get("home_player") or "").strip().lower()
    player2 = str(row.get("player2") or row.get("away_player") or "").strip().lower()
    start = str(_first(row, ("start_time_utc", "match_time_utc", "scheduled_at", "start_time"), ""))
    return "fallback:" + "|".join(sorted((player1, player2))) + "|" + start


def symmetry_audit(rows: Iterable[Dict[str, Any]], tolerance: float = SYMMETRY_TOLERANCE) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if isinstance(row, dict):
            groups.setdefault(_match_key(row), []).append(row)
    checked = passed = failed = incomplete = 0
    failures: List[Dict[str, Any]] = []
    for key, group in groups.items():
        if len(group) < 2:
            incomplete += 1
            continue
        home = next((x for x in group if str(x.get("pick_side") or "").upper() == "HOME"), None)
        away = next((x for x in group if str(x.get("pick_side") or "").upper() == "AWAY"), None)
        if home is None or away is None:
            incomplete += 1
            continue
        checked += 1
        hp, ap = corq_probability(home), corq_probability(away)
        h_edge = _as_float(home.get("corq_edge"), hp - 0.50) or 0.0
        a_edge = _as_float(away.get("corq_edge"), ap - 0.50) or 0.0
        probability_ok = abs((hp + ap) - 1.0) <= tolerance
        edge_ok = abs(h_edge + a_edge) <= tolerance
        tie_ok = not ((hp == 0.50 or ap == 0.50) and (not no_prediction(home) or not no_prediction(away)))
        if probability_ok and edge_ok and tie_ok:
            passed += 1
        else:
            failed += 1
            failures.append({
                "match_key": key, "home_probability": hp, "away_probability": ap,
                "probability_sum": round(hp + ap, 8), "edge_sum": round(h_edge + a_edge, 8),
                "probability_ok": probability_ok, "edge_ok": edge_ok, "tie_ok": tie_ok,
            })
    return {
        "status": "PASS" if failed == 0 else "FAIL", "model_version": TOP7_MODEL_VERSION,
        "checked_pairs": checked, "passed_pairs": passed, "failed_pairs": failed,
        "incomplete_pairs": incomplete, "tolerance": tolerance, "failures": failures,
    }


def hard_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    if no_prediction(row): reasons.append("REJECT_TOP7_NO_PREDICTION")
    if not is_today_match(row): reasons.append("REJECT_TOP7_NOT_TODAY_MATCH")
    if not is_notstarted(row): reasons.append("REJECT_TOP7_STATUS_NOT_PREMATCH")
    if not odds_available(row): reasons.append("REJECT_TOP7_MISSING_ODDS")
    if is_doubles(row): reasons.append("REJECT_TOP7_DOUBLES")
    if not side_valid(row): reasons.append("REJECT_TOP7_INVALID_SIDE_ORIENTATION")
    if odds_orientation_extreme_risk(row): reasons.append("REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME")
    odds = pick_odds_value(row)
    if odds is not None and odds < MIN_PICK_ODDS: reasons.append("REJECT_TOP7_LOW_ODDS_UNDER_1_40")
    if corq_probability(row) < MIN_FINAL_PROBABILITY: reasons.append("REJECT_TOP7_CORQ_BELOW_50")
    return _unique(reasons)


def soft_penalty_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    if pick_thinq_edge(row) < 0: reasons.append("PENALTY_THINQ_EDGE_AGAINST_PICK")
    if pick_data_depth(row) < 0.70: reasons.append("PENALTY_LOW_DATA_DEPTH")
    if form_data_depth(row) < 0.60: reasons.append("PENALTY_LOW_FORM_DEPTH")
    if thinq_confidence(row) < 0.65: reasons.append("PENALTY_LOW_THINQ_CONFIDENCE")
    value = _as_float(_first(row, ("corq_value_delta_pp", "value_delta_pp")))
    if value is not None and value < 0: reasons.append("PENALTY_NEGATIVE_VALUE_DELTA")
    expected = _as_float(_first(row, ("expected_value_pct", "ev_pct")))
    if expected is not None and expected < 0: reasons.append("PENALTY_NEGATIVE_EXPECTED_VALUE")
    if (pick_odds_value(row) or 99.0) < 1.55: reasons.append("PENALTY_SHORT_PRICE")
    return _unique(reasons)


def support_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    if pick_thinq_edge(row) >= 0.04: tags.append("PICK_STRONG")
    if pick_data_depth(row) >= 0.75: tags.append("HIGH_DATA_DEPTH")
    if form_data_depth(row) >= 0.70: tags.append("STRONG_FORM_DATA")
    if thinq_confidence(row) >= 0.75: tags.append("HIGH_THINQ_CONFIDENCE")
    value = _as_float(_first(row, ("corq_value_delta_pp", "value_delta_pp")))
    if value is not None and value >= 3.0: tags.append("POSITIVE_VALUE")
    return _unique(tags)


def quality_score(row: Dict[str, Any]) -> float:
    probability = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    form = form_data_depth(row) * 100.0
    confidence = thinq_confidence(row) * 100.0
    edge = pick_thinq_edge(row) * 100.0
    value = _as_float(_first(row, ("corq_value_delta_pp", "value_delta_pp")), 0.0) or 0.0
    expected = _as_float(_first(row, ("expected_value_pct", "ev_pct")), 0.0) or 0.0
    penalties = len(soft_penalty_reasons(row)) * 2.0
    bonus = len(support_tags(row)) * 1.0
    score = probability + 0.18 * depth + 0.08 * form + 0.08 * confidence + 0.20 * edge
    score += max(min(value, 8.0), -12.0) * 0.20
    score += max(min(expected, 10.0), -15.0) * 0.08
    return round(score - penalties + bonus, 4)


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    hard = hard_reject_reasons(row)
    soft = soft_penalty_reasons(row)
    support = support_tags(row)
    row["top7_filter_mode"] = TOP7_MODEL_VERSION
    row["top7_publishable"] = not hard
    row["eligible_for_top7"] = not hard
    row["corq_top7_selectable"] = not hard
    row["top7_hard_reject_reasons"] = hard
    row["top7_reject_reasons"] = hard
    row["top7_quality_reject_reasons"] = hard
    row["top7_primary_reject_reason"] = hard[0] if hard else None
    row["top7_reject_reason_count"] = len(hard)
    row["top7_soft_penalty_reasons"] = soft
    row["top7_soft_penalty_count"] = len(soft)
    row["top7_support_tags"] = support
    row["top7_positive_support_count"] = len(support)
    row["top7_pick_data_depth"] = pick_data_depth(row)
    row["top7_form_data_depth"] = form_data_depth(row)
    row["top7_quality_score"] = quality_score(row) if not hard else 0.0
    row["corq_top7_sort_score"] = row["top7_quality_score"]
    row["top7_selection_model_version"] = TOP7_MODEL_VERSION
    row["corq_no_prediction"] = no_prediction(row)
    return row


def annotate_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for index, row in enumerate(rows or [], 1):
        if not isinstance(row, dict):
            continue
        row.setdefault("corq_source_rank", index)
        out.append(annotate_top7_quality(row))
    audit = symmetry_audit(out)
    for row in out:
        row["corq_symmetry_audit_status"] = audit["status"]
        row["corq_symmetry_audit_model_version"] = TOP7_MODEL_VERSION
    return out


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    data = [row for row in rows if isinstance(row, dict) and row.get("top7_publishable") is True]
    return sorted(data, key=lambda row: (
        quality_score(row), corq_probability(row), pick_data_depth(row),
        thinq_confidence(row), pick_odds_value(row) or 0.0,
    ), reverse=True)


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    annotated = annotate_rows(rows)
    ranked = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen = set()
    for row in ranked:
        key = _match_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= int(top_n or TOP_N_DEFAULT):
            break
    for index, row in enumerate(selected, 1):
        row["top7_rank"] = index
    return selected


def make_all_match_view(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return annotate_rows(predictions)


def rank_corq(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    rows = annotate_rows(predictions)
    return sorted(rows, key=lambda row: (quality_score(row), corq_probability(row)), reverse=True)


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return select_top7(ranked, top_n=top_n)


def rank_predictions(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    all_rows = annotate_rows(predictions)
    return all_rows, select_top7(all_rows, top_n=top_n)


def build_all_and_top7(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n)


def build_rankings(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n)


def apply_ranking(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n)


def evaluate_eligibility(row: Dict[str, Any]) -> Dict[str, Any]:
    return annotate_top7_quality(row)


def is_publishable(row: Dict[str, Any]) -> bool:
    return not hard_reject_reasons(row)
