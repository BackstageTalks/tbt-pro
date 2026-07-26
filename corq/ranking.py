"""CORQ ranking and TOP7 publication quality guard.

Principles:
- ALL stays broad and audit-friendly.
- TOP7 contains only publishable bets.
- Telegram/RSS should read TOP7 only.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TOP_N_DEFAULT = 7
TOP7_FILTER_MODE = "PUBLISHABLE_CORQ_THINQ_GUARD_V1"

MIN_CORQ_PROBABILITY = 0.50
MIN_PICK_THINQ_EDGE = 0.0
MIN_PICK_DATA_DEPTH = 0.40
MIN_ELO_DEPTH_IF_MISSING = 0.50
MIN_THINQ_CONFIDENCE = 0.50
EXTREME_UNKNOWN_ODDS_GAP_PCT = 1.50
MIN_PICK_ODDS = 1.40
MIN_FORM_DATA_DEPTH = 0.40
BRATISLAVA_TZ = "Europe/Bratislava"

OPEN_STATUS_TYPES = {"notstarted", "not_started", "scheduled", "open", "prematch", "pre-match", "upcoming"}
BLOCKED_STATUS_TYPES = {
    "finished", "ended", "complete", "completed", "inprogress", "in_progress", "live", "started",
    "cancelled", "canceled", "postponed", "retired", "walkover", "interrupted", "suspended",
}
CONFIRMED_ODDS_DIRECTIONS = {
    "DIRECT_BY_NUMERIC_OUTCOME", "REVERSED_BY_NUMERIC_OUTCOME", "DIRECT_TO_MATCH_PLAYERS", "REVERSED_TO_MATCH_PLAYERS",
}
UNKNOWN_ODDS_DIRECTIONS = {"DIRECT_OR_LABEL_UNKNOWN", "UNKNOWN", "UNCONFIRMED", "", None}


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text or text in {"—", "-", "None", "null"}:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _prob(value: Any, default: float = 0.0) -> float:
    x = _as_float(value, None)
    if x is None:
        return default
    return x / 100.0 if abs(x) > 1.5 else x


def _get_nested(row: Dict[str, Any], *path: str) -> Any:
    cur: Any = row
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _first(row: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) is not None:
            return row.get(key)
    return default


def _local_today() -> str:
    explicit = os.getenv("CORQ_RUN_DATE") or os.getenv("RUN_DATE") or os.getenv("GITHUB_RUN_DATE")
    if explicit:
        return str(explicit)[:10]
    now = datetime.now(timezone.utc)
    if ZoneInfo is not None:
        now = now.astimezone(ZoneInfo(BRATISLAVA_TZ))
    return now.date().isoformat()


def _parse_match_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _match_date_local(row: Dict[str, Any]) -> Optional[str]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    candidates = [
        row.get("match_start"), row.get("start_time"), row.get("startTimestamp"), row.get("start_timestamp"), row.get("date"),
        raw.get("startTimestamp"), raw.get("start_time"),
    ]
    for value in candidates:
        dt = _parse_match_datetime(value)
        if dt is None:
            txt = str(value or "").strip()
            if len(txt) >= 10 and txt[4:5] == "-":
                return txt[:10]
            continue
        if ZoneInfo is not None:
            dt = dt.astimezone(ZoneInfo(BRATISLAVA_TZ))
        return dt.date().isoformat()
    return None


def is_today_match(row: Dict[str, Any]) -> bool:
    match_day = _match_date_local(row)
    if match_day is None:
        return True
    return match_day == _local_today()


def _flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in (
        "flags", "risk_flags", "corq_risk_flags", "thinq_flags", "corq_warning_flags",
        "reject_reasons", "corq_reject_reasons", "top7_reject_reasons",
    ):
        value = row.get(key)
        if isinstance(value, list):
            out.extend(str(x) for x in value if x is not None)
        elif value:
            out.append(str(value))
    thinq = row.get("thinq")
    if isinstance(thinq, dict):
        value = thinq.get("flags")
        if isinstance(value, list):
            out.extend(str(x) for x in value if x is not None)
    return out


def status_type(row: Dict[str, Any]) -> str:
    raw = _first(row, ["status_type", "match_status_type", "status"], "")
    if not raw:
        raw = _get_nested(row, "raw", "status", "type")
    return str(raw or "").strip().lower().replace(" ", "_")


def status_code(row: Dict[str, Any]) -> Any:
    value = _first(row, ["status_code", "match_status_code"], None)
    if value is None:
        value = _get_nested(row, "raw", "status", "code")
    return value


def is_notstarted(row: Dict[str, Any]) -> bool:
    st = status_type(row)
    code = status_code(row)
    if st in BLOCKED_STATUS_TYPES:
        return False
    if st in OPEN_STATUS_TYPES:
        return True
    if str(code) == "0" and st not in BLOCKED_STATUS_TYPES:
        return True
    return False


def corq_probability(row: Dict[str, Any]) -> float:
    value = _first(row, ["corq_estimated_win_probability", "corq_probability", "win_probability", "corq_win_probability", "corq_score"], None)
    if value is None:
        value = _get_nested(row, "corq", "probability")
    if value is None:
        value = _first(row, ["estimated_win_pct", "win_pct", "probability_pct"], None)
    return _prob(value, 0.0)


def thinq_confidence(row: Dict[str, Any]) -> float:
    value = _first(row, ["thinq_probability_confidence", "thinq_confidence", "thinQ_confidence", "thinq_data_confidence"], None)
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "confidence")
    if value is None:
        value = _get_nested(row, "thinq", "confidence")
    return _prob(value, 0.0)


def pick_thinq_edge(row: Dict[str, Any]) -> float:
    value = _first(row, ["pick_thinq_edge", "thinq_edge", "thinq_probability_edge", "thinq_total_edge"], None)
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "edge")
    if value is None:
        probability = _first(row, ["thinq_probability", "thinq_winner_probability"], None)
        if probability is not None:
            return _prob(probability, 0.5) - 0.5
    return _prob(value, 0.0)


def computed_pick_data_depth(row: Dict[str, Any]) -> float:
    edge = pick_thinq_edge(row)
    if edge <= 0:
        return 0.0
    conf = thinq_confidence(row)
    return max(0.0, min(conf * min(edge / 0.10, 1.0), 1.0))


def pick_data_depth(row: Dict[str, Any]) -> float:
    return computed_pick_data_depth(row)


def form_data_depth(row: Dict[str, Any]) -> float:
    value = _first(row, ["form_data_depth", "form_confidence", "thinq_form_confidence"], None)
    if value is None:
        value = _get_nested(row, "thinq", "recent_form", "form_data_depth")
    if value is None:
        value = _get_nested(row, "thinq", "recent_form", "form_confidence")
    return _prob(value, 0.0)


def pick_odds_value(row: Dict[str, Any]) -> Optional[float]:
    value = _first(row, ["pick_odds", "odds", "selected_odds", "decimal_odds"], None)
    if value is None:
        side = str(row.get("pick_side") or "").upper()
        if side == "AWAY":
            value = _first(row, ["odds_player2", "away_odds", "p2_odds", "odds2", "price2"], None)
        else:
            value = _first(row, ["odds_player1", "home_odds", "p1_odds", "odds1", "price1"], None)
    return _as_float(value, None)


def opponent_odds_value(row: Dict[str, Any]) -> Optional[float]:
    value = _first(row, ["opponent_odds", "opp_odds", "opponent_price"], None)
    if value is None:
        side = str(row.get("pick_side") or "").upper()
        if side == "AWAY":
            value = _first(row, ["odds_player1", "home_odds", "p1_odds", "odds1", "price1"], None)
        else:
            value = _first(row, ["odds_player2", "away_odds", "p2_odds", "odds2", "price2"], None)
    return _as_float(value, None)


def odds_available(row: Dict[str, Any]) -> bool:
    if row.get("odds_pair_available") is True and pick_odds_value(row) is not None and opponent_odds_value(row) is not None:
        return True
    return pick_odds_value(row) is not None and opponent_odds_value(row) is not None


def is_doubles(row: Dict[str, Any]) -> bool:
    if row.get("is_doubles") is True:
        return True
    value = _first(row, ["match_type", "type", "event_type"], "")
    return "double" in str(value).lower()


def side_valid(row: Dict[str, Any]) -> bool:
    audit = row.get("side_audit")
    if isinstance(audit, dict) and "side_valid" in audit:
        return bool(audit.get("side_valid"))
    if "side_valid" in row:
        return bool(row.get("side_valid"))
    return True


def odds_orientation_extreme_risk(row: Dict[str, Any]) -> bool:
    direction = row.get("odds_matching_direction")
    confirmed = row.get("odds_labels_confirmed")
    gap = _as_float(row.get("odds_gap_pct"), 0.0) or 0.0
    if direction in CONFIRMED_ODDS_DIRECTIONS or confirmed is True:
        return False
    unknown = direction in UNKNOWN_ODDS_DIRECTIONS or confirmed is False
    return bool(unknown and gap >= EXTREME_UNKNOWN_ODDS_GAP_PCT)


def elo_unavailable(row: Dict[str, Any]) -> bool:
    flags = set(_flags(row))
    if flags.intersection({"MISSING_ELO", "MISSING_ELO_PICK", "MISSING_ELO_OPPONENT", "ELO_UNAVAILABLE"}):
        return True
    elo_status = _get_nested(row, "thinq", "elo", "status") or row.get("thinq_elo_status")
    if elo_status and str(elo_status).upper() in {"NO_DATA", "MISSING", "UNAVAILABLE", "ERROR"}:
        return True
    p_edge = _first(row, ["thinq_overall_elo_edge", "overall_elo_edge", "elo_edge"], None)
    s_edge = _first(row, ["thinq_surface_elo_edge", "surface_elo_edge"], None)
    if str(elo_status).upper() == "OK":
        return False
    return p_edge is None and s_edge is None


def recent_form_status(row: Dict[str, Any]) -> str:
    status = row.get("thinq_recent_form_status") or _get_nested(row, "thinq", "recent_form", "status")
    return str(status or "UNKNOWN").upper()


def recent_form_reason(row: Dict[str, Any]) -> str:
    return str(row.get("thinq_recent_form_reason") or _get_nested(row, "thinq", "recent_form", "reason") or "")


def recent_form_sample_audit(row: Dict[str, Any]) -> Dict[str, Any]:
    rf = _get_nested(row, "thinq", "recent_form")
    if not isinstance(rf, dict):
        rf = row.get("recent_form") if isinstance(row.get("recent_form"), dict) else {}
    pick = rf.get("pick") if isinstance(rf.get("pick"), dict) else {}
    opp = rf.get("opponent") if isinstance(rf.get("opponent"), dict) else {}
    return {
        "status": recent_form_status(row),
        "reason": recent_form_reason(row),
        "pick_last10_count": _as_float(_get_nested(pick, "last10", "count"), 0.0),
        "opponent_last10_count": _as_float(_get_nested(opp, "last10", "count"), 0.0),
        "pick_surface_count": _as_float(_get_nested(pick, "surface_last10", "count"), 0.0),
        "opponent_surface_count": _as_float(_get_nested(opp, "surface_last10", "count"), 0.0),
        "history_match_count": _get_nested(rf, "history_status", "match_count"),
    }


def low_data_risk_audit(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "corq_probability": round(corq_probability(row), 6),
        "pick_thinq_edge": round(pick_thinq_edge(row), 6),
        "pick_data_depth": round(pick_data_depth(row), 6),
        "form_data_depth": round(form_data_depth(row), 6),
        "thinq_confidence": round(thinq_confidence(row), 6),
        "elo_coverage_missing": elo_unavailable(row),
        "recent_form": recent_form_sample_audit(row),
        "odds_available": odds_available(row),
    }


def top7_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    cp = corq_probability(row)
    edge = pick_thinq_edge(row)
    depth = pick_data_depth(row)
    form_depth = form_data_depth(row)
    conf = thinq_confidence(row)
    odds = pick_odds_value(row)

    if not is_notstarted(row):
        reasons.append("REJECT_TOP7_STATUS_NOT_PREMATCH")
    if not is_today_match(row):
        reasons.append("REJECT_TOP7_NOT_TODAY_MATCH")
    if cp < MIN_CORQ_PROBABILITY:
        reasons.append("REJECT_TOP7_CORQ_BELOW_50")
    if edge < MIN_PICK_THINQ_EDGE:
        reasons.append("REJECT_TOP7_THINQ_EDGE_AGAINST_PICK")
    if depth < MIN_PICK_DATA_DEPTH:
        reasons.append("REJECT_TOP7_LOW_PICK_DATA_DEPTH")
    if conf < MIN_THINQ_CONFIDENCE:
        reasons.append("REJECT_TOP7_LOW_THINQ_CONFIDENCE")
    if form_depth < MIN_FORM_DATA_DEPTH:
        reasons.append("REJECT_TOP7_LOW_FORM_DATA_DEPTH")
    if not odds_available(row):
        reasons.append("REJECT_TOP7_MISSING_ODDS")
    if odds is not None and odds < MIN_PICK_ODDS:
        reasons.append("REJECT_TOP7_LOW_ODDS_UNDER_1_40")
    if is_doubles(row):
        reasons.append("REJECT_TOP7_DOUBLES")
    if not side_valid(row):
        reasons.append("REJECT_TOP7_INVALID_SIDE_ORIENTATION")
    if odds_orientation_extreme_risk(row):
        reasons.append("REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME")
    if elo_unavailable(row) and depth < MIN_ELO_DEPTH_IF_MISSING:
        reasons.append("REJECT_TOP7_ELO_COVERAGE_MISSING_LOW_DEPTH")

    return reasons


def publishable_for_top7(row: Dict[str, Any]) -> bool:
    return not top7_reject_reasons(row)


def top7_quality_score(row: Dict[str, Any]) -> float:
    return round(
        corq_probability(row) * 100.0
        + pick_data_depth(row) * 25.0
        + thinq_confidence(row) * 15.0
        + max(pick_thinq_edge(row), 0.0) * 100.0 * 0.10
        + form_data_depth(row) * 5.0,
        4,
    )


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    reasons = top7_reject_reasons(row)
    row["top7_publishable"] = not reasons
    row["top7_quality_reject_reasons"] = reasons
    row["top7_filter_mode"] = TOP7_FILTER_MODE
    row["top7_corq_probability"] = round(corq_probability(row), 6)
    row["top7_pick_thinq_edge"] = round(pick_thinq_edge(row), 6)
    row["top7_thinq_confidence"] = round(thinq_confidence(row), 6)
    row["pick_data_depth"] = round(pick_data_depth(row), 6)
    row["stat_data_depth"] = round(pick_data_depth(row), 6)
    row["form_data_depth"] = round(form_data_depth(row), 6)
    row["top7_quality_score"] = top7_quality_score(row)
    row["recent_form_sample_audit"] = recent_form_sample_audit(row)
    row["low_data_risk_audit"] = low_data_risk_audit(row)
    return row


def annotate_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        new_row = row if isinstance(row, dict) else {}
        new_row.setdefault("corq_source_rank", idx)
        annotate_top7_quality(new_row)
        annotated.append(new_row)
    return annotated


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        [r for r in rows if r.get("top7_publishable") is True],
        key=lambda r: (
            top7_quality_score(r),
            corq_probability(r),
            pick_data_depth(r),
            max(pick_thinq_edge(r), 0.0),
            thinq_confidence(r),
            pick_odds_value(r) or 0.0,
        ),
        reverse=True,
    )


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    annotated = annotate_rows(rows)
    publishable = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen_matches = set()
    for row in publishable:
        key = row.get("match_key") or row.get("event_id") or row.get("id") or "|".join(sorted([
            str(row.get("player1") or row.get("home") or ""),
            str(row.get("player2") or row.get("away") or ""),
        ]))
        if key in seen_matches:
            continue
        seen_matches.add(key)
        selected.append(row)
        if len(selected) >= top_n:
            break
    for idx, row in enumerate(selected, start=1):
        row["top7_rank"] = idx
        row["corq_rank"] = idx
    return selected


def rank_predictions(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    all_rows = annotate_rows(list(predictions or []))
    top7 = select_top7(all_rows, top_n=top_n)
    return all_rows, top7


def build_all_and_top7(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n=top_n)


def build_rankings(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n=top_n)


def apply_ranking(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return rank_predictions(predictions, top_n=top_n)


def evaluate_eligibility(row: Dict[str, Any]) -> Dict[str, Any]:
    return annotate_top7_quality(row)


def is_publishable(row: Dict[str, Any]) -> bool:
    return publishable_for_top7(row)


def _ranking_score(row: Dict[str, Any]) -> float:
    return round(corq_probability(row) * 100.0 + max(pick_thinq_edge(row), 0.0) * 10.0 + pick_data_depth(row) * 5.0, 4)


def make_all_match_view(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    rows = [r for r in annotate_rows(list(predictions or [])) if is_today_match(r)]
    return sorted(rows, key=_ranking_score, reverse=True)


def rank_corq(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return make_all_match_view(predictions, *args, **kwargs)


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return select_top7(list(ranked or []), top_n=top_n)
