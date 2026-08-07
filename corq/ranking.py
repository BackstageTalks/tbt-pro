"""CORQ ranking and TOP7 publication quality guard.

Principles:
- ALL stays broad and audit-friendly.
- TOP7 contains only publishable bets.
- Telegram/RSS should read TOP7 only.

This module is intentionally defensive and dictionary-based because the runtime
can contain rows from different stages of the pipeline.  It accepts both newer
and older field names and writes explicit audit fields back to each row.
"""

from __future__ import annotations

from copy import deepcopy
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

OPEN_STATUS_TYPES = {
    "notstarted",
    "not_started",
    "scheduled",
    "open",
    "prematch",
    "pre-match",
    "upcoming",
}

BLOCKED_STATUS_TYPES = {
    "finished",
    "ended",
    "complete",
    "completed",
    "inprogress",
    "in_progress",
    "live",
    "started",
    "cancelled",
    "canceled",
    "postponed",
    "retired",
    "walkover",
    "interrupted",
    "suspended",
}

CONFIRMED_ODDS_DIRECTIONS = {
    "DIRECT_BY_NUMERIC_OUTCOME",
    "REVERSED_BY_NUMERIC_OUTCOME",
    "DIRECT_TO_MATCH_PLAYERS",
    "REVERSED_TO_MATCH_PLAYERS",
}

UNKNOWN_ODDS_DIRECTIONS = {
    "DIRECT_OR_LABEL_UNKNOWN",
    "UNKNOWN",
    "UNCONFIRMED",
    "",
    None,
}


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return default
    text = str(value).strip().replace("%", "")
    if not text or text in {"—", "-", "None", "null"}:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _prob(value: Any, default: float = 0.0) -> float:
    """Return probability as 0..1 from either 0..1 or 0..100 input."""
    x = _as_float(value, None)
    if x is None:
        return default
    if x > 1.5:
        return x / 100.0
    return x


def _percent(value: Any, default: float = 0.0) -> float:
    """Return percentage points, e.g. 0.61 -> 61.0 and 61 -> 61."""
    x = _as_float(value, None)
    if x is None:
        return default
    if -1.5 <= x <= 1.5:
        return x * 100.0
    return x


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
        row.get("match_start"),
        row.get("start_time"),
        row.get("startTimestamp"),
        row.get("start_timestamp"),
        row.get("date"),
        raw.get("startTimestamp"),
        raw.get("start_time"),
    ]
    for value in candidates:
        dt = _parse_match_datetime(value)
        if dt is None:
            # Some rows can already carry YYYY-MM-DD date strings.
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
        # Keep undated rows in ALL, but TOP7 will still be protected by status/odds/data guards.
        return True
    return match_day == _local_today()

def _flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in (
        "flags",
        "risk_flags",
        "corq_risk_flags",
        "thinq_flags",
        "corq_warning_flags",
        "reject_reasons",
        "corq_reject_reasons",
        "top7_reject_reasons",
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
    # TennisApi commonly uses status.code 0 for not-started/pre-match.
    if str(code) == "0" and st not in BLOCKED_STATUS_TYPES:
        return True
    return False


def corq_probability(row: Dict[str, Any]) -> float:
    value = _first(
        row,
        [
            "corq_estimated_win_probability",
            "corq_probability",
            "win_probability",
            "corq_win_probability",
            "corq_score",
        ],
        None,
    )
    if value is None:
        value = _get_nested(row, "corq", "probability")
    if value is None:
        pct = _first(row, ["estimated_win_pct", "win_pct", "probability_pct"], None)
        return _prob(pct, 0.0)
    return _prob(value, 0.0)


def thinq_confidence(row: Dict[str, Any]) -> float:
    """Return data/model confidence, not win probability."""
    value = _first(
        row,
        [
            "thinq_data_confidence",
            "thinq_probability_confidence",
            "thinq_confidence",
            "thinQ_confidence",
            "data_confidence",
        ],
        None,
    )
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "confidence")
    if value is None:
        value = _get_nested(row, "thinq", "thinq_data_confidence")
    if value is None:
        value = _get_nested(row, "thinq", "confidence")
    return _prob(value, 0.0)


def thinq_pick_probability(row: Dict[str, Any]) -> float:
    """Return displayed model pick probability, not confidence.

    Real ThinQ probability is preferred.  If ThinQ attach failed but the CorQ/MMx
    layer still produced a raw model probability, use that as the display/model
    fallback. Missing values stay missing internally by returning 0 only as the
    final numeric guard for legacy callers.
    """
    failed = bool(row.get("thinq_error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (row.get("thinq_flags") or []))
    thinq = row.get("thinq")
    if isinstance(thinq, dict):
        failed = failed or bool(thinq.get("error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (thinq.get("flags") or []))
    value = None
    for key in (
        "thinq_pick_probability",
        "thinq_probability",
        "top7_thinq_pick_probability",
        "corq_thinq_probability",
        "corq_raw_model_probability",
    ):
        candidate = row.get(key)
        if candidate is None:
            continue
        parsed = _as_float(candidate, None)
        if parsed is not None and failed and abs(parsed) < 1e-12 and key != "corq_raw_model_probability":
            continue
        value = candidate
        break
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "pick_probability")
    if value is None:
        value = _get_nested(row, "thinq", "thinq_probability_layer", "pick_probability")
    if value is None:
        value = _get_nested(row, "thinq", "probability_layer", "pick_probability")
    return _prob(value, 0.0)


def pick_thinq_edge(row: Dict[str, Any]) -> float:
    """Return ThinQ edge from pick perspective as 0..1.

    Positive supports the displayed pick. Negative goes against it.
    """
    value = _first(
        row,
        [
            "pick_thinq_edge",
            "thinq_edge",
            "thinq_total_edge",
            "thinq_probability_edge",
        ],
        None,
    )
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "edge")
    if value is None:
        p = _first(row, ["thinq_probability", "thinq_winner_probability"], None)
        if p is None:
            p = _get_nested(row, "thinq_probability_layer", "probability")
        if p is not None:
            return _prob(p, 0.50) - 0.50
        # Fallback to CORQ edge around 50 if no ThinQ probability exists.
        cp = corq_probability(row)
        return cp - 0.50 if cp else 0.0
    return _percent(value, 0.0) / 100.0


def computed_pick_data_depth(row: Dict[str, Any]) -> float:
    """Compute statistical support for the displayed pick as 0..1.

    Data depth is coverage/quality, not pick support. A negative ThinQ edge
    should reject the candidate via THINQ_EDGE_AGAINST_PICK, but it should not
    make the data depth falsely look like zero.
    """
    conf = thinq_confidence(row)
    form = form_data_depth(row)
    elo_score = 0.35 if not elo_unavailable(row) else 0.0
    form_score = min(form, 1.0) * 0.45
    conf_score = min(conf, 1.0) * 0.20
    return round(max(0.0, min(elo_score + form_score + conf_score, 1.0)), 6)
def pick_data_depth(row: Dict[str, Any]) -> float:
    # Always recompute to avoid the older duplicate behavior where this field
    # simply copied ThinQ confidence.
    return computed_pick_data_depth(row)




def form_data_depth(row: Dict[str, Any]) -> float:
    """Return form-layer data depth as 0..1.

    This is separate from overall ThinQ confidence.  A match can have strong
    ELO/H2H support but weak form depth.  For TOP7 we require at least a basic
    form data floor, because public picks should not be built on empty recent form.
    """
    for key in ("form_data_depth", "form_confidence", "thinq_form_confidence"):
        value = row.get(key)
        x = _prob(value, -1.0)
        if x >= 0:
            return max(0.0, min(x, 1.0))
    rf = _get_nested(row, "thinq", "recent_form")
    if isinstance(rf, dict):
        for key in ("form_data_depth", "form_confidence"):
            x = _prob(rf.get(key), -1.0)
            if x >= 0:
                return max(0.0, min(x, 1.0))
    return 0.0


def pick_odds_value(row: Dict[str, Any]) -> Optional[float]:
    value = _first(row, ["pick_odds", "odds", "odds_player1", "home_odds", "p1_odds", "price1"], None)
    return _as_float(value, None)

def odds_available(row: Dict[str, Any]) -> bool:
    if row.get("odds_pair_available") is True:
        return True
    p1 = _first(row, ["odds_player1", "home_odds", "p1_odds", "odds1", "price1", "pick_odds", "odds"], None)
    p2 = _first(row, ["odds_player2", "away_odds", "p2_odds", "odds2", "price2", "opponent_odds", "opp_odds"], None)
    if _as_float(p1, None) is not None and _as_float(p2, None) is not None:
        return True
    # For already expanded side candidate, at least pick odds must exist.
    return _as_float(p1, None) is not None


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
    # If no side audit exists, do not silently fail closed for legacy rows that
    # predate side_audit.  Missing audit is still marked for ALL notes elsewhere.
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
    # Do not treat true 0.0 as missing if the explicit status is OK.
    if str(elo_status).upper() == "OK":
        return False
    if p_edge is None and s_edge is None:
        return True
    return False


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

    if not is_today_match(row):
        reasons.append("REJECT_TOP7_NOT_TODAY_MATCH")
    if not is_notstarted(row):
        reasons.append("REJECT_TOP7_STATUS_NOT_PREMATCH")
    odds_value = pick_odds_value(row)
    if odds_value is not None and odds_value < MIN_PICK_ODDS:
        reasons.append("REJECT_TOP7_LOW_ODDS_UNDER_1_40")
    if cp < MIN_CORQ_PROBABILITY:
        reasons.append("REJECT_TOP7_CORQ_BELOW_50")
    if edge < MIN_PICK_THINQ_EDGE:
        reasons.append("REJECT_TOP7_THINQ_EDGE_AGAINST_PICK")
    if depth < MIN_PICK_DATA_DEPTH:
        reasons.append("REJECT_TOP7_LOW_PICK_DATA_DEPTH")
    if thinq_confidence(row) < MIN_THINQ_CONFIDENCE:
        reasons.append("REJECT_TOP7_LOW_THINQ_CONFIDENCE")
    if form_data_depth(row) < MIN_FORM_DATA_DEPTH:
        reasons.append("REJECT_TOP7_LOW_FORM_DATA_DEPTH")
    if not odds_available(row):
        reasons.append("REJECT_TOP7_MISSING_ODDS")
    if is_doubles(row):
        reasons.append("REJECT_TOP7_DOUBLES")
    if not side_valid(row):
        reasons.append("REJECT_TOP7_INVALID_SIDE_ORIENTATION")
    if odds_orientation_extreme_risk(row):
        reasons.append("REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME")
    if elo_unavailable(row) and depth < MIN_ELO_DEPTH_IF_MISSING:
        reasons.append("REJECT_TOP7_ELO_UNAVAILABLE_LOW_DEPTH")
    return reasons


TOP7_REJECT_PRIORITY = [
    "REJECT_TOP7_NOT_TODAY_MATCH",
    "REJECT_TOP7_STATUS_NOT_PREMATCH",
    "REJECT_TOP7_MISSING_ODDS",
    "REJECT_TOP7_INVALID_SIDE_ORIENTATION",
    "REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME",
    "REJECT_TOP7_DOUBLES",
    "REJECT_TOP7_LOW_ODDS_UNDER_1_40",
    "REJECT_TOP7_CORQ_BELOW_50",
    "REJECT_TOP7_THINQ_EDGE_AGAINST_PICK",
    "REJECT_TOP7_LOW_PICK_DATA_DEPTH",
    "REJECT_TOP7_LOW_THINQ_CONFIDENCE",
    "REJECT_TOP7_LOW_FORM_DATA_DEPTH",
    "REJECT_TOP7_ELO_UNAVAILABLE_LOW_DEPTH",
]


def top7_primary_reject_reason(reasons: Sequence[str]) -> Optional[str]:
    if not reasons:
        return None
    reason_set = set(str(x) for x in reasons if x)
    for reason in TOP7_REJECT_PRIORITY:
        if reason in reason_set:
            return reason
    return str(reasons[0]) if reasons else None


def publishable_for_top7(row: Dict[str, Any]) -> bool:
    return not top7_reject_reasons(row)


def h2h_pick_opp_counts(row: Dict[str, Any]) -> Tuple[int, int, int]:
    h2h = _get_nested(row, "thinq", "h2h")
    if not isinstance(h2h, dict):
        h2h = {}
    pick_w = int(_as_float(h2h.get("pick_wins") or row.get("thinq_h2h_pick_wins"), 0) or 0)
    opp_w = int(_as_float(h2h.get("opponent_wins") or row.get("thinq_h2h_opponent_wins"), 0) or 0)
    total = int(_as_float(h2h.get("total_matches") or row.get("thinq_h2h_total_matches"), pick_w + opp_w) or 0)
    return pick_w, opp_w, total


def surface_h2h_pick_opp_counts(row: Dict[str, Any]) -> Tuple[int, int, int]:
    h2h = _get_nested(row, "thinq", "h2h")
    if not isinstance(h2h, dict):
        h2h = {}
    matches = int(_as_float(h2h.get("same_surface_matches") or row.get("thinq_h2h_same_surface_matches"), 0) or 0)
    pick_w = int(_as_float(h2h.get("same_surface_pick_wins") or row.get("thinq_h2h_same_surface_pick_wins"), 0) or 0)
    opp_w = max(matches - pick_w, 0)
    return pick_w, opp_w, matches


def h2h_edge_value(row: Dict[str, Any]) -> float:
    value = _first(row, ["h2h_edge", "thinq_h2h_edge"], None)
    if value is None:
        value = _get_nested(row, "thinq", "h2h", "edge")
    return _percent(value, 0.0) / 100.0


def recent_pick_form_counts(row: Dict[str, Any]) -> Tuple[int, int, int]:
    rf = _get_nested(row, "thinq", "recent_form")
    if not isinstance(rf, dict):
        rf = row.get("recent_form") if isinstance(row.get("recent_form"), dict) else {}
    pick = rf.get("pick") if isinstance(rf.get("pick"), dict) else {}
    wins = int(_as_float(_get_nested(pick, "last10", "wins"), _as_float(row.get("pick_recent_wins"), 0)) or 0)
    losses = int(_as_float(_get_nested(pick, "last10", "losses"), _as_float(row.get("pick_recent_losses"), 0)) or 0)
    count = int(_as_float(_get_nested(pick, "last10", "count"), wins + losses) or 0)
    return wins, losses, count


def recent_surface_edge_value(row: Dict[str, Any]) -> float:
    value = _first(row, ["surface_recent_form_edge", "pick_surface_edge", "surface_edge", "thinq_surface_recent_form_edge"], None)
    if value is None:
        value = _get_nested(row, "thinq", "recent_form", "surface_recent_form_edge")
    return _percent(value, 0.0) / 100.0


def opponent_odds_value(row: Dict[str, Any]) -> Optional[float]:
    value = _first(row, ["opponent_odds", "opp_odds", "odds_player2", "away_odds", "p2_odds", "price2"], None)
    return _as_float(value, None)


def top7_risk_assessment(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return risk tags, public labels, penalty points and bonus points for TOP7 sorting.

    These are ranking modifiers only. They do not hard-reject a pick. The goal is
    to prefer cleaner publishable picks when enough alternatives exist, while
    keeping risk situations available for ALL/Results audit.
    """
    tags: List[str] = []
    labels: List[str] = []
    details: List[Dict[str, Any]] = []
    penalty = 0.0
    bonus = 0.0

    cp = corq_probability(row)
    edge = pick_thinq_edge(row)
    depth = pick_data_depth(row)
    fdepth = form_data_depth(row)
    conf = thinq_confidence(row)
    pick_odds = pick_odds_value(row)
    opp_odds = opponent_odds_value(row)

    h2h_pick, h2h_opp, h2h_total = h2h_pick_opp_counts(row)
    h2h_edge = h2h_edge_value(row)
    h2h_against = (h2h_total >= 3 and h2h_opp - h2h_pick >= 3) or h2h_edge <= -0.03
    if h2h_against:
        tags.append("H2H_STRONG_AGAINST_PICK")
        labels.append("H2H strongly against pick")
        details.append({"tag": "H2H_STRONG_AGAINST_PICK", "penalty": 6.0, "h2h_pick_wins": h2h_pick, "h2h_opponent_wins": h2h_opp, "h2h_edge": round(h2h_edge, 6)})
        penalty += 6.0
        if cp >= 0.50 and edge > 0:
            tags.append("MODEL_SUPPORT_H2H_DISAGREE")
            labels.append("Model support, H2H disagrees")

    sh2h_pick, sh2h_opp, sh2h_total = surface_h2h_pick_opp_counts(row)
    surface_h2h_against = sh2h_total >= 2 and sh2h_opp > sh2h_pick
    if surface_h2h_against:
        tags.append("SURFACE_H2H_AGAINST_PICK")
        labels.append("Surface H2H against pick")
        details.append({"tag": "SURFACE_H2H_AGAINST_PICK", "penalty": 2.5, "surface_h2h_pick_wins": sh2h_pick, "surface_h2h_opponent_wins": sh2h_opp})
        penalty += 2.5

    form_w, form_l, form_count = recent_pick_form_counts(row)
    surface_edge = recent_surface_edge_value(row)
    form_risk = form_count >= 6 and form_w <= 2 and surface_edge < 0 and edge > 0 and cp >= 0.50
    if form_risk:
        tags.append("FORM_RISK_MODEL_SUPPORT")
        labels.append("Form risk, model support")
        details.append({"tag": "FORM_RISK_MODEL_SUPPORT", "penalty": 2.0, "pick_form_wins": form_w, "pick_form_losses": form_l, "surface_edge": round(surface_edge, 6)})
        penalty += 2.0

    market_against = pick_odds is not None and opp_odds is not None and pick_odds >= 2.80 and opp_odds <= 1.45
    if market_against:
        tags.append("MARKET_STRONG_AGAINST_PICK")
        labels.append("Market strongly against pick")
        details.append({"tag": "MARKET_STRONG_AGAINST_PICK", "penalty": 3.0, "pick_odds": pick_odds, "opponent_odds": opp_odds})
        penalty += 3.0
        if cp >= 0.58:
            tags.append("MODEL_SUPPORT_MARKET_DISAGREE")
            labels.append("Model support, market disagrees")

    primary_risk_count = len({t for t in tags if t in {"H2H_STRONG_AGAINST_PICK", "SURFACE_H2H_AGAINST_PICK", "FORM_RISK_MODEL_SUPPORT", "MARKET_STRONG_AGAINST_PICK"}})
    if primary_risk_count >= 2:
        tags.append("MULTI_RISK_PICK")
        labels.append("Multiple risk signals")
        details.append({"tag": "MULTI_RISK_PICK", "penalty": 2.0, "risk_count": primary_risk_count})
        penalty += 2.0

    clean_pick = (
        not tags
        and cp >= 0.55
        and edge >= 0.03
        and depth >= 0.70
        and fdepth >= 0.70
        and conf >= 0.70
        and pick_odds is not None
        and 1.40 <= pick_odds <= 2.20
    )
    if clean_pick:
        tags.append("CLEAN_MODEL_SUPPORT")
        labels.append("Clean model support")
        details.append({"tag": "CLEAN_MODEL_SUPPORT", "bonus": 3.0})
        bonus += 3.0

    # De-duplicate while preserving order.
    seen_tags = set()
    unique_tags: List[str] = []
    for tag in tags:
        if tag not in seen_tags:
            seen_tags.add(tag)
            unique_tags.append(tag)
    seen_labels = set()
    unique_labels: List[str] = []
    for label in labels:
        if label not in seen_labels:
            seen_labels.add(label)
            unique_labels.append(label)

    return {
        "tags": unique_tags,
        "labels": unique_labels,
        "details": details,
        "penalty_points": round(penalty, 4),
        "bonus_points": round(bonus, 4),
        "net_points": round(bonus - penalty, 4),
    }


def top7_quality_score(row: Dict[str, Any]) -> float:
    """Score among already publishable candidates.

    Odds are deliberately *not* a primary driver.  The score favors high final
    CorQ probability, actual pick support, ThinQ edge and data quality, then
    applies soft risk penalties/bonuses. Risk penalties do not reject a pick;
    they only push risk-heavy candidates lower if cleaner alternatives exist.
    """
    cp = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    edge = max(pick_thinq_edge(row), 0.0) * 100.0
    conf = thinq_confidence(row) * 100.0
    # Confidence is data quality, not directional support. It can only amplify
    # confirmed positive ThinQ edge, never act as a standalone pick bonus.
    confidence_weighted_edge = (conf / 100.0) * edge
    risk = top7_risk_assessment(row)
    raw = cp + 0.25 * depth + 0.25 * edge + 0.10 * confidence_weighted_edge
    return round(raw - float(risk.get("penalty_points") or 0.0) + float(risk.get("bonus_points") or 0.0), 4)


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    reasons = top7_reject_reasons(row)
    cp = corq_probability(row)
    edge = pick_thinq_edge(row)
    conf = thinq_confidence(row)
    depth = pick_data_depth(row)

    publishable = not reasons
    status_allowed = is_notstarted(row)
    row["top7_filter_mode"] = TOP7_FILTER_MODE
    row["top7_publishable"] = publishable
    row["eligible_for_top7"] = publishable
    # These are hard TOP7 reject reasons. They are intentionally empty for
    # publishable rows. Workflow summaries should count this field only on
    # non-publishable diagnostic rows, not on selected TOP7 rows.
    row["top7_quality_reject_reasons"] = reasons
    row["top7_reject_reasons"] = reasons
    row["top7_hard_reject_reasons"] = reasons
    row["top7_primary_reject_reason"] = top7_primary_reject_reason(reasons)
    row["top7_reject_reason_count"] = len(reasons)
    row["top7_reject_summary_scope"] = "NON_PUBLISHABLE_ROWS_ONLY"
    row["top7_status_allowed"] = status_allowed
    row["top7_status_type_normalized"] = status_type(row)
    row["top7_status_code"] = status_code(row)
    row["top7_corq_probability"] = round(cp, 6)
    row["top7_pick_thinq_edge"] = round(edge, 6)
    row["top7_thinq_confidence"] = round(conf, 6)
    row["top7_thinq_data_confidence"] = round(conf, 6)
    row["top7_thinq_pick_probability"] = round(thinq_pick_probability(row), 6)
    if row.get("thinq_error") or "THINQ_ATTACH_FAILED" in set(str(x) for x in (row.get("thinq_flags") or [])):
        flags = row.get("corq_warning_flags")
        if not isinstance(flags, list):
            flags = []
        if "THINQ_ATTACH_FAILED" not in flags:
            flags.append("THINQ_ATTACH_FAILED")
        row["corq_warning_flags"] = flags
    row["pick_data_depth"] = round(depth, 6)
    row["stat_data_depth"] = round(depth, 6)
    row["form_data_depth"] = round(form_data_depth(row), 6)
    row["top7_pick_odds"] = pick_odds_value(row)
    row["top7_match_date_local"] = _match_date_local(row)
    row["recent_form_status"] = recent_form_status(row)
    row["recent_form_reason"] = recent_form_reason(row)
    row["recent_form_sample_audit"] = recent_form_sample_audit(row)
    row["low_data_risk_audit"] = low_data_risk_audit(row)
    risk = top7_risk_assessment(row)
    row["top7_risk_tags"] = risk["tags"]
    row["top7_risk_labels"] = risk["labels"]
    row["top7_risk_penalty_details"] = risk["details"]
    row["top7_risk_penalty_points"] = risk["penalty_points"]
    row["top7_clean_bonus_points"] = risk["bonus_points"]
    row["top7_quality_score"] = top7_quality_score(row) if not reasons else 0.0
    if risk["tags"]:
        existing_flags = row.get("corq_warning_flags")
        if not isinstance(existing_flags, list):
            existing_flags = []
        merged = list(existing_flags)
        for tag in risk["tags"]:
            if tag not in merged:
                merged.append(tag)
        row["corq_warning_flags"] = merged
    return row


def annotate_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        new_row = row if isinstance(row, dict) else {}
        new_row.setdefault("corq_source_rank", idx)
        annotate_top7_quality(new_row)
        annotated.append(new_row)
    return annotated



def _match_identity_key(row: Dict[str, Any]) -> str:
    return str(
        row.get("match_key")
        or row.get("event_id")
        or row.get("id")
        or "|".join(sorted([str(row.get("player1") or row.get("home") or ""), str(row.get("player2") or row.get("away") or "")]))
    )


def _basic_top7_safety_ok(row: Dict[str, Any], allow_status_fallback: bool = False) -> bool:
    """Minimum safety gates for emergency TOP7 fallback.

    This is intentionally much less strict than full publishable_for_top7().
    It prevents an empty CorQ page while still blocking clearly unsafe/non-bet rows.
    Quality concerns such as CorQ below 50 or ThinQ edge against pick are allowed
    only as fallback rows and are marked in the output.
    """
    if not is_today_match(row):
        return False
    if is_doubles(row):
        return False
    if not odds_available(row):
        return False
    if not side_valid(row):
        return False
    if odds_orientation_extreme_risk(row):
        return False
    odds_value = pick_odds_value(row)
    if odds_value is not None and odds_value < MIN_PICK_ODDS:
        return False
    if not allow_status_fallback and not is_notstarted(row):
        return False
    return True


def _fallback_quality_score(row: Dict[str, Any]) -> float:
    risk = top7_risk_assessment(row)
    cp = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    edge = max(pick_thinq_edge(row), -0.08) * 100.0
    conf = thinq_confidence(row) * 100.0
    odds_value = pick_odds_value(row) or 0.0
    return round(cp + 0.20 * depth + 0.18 * edge + 0.05 * conf - float(risk.get("penalty_points") or 0.0) + min(odds_value, 3.0) * 0.25, 4)


def sort_fallback_candidates(rows: Iterable[Dict[str, Any]], allow_status_fallback: bool = False) -> List[Dict[str, Any]]:
    data = [r for r in rows if isinstance(r, dict) and r.get("top7_publishable") is not True and _basic_top7_safety_ok(r, allow_status_fallback=allow_status_fallback)]
    return sorted(
        data,
        key=lambda r: (
            _fallback_quality_score(r),
            _ranking_score(r),
            corq_probability(r),
            pick_data_depth(r),
            thinq_confidence(r),
        ),
        reverse=True,
    )


def _append_unique_selection(selected: List[Dict[str, Any]], candidates: Iterable[Dict[str, Any]], seen_matches: set, top_n: int, *, fallback_reason: Optional[str] = None) -> None:
    for row in candidates:
        key = _match_identity_key(row)
        if key in seen_matches:
            continue
        seen_matches.add(key)
        if fallback_reason:
            row["top7_fallback_selected"] = True
            row["top7_fallback_reason"] = fallback_reason
            row["top7_publishable"] = False
            row["eligible_for_top7"] = False
            flags = row.get("corq_warning_flags")
            if not isinstance(flags, list):
                flags = []
            for flag in ("TOP7_SOFT_FALLBACK", fallback_reason):
                if flag not in flags:
                    flags.append(flag)
            row["corq_warning_flags"] = flags
        selected.append(row)
        if len(selected) >= top_n:
            break

def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    data = [r for r in rows if r.get("top7_publishable") is True]
    return sorted(
        data,
        key=lambda r: (
            top7_quality_score(r),
            corq_probability(r),
            pick_data_depth(r),
            max(pick_thinq_edge(r), 0.0),
            thinq_confidence(r),
            _as_float(_first(r, ["pick_odds", "odds", "odds_player1", "home_odds"], 0.0), 0.0) or 0.0,
        ),
        reverse=True,
    )


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    annotated = annotate_rows(rows)
    publishable = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen_matches = set()
    _append_unique_selection(selected, publishable, seen_matches, top_n)

    # Do not allow an empty CorQ page. If strict publishable logic returns
    # fewer than top_n rows, backfill with safe same-day prematch candidates
    # and mark them clearly as fallback rows. This is a display continuity
    # safety net, not a quality upgrade.
    if len(selected) < top_n:
        fallback = sort_fallback_candidates(annotated, allow_status_fallback=False)
        _append_unique_selection(
            selected,
            fallback,
            seen_matches,
            top_n,
            fallback_reason="TOP7_SOFT_FALLBACK_QUALITY_RELAXED",
        )

    # Absolute emergency: if status normalization failed for the provider and
    # the page would still be empty, relax only the status gate. Rows remain
    # flagged and can be audited in the UI/JSON.
    if len(selected) < top_n:
        fallback_status = sort_fallback_candidates(annotated, allow_status_fallback=True)
        _append_unique_selection(
            selected,
            fallback_status,
            seen_matches,
            top_n,
            fallback_reason="TOP7_SOFT_FALLBACK_STATUS_RELAXED",
        )

    for idx, row in enumerate(selected, start=1):
        row["top7_rank"] = idx
        row["corq_rank"] = idx
    return selected

def rank_predictions(predictions: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (ALL annotated rows, TOP7 publishable rows)."""
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
    """Backward-compatible eligibility evaluator used by older engine code."""
    return annotate_top7_quality(row)


def is_publishable(row: Dict[str, Any]) -> bool:
    return publishable_for_top7(row)

# ---------------------------------------------------------------------------
# Backward-compatible API expected by corq.engine
# ---------------------------------------------------------------------------

def _ranking_score(row: Dict[str, Any]) -> float:
    """Broad CORQ ranking score for ALL/ranked views.

    This keeps legacy engine calls working.  It does *not* decide publication
    eligibility.  TOP7 publication is handled by top7_from_ranking().
    """
    adjusted = _first(row, ["corq_adjusted_score", "adjusted_score", "corq_score"], None)
    if adjusted is not None:
        value = _prob(adjusted, 0.0)
        return value
    return corq_probability(row)


def make_all_match_view(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """Return today's broad ALL audit view with TOP7 quality annotations.

    ALL stays broad for today's slate only. Yesterday and older matches belong
    to Results, not to the current ALL/TOP7 page.
    """
    rows = [r for r in list(predictions or []) if isinstance(r, dict) and is_today_match(r)]
    return annotate_rows(rows)


def rank_corq(predictions: Iterable[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """Return broad CORQ-ranked rows.

    Sorting is intentionally broader than TOP7 filtering.  Filtering is only
    applied inside top7_from_ranking().
    """
    rows = annotate_rows(list(predictions or []))
    ranked = sorted(
        rows,
        key=lambda r: (
            _ranking_score(r),
            corq_probability(r),
            pick_data_depth(r),
            max(pick_thinq_edge(r), 0.0),
            thinq_confidence(r),
        ),
        reverse=True,
    )
    for idx, row in enumerate(ranked, start=1):
        row["corq_source_rank"] = idx
        row.setdefault("corq_rank", idx)
    return ranked


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """Return TOP7 rows from an already ranked list.

    Strict publishable rows are preferred. If strict gates produce fewer than
    seven rows, the function backfills with safe same-day fallback candidates so
    the CorQ page never renders empty after a successful daily runtime.
    """
    rows = annotate_rows(list(ranked or []))
    publishable = sort_publishable(rows)
    selected: List[Dict[str, Any]] = []
    seen_matches = set()
    _append_unique_selection(selected, publishable, seen_matches, top_n)

    if len(selected) < top_n:
        fallback = sort_fallback_candidates(rows, allow_status_fallback=False)
        _append_unique_selection(
            selected,
            fallback,
            seen_matches,
            top_n,
            fallback_reason="TOP7_SOFT_FALLBACK_QUALITY_RELAXED",
        )

    if len(selected) < top_n:
        fallback_status = sort_fallback_candidates(rows, allow_status_fallback=True)
        _append_unique_selection(
            selected,
            fallback_status,
            seen_matches,
            top_n,
            fallback_reason="TOP7_SOFT_FALLBACK_STATUS_RELAXED",
        )

    for idx, row in enumerate(selected, start=1):
        row["top7_rank"] = idx
        row["corq_rank"] = idx
    return selected

# ============================================================
# Risk/support ranking override V2
# ============================================================
# This block intentionally overrides the earlier soft-risk functions.  The
# original implementation already produced warning tags, but negative signals
# were mostly visual.  V2 separates positive/support tags from risk tags and
# makes stacked risk reduce TOP7 ranking quality.
try:
    _ORIGINAL_RISK_SUPPORT_ANNOTATE_TOP7_QUALITY
except NameError:
    _ORIGINAL_RISK_SUPPORT_ANNOTATE_TOP7_QUALITY = annotate_top7_quality


def _risk_support_recent_counts(row: Dict[str, Any], side: str, surface: bool = False) -> Tuple[int, int, int]:
    rf = _get_nested(row, "thinq", "recent_form")
    if not isinstance(rf, dict):
        rf = row.get("recent_form") if isinstance(row.get("recent_form"), dict) else {}
    ctx = rf.get(side) if isinstance(rf.get(side), dict) else {}
    bucket_name = "surface_last10" if surface else "last10"
    bucket = ctx.get(bucket_name) if isinstance(ctx.get(bucket_name), dict) else {}
    prefix = "pick" if side == "pick" else "opponent"
    surface_prefixes = [
        f"{prefix}_surface_wins",
        f"{prefix}_surface_losses",
        f"{prefix}_surface_count",
    ]
    normal_prefixes = [
        f"{prefix}_recent_wins",
        f"{prefix}_recent_losses",
        f"{prefix}_recent_count",
    ]
    keys = surface_prefixes if surface else normal_prefixes
    wins = int(_as_float(_get_nested(bucket, "wins"), _as_float(row.get(keys[0]), 0)) or 0)
    losses = int(_as_float(_get_nested(bucket, "losses"), _as_float(row.get(keys[1]), 0)) or 0)
    count = int(_as_float(_get_nested(bucket, "count"), _as_float(row.get(keys[2]), wins + losses)) or 0)
    if count <= 0:
        count = wins + losses
    return wins, losses, count


def _risk_support_first_float(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _get_nested(row, *key.split('.')) if '.' in key else row.get(key)
        num = _as_float(value, None)
        if num is not None:
            return num
    return None


def _risk_support_tag_blob(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("tags", "audit_tags", "audit_filter_tags", "public_notes", "top7_risk_tags", "top7_support_tags", "corq_warning_flags", "risk_flags", "flags"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " | ".join(parts).lower().replace("_", " ")


def _risk_support_add(tags: List[str], labels: List[str], details: List[Dict[str, Any]], tag: str, label: str, points: float, **extra: Any) -> float:
    tags.append(tag)
    labels.append(label)
    payload = {"tag": tag, "penalty" if points < 0 else "bonus": abs(points)}
    payload.update(extra)
    details.append(payload)
    return points


def top7_risk_assessment(row: Dict[str, Any]) -> Dict[str, Any]:
    tags: List[str] = []
    labels: List[str] = []
    details: List[Dict[str, Any]] = []
    risk_tags: List[str] = []
    support_tags: List[str] = []
    risk_labels: List[str] = []
    support_labels: List[str] = []
    penalty = 0.0
    bonus = 0.0

    cp = corq_probability(row)
    edge = pick_thinq_edge(row)
    depth = pick_data_depth(row)
    fdepth = form_data_depth(row)
    conf = thinq_confidence(row)
    p_odds = pick_odds_value(row)
    o_odds = opponent_odds_value(row)
    text = _risk_support_tag_blob(row)

    def add_risk(tag: str, label: str, pts: float, **extra: Any) -> None:
        nonlocal penalty
        risk_tags.append(tag)
        risk_labels.append(label)
        penalty += abs(_risk_support_add(tags, labels, details, tag, label, -abs(pts), **extra))

    def add_support(tag: str, label: str, pts: float, **extra: Any) -> None:
        nonlocal bonus
        support_tags.append(tag)
        support_labels.append(label)
        bonus += abs(_risk_support_add(tags, labels, details, tag, label, abs(pts), **extra))

    # H2H risk/support.
    h2h_pick, h2h_opp, h2h_total = h2h_pick_opp_counts(row)
    h2h_edge = h2h_edge_value(row)
    if (h2h_total >= 3 and h2h_opp - h2h_pick >= 3) or h2h_edge <= -0.03:
        add_risk("H2H_STRONG_AGAINST_PICK", "H2H strongly against pick", 6.0, h2h_pick_wins=h2h_pick, h2h_opponent_wins=h2h_opp, h2h_edge=round(h2h_edge, 6))
        if cp >= 0.50 and edge > 0:
            add_risk("MODEL_SUPPORT_H2H_DISAGREE", "Model support, H2H disagrees", 1.5)
    elif h2h_total >= 2 and (h2h_pick > h2h_opp or h2h_edge > 0):
        add_support("H2H_SUPPORT_PICK", "H2H supports pick", 1.0, h2h_pick_wins=h2h_pick, h2h_opponent_wins=h2h_opp)

    sh2h_pick, sh2h_opp, sh2h_total = surface_h2h_pick_opp_counts(row)
    if sh2h_total >= 2 and sh2h_opp > sh2h_pick:
        add_risk("SURFACE_H2H_AGAINST_PICK", "Surface H2H against pick", 2.5, surface_h2h_pick_wins=sh2h_pick, surface_h2h_opponent_wins=sh2h_opp)
    elif sh2h_total >= 2 and sh2h_pick > sh2h_opp:
        add_support("SURFACE_H2H_SUPPORT_PICK", "Surface H2H supports pick", 0.8, surface_h2h_pick_wins=sh2h_pick, surface_h2h_opponent_wins=sh2h_opp)

    # Recent form / surface form risk and support.
    p_w, p_l, p_c = _risk_support_recent_counts(row, "pick", False)
    ps_w, ps_l, ps_c = _risk_support_recent_counts(row, "pick", True)
    o_w, o_l, o_c = _risk_support_recent_counts(row, "opponent", False)
    os_w, os_l, os_c = _risk_support_recent_counts(row, "opponent", True)
    if (p_c >= 8 and p_w <= 3) or (ps_c >= 8 and ps_w <= 3) or "pick weak" in text:
        add_risk("PICK_WEAK_FORM", "Pick weak", 4.0, pick_recent=f"{p_w}-{p_l}", pick_surface=f"{ps_w}-{ps_l}")
    if (o_c >= 8 and o_w >= 8) or (os_c >= 8 and os_w >= 8) or "opp strong" in text:
        add_risk("OPP_STRONG_FORM", "Opp strong", 5.0, opponent_recent=f"{o_w}-{o_l}", opponent_surface=f"{os_w}-{os_l}")
    if (p_c >= 8 and p_w >= 8) or (ps_c >= 8 and ps_w >= 8) or "pick strong" in text:
        add_support("PICK_STRONG_FORM", "Pick strong", 2.0, pick_recent=f"{p_w}-{p_l}", pick_surface=f"{ps_w}-{ps_l}")
    if (o_c >= 8 and o_l >= 7) or (os_c >= 8 and os_l >= 7) or "opp weak" in text:
        add_support("OPP_WEAK_FORM", "Opp weak", 2.0, opponent_recent=f"{o_w}-{o_l}", opponent_surface=f"{os_w}-{os_l}")

    recent_edge = _risk_support_first_float(row, "recent_form_edge", "short_form_edge", "thinq_recent_form_edge")
    surface_edge = recent_surface_edge_value(row)
    if recent_edge is not None and recent_edge > 0:
        add_support("FORM_SUPPORT_PICK", "Form support", 1.0, recent_form_edge=round(float(recent_edge), 6))
    if surface_edge > 0:
        add_support("SURFACE_SUPPORT_PICK", "Surface support", 1.0, surface_edge=round(surface_edge, 6))
    if edge > 0:
        add_support("THINQ_EDGE_SUPPORT_PICK", "ThinQ edge support", 1.0, thinq_edge=round(edge, 6))

    # ELO support/risk.
    overall_elo = _risk_support_first_float(row, "thinq_overall_elo_edge", "overall_elo_edge", "elo_edge", "thinq.elo.overall_elo_edge")
    surface_elo = _risk_support_first_float(row, "thinq_surface_elo_edge", "surface_elo_edge", "thinq.elo.surface_elo_edge")
    if (overall_elo is not None and overall_elo > 0) or (surface_elo is not None and surface_elo > 0):
        add_support("ELO_SUPPORT_PICK", "ELO support", 1.0, overall_elo=overall_elo, surface_elo=surface_elo)
    if (overall_elo is not None and overall_elo < -0.03) or (surface_elo is not None and surface_elo < -0.03):
        add_risk("ELO_AGAINST_PICK", "ELO against pick", 2.0, overall_elo=overall_elo, surface_elo=surface_elo)

    # Market/value risk and support.
    market_text = " | ".join(str(x) for x in (
        row.get("marq_final"), row.get("marq_final_display"), row.get("final_marq"), row.get("market_final"), row.get("marq_market_final")
    ) if x).lower().replace("_", " ")
    marq_edge = _risk_support_first_float(row, "marq_edge_pct", "marq_edge", "edge_pct")
    market_delta = _risk_support_first_float(row, "corq_market_adjustment_pp", "corq_marq_delta_pp", "marq_delta_pp", "market_adjustment_pp", "marq_adjustment_pp")
    if "market against pick" in market_text or (marq_edge is not None and marq_edge < 0) or (market_delta is not None and market_delta < -3):
        add_risk("MARKET_AGAINST_PICK", "Market against pick", 3.5, marq_edge=marq_edge, market_delta=market_delta)
    if "market with pick" in market_text or (marq_edge is not None and marq_edge > 0) or (market_delta is not None and market_delta >= 0):
        add_support("MARKET_WITH_PICK", "Market with pick", 1.5, marq_edge=marq_edge, market_delta=market_delta)

    value_delta = _risk_support_first_float(row, "corq_value_delta_pp", "value_delta_pp", "prediction_snapshot.value.corq_value_delta_pp")
    ev = _risk_support_first_float(row, "expected_value_pct", "ev_pct", "prediction_snapshot.value.expected_value_pct")
    implied_ev = None
    if p_odds and cp is not None:
        implied_ev = (cp * p_odds - 1.0) * 100.0
    value_probe = value_delta if value_delta is not None else ev if ev is not None else implied_ev
    if value_probe is not None and value_probe > 0:
        add_support("VALUE_POSITIVE", "Value+", 1.5, value=value_probe)
    if value_probe is not None and value_probe < -2.0:
        add_risk("NO_VALUE_PRICE", "No value", 3.0, value=value_probe)
    if p_odds is not None and p_odds < 1.50:
        add_risk("SHORT_PRICE_RISK", "Short price", 2.0, pick_odds=p_odds)
    if p_odds is not None and o_odds is not None and p_odds >= 2.80 and o_odds <= 1.45:
        add_risk("MARKET_STRONG_AGAINST_PICK", "Market strongly against pick", 3.0, pick_odds=p_odds, opponent_odds=o_odds)

    # Data/conflict risks.
    if depth < 0.55 or fdepth < 0.55 or conf < 0.55:
        add_risk("LOW_DATA_CONFIDENCE", "Low data confidence", 2.5, pick_data_depth=round(depth, 6), form_data_depth=round(fdepth, 6), thinq_confidence=round(conf, 6))
    if edge > 0 and market_delta is not None and market_delta < -3:
        add_risk("MMX_MODEL_MARKET_CONFLICT", "MMx model-market conflict", 2.5, thinq_edge=round(edge, 6), market_delta=market_delta)

    # Clean support stays a bonus, but only if risk stack is empty.
    if not risk_tags and cp >= 0.55 and edge >= 0.03 and depth >= 0.70 and fdepth >= 0.70 and conf >= 0.70 and p_odds is not None and 1.40 <= p_odds <= 2.20:
        add_support("CLEAN_MODEL_SUPPORT", "Clean model support", 3.0)

    primary_risk_count = len({t for t in risk_tags if t not in {"MODEL_SUPPORT_H2H_DISAGREE"}})
    if primary_risk_count >= 2:
        add_risk("MULTI_RISK_PICK", "Multiple risk signals", 3.0, risk_count=primary_risk_count)
    if primary_risk_count >= 3 or penalty >= 10.0:
        add_risk("HIGH_RISK_PICK", "High Risk", 4.0, risk_count=primary_risk_count, penalty_before_high_risk=round(penalty, 4))

    def unique(items: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    risk_tags_u = unique(risk_tags)
    support_tags_u = unique(support_tags)
    return {
        "tags": unique(tags),
        "labels": unique(labels),
        "risk_tags": risk_tags_u,
        "risk_labels": unique(risk_labels),
        "support_tags": support_tags_u,
        "support_labels": unique(support_labels),
        "positive_support_count": len(support_tags_u),
        "risk_count": len(risk_tags_u),
        "high_risk": "HIGH_RISK_PICK" in risk_tags_u,
        "details": details,
        "penalty_points": round(penalty, 4),
        "bonus_points": round(bonus, 4),
        "net_points": round(bonus - penalty, 4),
    }


def top7_quality_score(row: Dict[str, Any]) -> float:
    cp = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    edge = max(pick_thinq_edge(row), 0.0) * 100.0
    conf = thinq_confidence(row) * 100.0
    risk = top7_risk_assessment(row)
    confidence_weighted_edge = (conf / 100.0) * edge
    raw = cp + 0.25 * depth + 0.25 * edge + 0.10 * confidence_weighted_edge
    raw -= float(risk.get("penalty_points") or 0.0)
    raw += float(risk.get("bonus_points") or 0.0)
    # Stacked risks must materially move rows down, even when raw CorQ is high.
    raw -= max(0, int(risk.get("risk_count") or 0) - 1) * 2.0
    raw += min(int(risk.get("positive_support_count") or 0), 4) * 0.75
    return round(raw, 4)


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    row = _ORIGINAL_RISK_SUPPORT_ANNOTATE_TOP7_QUALITY(row)
    risk = top7_risk_assessment(row)
    row["top7_risk_tags"] = risk["risk_tags"]
    row["top7_risk_labels"] = risk["risk_labels"]
    row["top7_support_tags"] = risk["support_tags"]
    row["top7_support_labels"] = risk["support_labels"]
    row["top7_positive_support_count"] = risk["positive_support_count"]
    row["top7_risk_count"] = risk["risk_count"]
    row["top7_high_risk"] = risk["high_risk"]
    row["top7_risk_penalty_details"] = risk["details"]
    row["top7_risk_penalty_points"] = risk["penalty_points"]
    row["top7_clean_bonus_points"] = risk["bonus_points"]
    row["top7_quality_score"] = top7_quality_score(row) if not row.get("top7_quality_reject_reasons") else 0.0
    flags = row.get("corq_warning_flags")
    if not isinstance(flags, list):
        flags = []
    for tag in list(risk["risk_tags"]) + (["HIGH_RISK_PICK"] if risk.get("high_risk") else []):
        if tag not in flags:
            flags.append(tag)
    row["corq_warning_flags"] = flags
    return row


# ============================================================
# Value-aware TOP7 override V3
# ============================================================
# Goal:
# - CorQ remains important, but a bad price must not be overpowered by raw win%.
# - Negative value below -5pp gets a stronger ranking penalty.
# - Short price + no value is treated as a stacked price risk.
# - Odds below 1.50 can pass TOP7 only with very strong support, strong data depth,
#   and without extreme negative value.
# - TOP7 sorting should prefer value-neutral/value-positive rows over pure short favourites.
try:
    _VALUE_AWARE_BASE_TOP7_REJECT_REASONS
except NameError:
    _VALUE_AWARE_BASE_TOP7_REJECT_REASONS = top7_reject_reasons
    _VALUE_AWARE_BASE_TOP7_RISK_ASSESSMENT = top7_risk_assessment

VALUE_AWARE_MODEL_VERSION = "VALUE_AWARE_TOP7_V3"
VALUE_NEGATIVE_HARD_PP = -5.0
VALUE_NEGATIVE_EXTREME_EV_PCT = -8.0
SHORT_PRICE_LIMIT = 1.50
SHORT_PRICE_MIN_SUPPORT_COUNT = 5
SHORT_PRICE_MIN_PICK_DEPTH = 0.75
SHORT_PRICE_MIN_FORM_DEPTH = 0.70
SHORT_PRICE_MIN_THINQ_CONFIDENCE = 0.75
SHORT_PRICE_MIN_VALUE_DELTA_PP = -5.0
SHORT_PRICE_MIN_EXPECTED_VALUE_PCT = -7.5


def value_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    """Return CorQ value delta in percentage points when available.

    Positive means model probability is above the raw break-even price.
    Negative means the price is worse than the CorQ probability.
    """
    value = _risk_support_first_float(
        row,
        "corq_value_delta_pp",
        "value_delta_pp",
        "prediction_snapshot.value.corq_value_delta_pp",
    )
    if value is not None:
        return float(value)
    odds = pick_odds_value(row)
    cp = corq_probability(row)
    if odds and odds > 0 and cp is not None:
        return round((cp - (1.0 / odds)) * 100.0, 4)
    return None


def expected_value_pct(row: Dict[str, Any]) -> Optional[float]:
    """Return expected value percentage when available or computable."""
    value = _risk_support_first_float(
        row,
        "expected_value_pct",
        "ev_pct",
        "prediction_snapshot.value.expected_value_pct",
    )
    if value is not None:
        return float(value)
    odds = pick_odds_value(row)
    cp = corq_probability(row)
    if odds and odds > 0 and cp is not None:
        return round((cp * odds - 1.0) * 100.0, 4)
    return None


def _value_aware_positive_support_count_from_base(base: Dict[str, Any]) -> int:
    tags = base.get("support_tags")
    if isinstance(tags, list):
        return len({str(x) for x in tags if x})
    count = _as_float(base.get("positive_support_count"), None)
    return int(count or 0)


def _short_price_gate_audit(row: Dict[str, Any], base_risk: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base_risk = base_risk or _VALUE_AWARE_BASE_TOP7_RISK_ASSESSMENT(row)
    odds = pick_odds_value(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    support_count = _value_aware_positive_support_count_from_base(base_risk)
    depth = pick_data_depth(row)
    fdepth = form_data_depth(row)
    conf = thinq_confidence(row)
    checks = {
        "is_short_price": bool(odds is not None and odds < SHORT_PRICE_LIMIT),
        "support_count": support_count,
        "pick_data_depth": round(depth, 6),
        "form_data_depth": round(fdepth, 6),
        "thinq_confidence": round(conf, 6),
        "value_delta_pp": vd,
        "expected_value_pct": ev,
        "min_support_count": SHORT_PRICE_MIN_SUPPORT_COUNT,
        "min_pick_data_depth": SHORT_PRICE_MIN_PICK_DEPTH,
        "min_form_data_depth": SHORT_PRICE_MIN_FORM_DEPTH,
        "min_thinq_confidence": SHORT_PRICE_MIN_THINQ_CONFIDENCE,
        "min_value_delta_pp": SHORT_PRICE_MIN_VALUE_DELTA_PP,
        "min_expected_value_pct": SHORT_PRICE_MIN_EXPECTED_VALUE_PCT,
    }
    ok = True
    if checks["is_short_price"]:
        ok = (
            support_count >= SHORT_PRICE_MIN_SUPPORT_COUNT
            and depth >= SHORT_PRICE_MIN_PICK_DEPTH
            and fdepth >= SHORT_PRICE_MIN_FORM_DEPTH
            and conf >= SHORT_PRICE_MIN_THINQ_CONFIDENCE
            and (vd is None or vd >= SHORT_PRICE_MIN_VALUE_DELTA_PP)
            and (ev is None or ev >= SHORT_PRICE_MIN_EXPECTED_VALUE_PCT)
        )
    checks["short_price_gate_ok"] = ok
    return checks


def _append_unique_value_risk(
    base: Dict[str, Any],
    *,
    tag: str,
    label: str,
    penalty: float,
    **extra: Any,
) -> None:
    tags = base.setdefault("tags", [])
    labels = base.setdefault("labels", [])
    risk_tags = base.setdefault("risk_tags", [])
    risk_labels = base.setdefault("risk_labels", [])
    details = base.setdefault("details", [])
    if tag not in risk_tags:
        risk_tags.append(tag)
    if tag not in tags:
        tags.append(tag)
    if label not in risk_labels:
        risk_labels.append(label)
    if label not in labels:
        labels.append(label)
    payload = {"tag": tag, "penalty": penalty}
    payload.update(extra)
    details.append(payload)
    base["penalty_points"] = round(float(base.get("penalty_points") or 0.0) + penalty, 4)
    base["net_points"] = round(float(base.get("bonus_points") or 0.0) - float(base.get("penalty_points") or 0.0), 4)


def _append_unique_value_support(
    base: Dict[str, Any],
    *,
    tag: str,
    label: str,
    bonus: float,
    **extra: Any,
) -> None:
    tags = base.setdefault("tags", [])
    labels = base.setdefault("labels", [])
    support_tags = base.setdefault("support_tags", [])
    support_labels = base.setdefault("support_labels", [])
    details = base.setdefault("details", [])
    if tag not in support_tags:
        support_tags.append(tag)
    if tag not in tags:
        tags.append(tag)
    if label not in support_labels:
        support_labels.append(label)
    if label not in labels:
        labels.append(label)
    payload = {"tag": tag, "bonus": bonus}
    payload.update(extra)
    details.append(payload)
    base["bonus_points"] = round(float(base.get("bonus_points") or 0.0) + bonus, 4)
    base["net_points"] = round(float(base.get("bonus_points") or 0.0) - float(base.get("penalty_points") or 0.0), 4)


def top7_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = list(_VALUE_AWARE_BASE_TOP7_REJECT_REASONS(row))
    base_risk = _VALUE_AWARE_BASE_TOP7_RISK_ASSESSMENT(row)
    audit = _short_price_gate_audit(row, base_risk)
    if audit.get("is_short_price") and not audit.get("short_price_gate_ok"):
        reasons.append("REJECT_TOP7_SHORT_PRICE_VALUE_GUARD")
    return list(dict.fromkeys(reasons))


if "REJECT_TOP7_SHORT_PRICE_VALUE_GUARD" not in TOP7_REJECT_PRIORITY:
    TOP7_REJECT_PRIORITY.append("REJECT_TOP7_SHORT_PRICE_VALUE_GUARD")


def top7_risk_assessment(row: Dict[str, Any]) -> Dict[str, Any]:
    base = deepcopy(_VALUE_AWARE_BASE_TOP7_RISK_ASSESSMENT(row))
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    p_odds = pick_odds_value(row)
    audit = _short_price_gate_audit(row, base)

    # Positive or neutral value should have a real sorting advantage over pure short favourites.
    if vd is not None and vd >= 0:
        _append_unique_value_support(base, tag="VALUE_POSITIVE_CONFIRMED", label="Value positive", bonus=2.5, value_delta_pp=vd)
    elif vd is not None and vd >= -2.0:
        _append_unique_value_support(base, tag="VALUE_NEUTRAL_PRICE", label="Value neutral", bonus=1.25, value_delta_pp=vd)

    # Existing NO_VALUE_PRICE stays, but deeper negative value now matters more.
    if vd is not None and vd <= VALUE_NEGATIVE_HARD_PP:
        _append_unique_value_risk(base, tag="NEGATIVE_VALUE_HARD", label="Negative value >5pp", penalty=5.0, value_delta_pp=vd)
    if ev is not None and ev <= VALUE_NEGATIVE_EXTREME_EV_PCT:
        _append_unique_value_risk(base, tag="NEGATIVE_EV_HARD", label="Negative EV hard", penalty=4.0, expected_value_pct=ev)

    # Short price and no-value together should be stronger than two independent weak warnings.
    no_value = (vd is not None and vd < -2.0) or (ev is not None and ev < -3.0)
    if p_odds is not None and p_odds < SHORT_PRICE_LIMIT and no_value:
        _append_unique_value_risk(
            base,
            tag="SHORT_NO_VALUE_COMBO",
            label="Short price + no value",
            penalty=5.0,
            pick_odds=p_odds,
            value_delta_pp=vd,
            expected_value_pct=ev,
        )

    # Publishability guard audit is also shown as risk if it fails.
    if audit.get("is_short_price") and not audit.get("short_price_gate_ok"):
        _append_unique_value_risk(
            base,
            tag="SHORT_PRICE_VALUE_GUARD_FAIL",
            label="Short price guard fail",
            penalty=8.0,
            **audit,
        )

    risk_tags = list(dict.fromkeys(str(x) for x in base.get("risk_tags", []) if x))
    support_tags = list(dict.fromkeys(str(x) for x in base.get("support_tags", []) if x))
    base["risk_tags"] = risk_tags
    base["support_tags"] = support_tags
    base["positive_support_count"] = len(support_tags)
    base["risk_count"] = len(risk_tags)
    base["high_risk"] = bool("HIGH_RISK_PICK" in risk_tags or base["risk_count"] >= 5 or float(base.get("penalty_points") or 0.0) >= 16.0)
    if base["high_risk"] and "HIGH_RISK_PICK" not in risk_tags:
        risk_tags.append("HIGH_RISK_PICK")
        labels = base.setdefault("risk_labels", [])
        if "High Risk" not in labels:
            labels.append("High Risk")
        all_labels = base.setdefault("labels", [])
        if "High Risk" not in all_labels:
            all_labels.append("High Risk")
        all_tags = base.setdefault("tags", [])
        if "HIGH_RISK_PICK" not in all_tags:
            all_tags.append("HIGH_RISK_PICK")
        base["risk_count"] = len(risk_tags)
    base["value_delta_pp"] = vd
    base["expected_value_pct"] = ev
    base["short_price_gate_audit"] = audit
    base["value_aware_model_version"] = VALUE_AWARE_MODEL_VERSION
    base["penalty_points"] = round(float(base.get("penalty_points") or 0.0), 4)
    base["bonus_points"] = round(float(base.get("bonus_points") or 0.0), 4)
    base["net_points"] = round(float(base.get("bonus_points") or 0.0) - float(base.get("penalty_points") or 0.0), 4)
    return base


def top7_quality_score(row: Dict[str, Any]) -> float:
    cp = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    edge = max(pick_thinq_edge(row), 0.0) * 100.0
    conf = thinq_confidence(row) * 100.0
    risk = top7_risk_assessment(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)

    # CorQ is still the largest component, but value now directly affects quality.
    confidence_weighted_edge = (conf / 100.0) * edge
    raw = cp + 0.22 * depth + 0.22 * edge + 0.08 * confidence_weighted_edge

    # Prefer value-neutral/value-positive rows. Punish deep negative price quality.
    if vd is not None:
        if vd >= 0:
            raw += min(vd, 8.0) * 0.65
        elif vd >= -2.0:
            raw += 0.75
        elif vd <= VALUE_NEGATIVE_HARD_PP:
            raw += vd * 0.85  # vd is negative, so this subtracts.
        else:
            raw += vd * 0.35
    if ev is not None and ev <= VALUE_NEGATIVE_EXTREME_EV_PCT:
        raw -= min(abs(ev) - abs(VALUE_NEGATIVE_EXTREME_EV_PCT), 8.0) * 0.45

    raw -= float(risk.get("penalty_points") or 0.0)
    raw += float(risk.get("bonus_points") or 0.0)
    raw -= max(0, int(risk.get("risk_count") or 0) - 1) * 2.5
    raw += min(int(risk.get("positive_support_count") or 0), 5) * 0.65
    return round(raw, 4)


# ---------------------------------------------------------------------------
# 2026-08-04 TOP7 data-health override: CorQ-first publishable shortlist
# ---------------------------------------------------------------------------
# Goal:
# - CorQ TOP7 = top 7 by final CorQ probability, but only among data-healthy picks.
# - Audit keeps everything else, including model/market conflicts.
# - Hard reject model-value traps that can be pulled up by market support.
# - Add combined data depth and LOW_CONTEXT_RISK for transparent auditing.

try:
    _DATA_HEALTH_BASE_TOP7_REJECT_REASONS
except NameError:
    _DATA_HEALTH_BASE_TOP7_REJECT_REASONS = top7_reject_reasons
    _DATA_HEALTH_BASE_TOP7_RISK_ASSESSMENT = top7_risk_assessment
    _DATA_HEALTH_BASE_ANNOTATE_TOP7_QUALITY = annotate_top7_quality

TOP7_DATA_HEALTH_MODEL_VERSION = "CORQ_TOP7_DATA_HEALTH_V1"
MODEL_VALUE_HARD_REJECT_PP = -7.0
EV_HARD_REJECT_PCT = -10.0
LOW_CONTEXT_SDATA_LIMIT = 0.55
COMBINED_DATA_DEPTH_MIN = 0.55


def _safe_pct_prob(value: Any, default: Optional[float] = None) -> Optional[float]:
    num = _as_float(value, None)
    if num is None:
        return default
    if num > 1.5:
        num = num / 100.0
    return max(0.0, min(float(num), 1.0))


def sets_games_data_depth(row: Dict[str, Any]) -> float:
    value = _first(
        row,
        [
            "sets_games_data_depth",
            "sets_games_s_data_depth",
            "sets_games_stat_data_depth",
            "sg_data_depth",
            "ta_sets_games_data_depth",
            "sets_games_depth",
        ],
        None,
    )
    if value is None:
        value = _get_nested(row, "sets_games", "data_depth")
    if value is None:
        value = _get_nested(row, "sets_games", "s_data_depth")
    if value is None:
        value = _get_nested(row, "sets_games", "stat_data_depth")
    if value is None:
        # If Sets/Games depth is unavailable, use pick data depth as a conservative fallback
        # so older rows are not rejected only because this new audit field is missing.
        return pick_data_depth(row)
    return _safe_pct_prob(value, 0.0) or 0.0


def combined_data_depth(row: Dict[str, Any]) -> float:
    corq_depth = pick_data_depth(row)
    form_depth = form_data_depth(row)
    sg_depth = sets_games_data_depth(row)
    combined = (0.50 * corq_depth) + (0.30 * form_depth) + (0.20 * sg_depth)
    return round(max(0.0, min(combined, 1.0)), 6)


def _surface_h2h_missing(row: Dict[str, Any]) -> bool:
    pick_w, opp_w, matches = surface_h2h_pick_opp_counts(row)
    if matches > 0:
        return False
    text = " ".join(str(x or "") for x in (
        _first(row, ["surface_h2h_display", "s_h2h_display", "same_surface_h2h_display"], ""),
        _get_nested(row, "thinq", "h2h", "same_surface_status"),
        _get_nested(row, "thinq", "h2h", "status"),
    )).lower()
    if "no data" in text or "missing" in text:
        return True
    return matches <= 0


def low_context_risk(row: Dict[str, Any]) -> bool:
    return bool(
        elo_unavailable(row)
        and _surface_h2h_missing(row)
        and pick_data_depth(row) < LOW_CONTEXT_SDATA_LIMIT
    )


def _data_health_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    tq = thinq_pick_probability(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    cdepth = combined_data_depth(row)

    if tq < 0.50 and vd is not None and vd < 0:
        reasons.append("REJECT_TOP7_THINQ_BELOW_50_AND_NEGATIVE_VALUE")
    if vd is not None and vd <= MODEL_VALUE_HARD_REJECT_PP:
        reasons.append("REJECT_TOP7_MODEL_VALUE_HARD_NEGATIVE")
    if ev is not None and ev <= EV_HARD_REJECT_PCT:
        reasons.append("REJECT_TOP7_EV_HARD_NEGATIVE")
    if cdepth < COMBINED_DATA_DEPTH_MIN:
        reasons.append("REJECT_TOP7_LOW_COMBINED_DATA_DEPTH")
    return reasons


def top7_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = list(_DATA_HEALTH_BASE_TOP7_REJECT_REASONS(row))
    reasons.extend(_data_health_reject_reasons(row))
    return list(dict.fromkeys(reasons))


for _reason in (
    "REJECT_TOP7_THINQ_BELOW_50_AND_NEGATIVE_VALUE",
    "REJECT_TOP7_MODEL_VALUE_HARD_NEGATIVE",
    "REJECT_TOP7_EV_HARD_NEGATIVE",
    "REJECT_TOP7_LOW_COMBINED_DATA_DEPTH",
):
    if _reason not in TOP7_REJECT_PRIORITY:
        TOP7_REJECT_PRIORITY.append(_reason)


def top7_risk_assessment(row: Dict[str, Any]) -> Dict[str, Any]:
    base = deepcopy(_DATA_HEALTH_BASE_TOP7_RISK_ASSESSMENT(row))
    cdepth = combined_data_depth(row)
    base["combined_data_depth"] = cdepth
    base["sets_games_data_depth"] = round(sets_games_data_depth(row), 6)
    base["data_health_model_version"] = TOP7_DATA_HEALTH_MODEL_VERSION

    risk_tags = list(dict.fromkeys(str(x) for x in base.get("risk_tags", []) if x))
    risk_labels = list(dict.fromkeys(str(x) for x in base.get("risk_labels", base.get("labels", [])) if x))
    all_tags = list(dict.fromkeys(str(x) for x in base.get("tags", []) if x))
    all_labels = list(dict.fromkeys(str(x) for x in base.get("labels", []) if x))
    details = list(base.get("details", [])) if isinstance(base.get("details"), list) else []

    if low_context_risk(row):
        if "LOW_CONTEXT_RISK" not in risk_tags:
            risk_tags.append("LOW_CONTEXT_RISK")
        if "LOW_CONTEXT_RISK" not in all_tags:
            all_tags.append("LOW_CONTEXT_RISK")
        if "Low context risk" not in risk_labels:
            risk_labels.append("Low context risk")
        if "Low context risk" not in all_labels:
            all_labels.append("Low context risk")
        details.append({
            "tag": "LOW_CONTEXT_RISK",
            "penalty": 4.0,
            "elo_unavailable": bool(elo_unavailable(row)),
            "surface_h2h_missing": bool(_surface_h2h_missing(row)),
            "pick_data_depth": round(pick_data_depth(row), 6),
            "combined_data_depth": cdepth,
        })
        base["penalty_points"] = round(float(base.get("penalty_points") or 0.0) + 4.0, 4)

    base["risk_tags"] = risk_tags
    base["risk_labels"] = risk_labels
    base["tags"] = all_tags
    base["labels"] = all_labels
    base["details"] = details
    base["risk_count"] = len(risk_tags)
    base["high_risk"] = bool("HIGH_RISK_PICK" in risk_tags or base["risk_count"] >= 5 or float(base.get("penalty_points") or 0.0) >= 16.0)
    base["bonus_points"] = round(float(base.get("bonus_points") or 0.0), 4)
    base["penalty_points"] = round(float(base.get("penalty_points") or 0.0), 4)
    base["net_points"] = round(base["bonus_points"] - base["penalty_points"], 4)
    return base


def top7_quality_score(row: Dict[str, Any]) -> float:
    """Audit score only. TOP7 sorting is CorQ-first in sort_publishable()."""
    cp = corq_probability(row) * 100.0
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    risk = top7_risk_assessment(row)
    cdepth = combined_data_depth(row) * 100.0
    raw = cp + 0.10 * cdepth
    if vd is not None:
        raw += max(min(vd, 8.0), -12.0) * 0.25
    if ev is not None:
        raw += max(min(ev, 10.0), -15.0) * 0.10
    raw -= float(risk.get("risk_count") or 0) * 1.5
    raw -= max(0.0, float(risk.get("penalty_points") or 0.0) - float(risk.get("bonus_points") or 0.0)) * 0.25
    return round(raw, 4)


def _value_sort_key(row: Dict[str, Any]) -> float:
    value = value_delta_pp(row)
    return -999.0 if value is None else float(value)


def _ev_sort_key(row: Dict[str, Any]) -> float:
    value = expected_value_pct(row)
    return -999.0 if value is None else float(value)


def _risk_sort_key(row: Dict[str, Any]) -> int:
    try:
        return int(top7_risk_assessment(row).get("risk_count") or 0)
    except Exception:
        return 99


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    data = [r for r in rows if r.get("top7_publishable") is True]
    ranked = sorted(
        data,
        key=lambda r: (
            corq_probability(r),
            _value_sort_key(r),
            _ev_sort_key(r),
            -_risk_sort_key(r),
            combined_data_depth(r),
            thinq_pick_probability(r),
            pick_data_depth(r),
            max(pick_thinq_edge(r), 0.0),
        ),
        reverse=True,
    )
    for idx, row in enumerate(ranked, start=1):
        row["top7_sort_rank"] = idx
        row["top7_sort_primary"] = "CORQ_PROBABILITY_DESC"
        row["top7_sort_model_version"] = TOP7_DATA_HEALTH_MODEL_VERSION
    return ranked


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    row = _DATA_HEALTH_BASE_ANNOTATE_TOP7_QUALITY(row)
    # Base annotation may have used the older reject list. Refresh final hard gates and audit fields.
    reasons = top7_reject_reasons(row)
    publishable = not reasons
    row["top7_filter_mode"] = "PUBLISHABLE_CORQ_FIRST_DATA_HEALTH_V1"
    row["top7_publishable"] = publishable
    row["eligible_for_top7"] = publishable
    row["top7_quality_reject_reasons"] = reasons
    row["top7_reject_reasons"] = reasons
    row["top7_hard_reject_reasons"] = reasons
    row["top7_primary_reject_reason"] = top7_primary_reject_reason(reasons)
    row["top7_reject_reason_count"] = len(reasons)
    row["top7_combined_data_depth"] = combined_data_depth(row)
    row["top7_sets_games_data_depth"] = round(sets_games_data_depth(row), 6)
    row["top7_low_context_risk"] = low_context_risk(row)
    row["top7_value_delta_pp"] = value_delta_pp(row)
    row["top7_expected_value_pct"] = expected_value_pct(row)
    row["top7_quality_score"] = top7_quality_score(row) if publishable else 0.0
    risk = top7_risk_assessment(row)
    row["top7_risk_tags"] = risk.get("risk_tags", [])
    row["top7_risk_labels"] = risk.get("risk_labels", risk.get("labels", []))
    row["top7_risk_count"] = risk.get("risk_count", 0)
    row["top7_risk_penalty_points"] = risk.get("penalty_points", 0.0)
    row["top7_clean_bonus_points"] = risk.get("bonus_points", 0.0)
    row["top7_data_health_model_version"] = TOP7_DATA_HEALTH_MODEL_VERSION
    return row

# ============================================================
# Value-first TOP7 final override V4
# ============================================================
# This final block intentionally overrides the earlier CorQ-first sorter.
# Goal: TOP7 = best value/risk bets, not simply highest raw win probability.
# - odds <= 1.55 need value >= +4pp or EV >= +4%
# - odds <= 1.55 get a ranking penalty unless value/risk/market/data are clean
# - sorting is value-first, EV-second, risk/data/market next, raw CorQ last
# - no forced fallback fill: if only 4 rows pass, TOP7 publishes 4 rows

try:
    _VALUE_FIRST_V4_BASE_TOP7_REJECT_REASONS
except NameError:
    _VALUE_FIRST_V4_BASE_TOP7_REJECT_REASONS = top7_reject_reasons
    _VALUE_FIRST_V4_BASE_TOP7_RISK_ASSESSMENT = top7_risk_assessment
    _VALUE_FIRST_V4_BASE_ANNOTATE_TOP7_QUALITY = annotate_top7_quality

TOP7_VALUE_FIRST_MODEL_VERSION = "CORQ_TOP7_VALUE_FIRST_V4"
LOW_ODDS_FAVORITE_LIMIT = 1.55
LOW_ODDS_MIN_VALUE_DELTA_PP = 4.0
LOW_ODDS_MIN_EXPECTED_VALUE_PCT = 4.0
LOW_ODDS_SORT_PENALTY = 10.0
LOW_ODDS_EXEMPT_MIN_VALUE_DELTA_PP = 5.0
LOW_ODDS_EXEMPT_MIN_EXPECTED_VALUE_PCT = 6.0
LOW_ODDS_EXEMPT_MIN_COMBINED_DEPTH = 0.70


def _vf4_clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _vf4_market_text(row: Dict[str, Any]) -> str:
    return " | ".join(
        str(x)
        for x in (
            row.get("marq_final"),
            row.get("marq_final_display"),
            row.get("final_marq"),
            row.get("market_final"),
            row.get("marq_market_final"),
            row.get("marq_v2_signal"),
            row.get("marq_signal"),
        )
        if x
    ).lower().replace("_", " ")


def _vf4_market_with_pick(row: Dict[str, Any]) -> bool:
    txt = _vf4_market_text(row)
    if "market with pick" in txt or "with pick" in txt or "value market edge" in txt:
        return True
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    return bool((vd is not None and vd >= 3.0) or (ev is not None and ev >= 3.0))


def _vf4_market_against_pick(row: Dict[str, Any]) -> bool:
    txt = _vf4_market_text(row)
    if "market against pick" in txt or "against pick" in txt or "no value price" in txt:
        return True
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    return bool((vd is not None and vd <= -2.0) or (ev is not None and ev <= -3.0))


def _vf4_low_odds_value_ok(row: Dict[str, Any]) -> bool:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    return bool(
        (vd is not None and vd >= LOW_ODDS_MIN_VALUE_DELTA_PP)
        or (ev is not None and ev >= LOW_ODDS_MIN_EXPECTED_VALUE_PCT)
    )


def _vf4_low_odds_exempt(row: Dict[str, Any], risk: Optional[Dict[str, Any]] = None) -> bool:
    risk = risk or top7_risk_assessment(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    strong_value = bool(
        (vd is not None and vd >= LOW_ODDS_EXEMPT_MIN_VALUE_DELTA_PP)
        or (ev is not None and ev >= LOW_ODDS_EXEMPT_MIN_EXPECTED_VALUE_PCT)
    )
    clean_risk = int(risk.get("risk_count") or 0) == 0 and not _vf4_market_against_pick(row)
    market_support = _vf4_market_with_pick(row)
    high_depth = combined_data_depth(row) >= LOW_ODDS_EXEMPT_MIN_COMBINED_DEPTH
    return bool(strong_value and clean_risk and market_support and high_depth)


def _vf4_low_odds_gate_status(row: Dict[str, Any]) -> str:
    odds = pick_odds_value(row)
    if odds is None:
        return "NO_PICK_ODDS"
    if odds > LOW_ODDS_FAVORITE_LIMIT:
        return "NOT_LOW_ODDS"
    if _vf4_low_odds_value_ok(row):
        return "LOW_ODDS_VALUE_OK"
    return "LOW_ODDS_REJECTED_NEEDS_VALUE"


def _vf4_value_gate_status(row: Dict[str, Any]) -> str:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if vd is None and ev is None:
        return "NO_VALUE_DATA"
    if (vd is not None and vd >= 4.0) or (ev is not None and ev >= 4.0):
        return "STRONG_VALUE"
    if (vd is not None and vd > 0) or (ev is not None and ev > 0):
        return "POSITIVE_VALUE"
    if (vd is not None and vd < 0) or (ev is not None and ev < 0):
        return "NEGATIVE_VALUE"
    return "NEUTRAL_VALUE"


def _vf4_market_bonus(row: Dict[str, Any]) -> float:
    if _vf4_market_with_pick(row):
        return 4.0
    if _vf4_market_against_pick(row):
        return -4.0
    return 0.0


def _vf4_rank_audit_tags(row: Dict[str, Any], risk: Optional[Dict[str, Any]] = None) -> List[str]:
    risk = risk or top7_risk_assessment(row)
    tags: List[str] = []
    vstatus = _vf4_value_gate_status(row)
    lstatus = _vf4_low_odds_gate_status(row)
    tags.append(vstatus)
    if lstatus != "NOT_LOW_ODDS":
        tags.append(lstatus)
    if _vf4_market_with_pick(row):
        tags.append("MARKET_WITH_PICK")
    if _vf4_market_against_pick(row):
        tags.append("MARKET_AGAINST_PICK")
    if combined_data_depth(row) >= LOW_ODDS_EXEMPT_MIN_COMBINED_DEPTH:
        tags.append("HIGH_DATA_DEPTH")
    if int(risk.get("risk_count") or 0) >= 2:
        tags.append("STACKED_RISK")
    for tag in risk.get("risk_tags") or []:
        if tag:
            tags.append(str(tag))
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def top7_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = list(_VALUE_FIRST_V4_BASE_TOP7_REJECT_REASONS(row))
    odds = pick_odds_value(row)
    if odds is not None and odds <= LOW_ODDS_FAVORITE_LIMIT and not _vf4_low_odds_value_ok(row):
        reasons.append("REJECT_TOP7_LOW_ODDS_FAVORITE_VALUE_GATE")
    return list(dict.fromkeys(reasons))


if "REJECT_TOP7_LOW_ODDS_FAVORITE_VALUE_GATE" not in TOP7_REJECT_PRIORITY:
    TOP7_REJECT_PRIORITY.append("REJECT_TOP7_LOW_ODDS_FAVORITE_VALUE_GATE")


def top7_risk_assessment(row: Dict[str, Any]) -> Dict[str, Any]:
    base = deepcopy(_VALUE_FIRST_V4_BASE_TOP7_RISK_ASSESSMENT(row))
    odds = pick_odds_value(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)

    base["value_first_model_version"] = TOP7_VALUE_FIRST_MODEL_VERSION
    base["value_delta_pp"] = vd
    base["expected_value_pct"] = ev
    base["market_support_bonus"] = _vf4_market_bonus(row)
    base["low_odds_gate_status"] = _vf4_low_odds_gate_status(row)
    base["value_gate_status"] = _vf4_value_gate_status(row)

    if odds is not None and odds <= LOW_ODDS_FAVORITE_LIMIT:
        exempt = _vf4_low_odds_exempt(row, base)
        base["low_odds_penalty_exempt"] = exempt
        base["low_odds_penalty_points"] = 0.0 if exempt else LOW_ODDS_SORT_PENALTY
        if not exempt:
            _append_unique_value_risk(
                base,
                tag="LOW_ODDS_FAVORITE_SORT_PENALTY",
                label="Short price penalty",
                penalty=LOW_ODDS_SORT_PENALTY,
                odds=odds,
                value_delta_pp=vd,
                expected_value_pct=ev,
            )
    else:
        base["low_odds_penalty_exempt"] = True
        base["low_odds_penalty_points"] = 0.0

    if _vf4_market_with_pick(row):
        _append_unique_value_support(
            base,
            tag="VALUE_FIRST_MARKET_WITH_PICK",
            label="Market with pick",
            bonus=2.0,
        )
    if vd is not None and vd >= 4.0:
        _append_unique_value_support(
            base,
            tag="VALUE_FIRST_STRONG_DELTA",
            label="Strong value delta",
            bonus=2.0,
            value_delta_pp=vd,
        )
    if ev is not None and ev >= 4.0:
        _append_unique_value_support(
            base,
            tag="VALUE_FIRST_STRONG_EV",
            label="Strong EV",
            bonus=2.0,
            expected_value_pct=ev,
        )

    base["risk_count"] = len(base.get("risk_tags") or [])
    base["positive_support_count"] = len(base.get("support_tags") or [])
    base["high_risk"] = bool(base.get("high_risk")) or int(base.get("risk_count") or 0) >= 3
    return base


def top7_quality_score(row: Dict[str, Any]) -> float:
    """Value-first TOP7 sort score.

    The score intentionally puts model-vs-price value before raw CorQ probability.
    Raw CorQ remains in the score, but only as a later/tie-break style factor.
    """
    risk = top7_risk_assessment(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    cp = corq_probability(row) * 100.0
    cdepth = combined_data_depth(row) * 100.0
    pdepth = pick_data_depth(row) * 100.0
    conf = thinq_confidence(row) * 100.0
    edge = max(pick_thinq_edge(row), 0.0) * 100.0
    market_bonus = _vf4_market_bonus(row)
    penalty = float(risk.get("penalty_points") or 0.0)
    bonus = float(risk.get("bonus_points") or 0.0)

    raw = 0.0
    raw += _vf4_clamp(vd if vd is not None else -3.0, -12.0, 14.0) * 4.0
    raw += _vf4_clamp(ev if ev is not None else -4.0, -18.0, 28.0) * 1.15
    raw += market_bonus
    raw += cdepth * 0.18
    raw += pdepth * 0.08
    raw += conf * 0.04
    raw += edge * 0.20
    raw += cp * 0.18
    raw -= penalty
    raw += bonus * 0.50
    raw -= max(0, int(risk.get("risk_count") or 0) - 1) * 2.0
    return round(raw, 4)


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    data = [r for r in rows if r.get("top7_publishable") is True]
    ranked = sorted(
        data,
        key=lambda r: (
            top7_quality_score(r),
            value_delta_pp(r) if value_delta_pp(r) is not None else -999.0,
            expected_value_pct(r) if expected_value_pct(r) is not None else -999.0,
            -int(top7_risk_assessment(r).get("risk_count") or 0),
            combined_data_depth(r),
            _vf4_market_bonus(r),
            pick_data_depth(r),
            thinq_confidence(r),
            corq_probability(r),
        ),
        reverse=True,
    )
    for idx, row in enumerate(ranked, start=1):
        row["top7_sort_rank"] = idx
        row["top7_sort_primary"] = "VALUE_FIRST_SCORE_DESC"
        row["top7_sort_model_version"] = TOP7_VALUE_FIRST_MODEL_VERSION
        row["corq_top7_sort_score"] = top7_quality_score(row)
    return ranked


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    row = _VALUE_FIRST_V4_BASE_ANNOTATE_TOP7_QUALITY(row)
    reasons = top7_reject_reasons(row)
    publishable = not reasons
    risk = top7_risk_assessment(row)

    row["top7_filter_mode"] = "PUBLISHABLE_VALUE_FIRST_LOW_ODDS_GATE_V4"
    row["top7_publishable"] = publishable
    row["eligible_for_top7"] = publishable
    row["top7_quality_reject_reasons"] = reasons
    row["top7_reject_reasons"] = reasons
    row["top7_hard_reject_reasons"] = reasons
    row["top7_primary_reject_reason"] = top7_primary_reject_reason(reasons)
    row["top7_reject_reason_count"] = len(reasons)

    row["top7_value_delta_pp"] = value_delta_pp(row)
    row["top7_expected_value_pct"] = expected_value_pct(row)
    row["top7_combined_data_depth"] = combined_data_depth(row)
    row["top7_sets_games_data_depth"] = round(sets_games_data_depth(row), 6)
    row["top7_low_context_risk"] = low_context_risk(row)

    row["top7_risk_tags"] = risk.get("risk_tags", [])
    row["top7_risk_labels"] = risk.get("risk_labels", risk.get("labels", []))
    row["top7_support_tags"] = risk.get("support_tags", [])
    row["top7_support_labels"] = risk.get("support_labels", [])
    row["top7_positive_support_count"] = risk.get("positive_support_count", 0)
    row["top7_risk_count"] = risk.get("risk_count", 0)
    row["top7_high_risk"] = risk.get("high_risk", False)
    row["top7_risk_penalty_details"] = risk.get("details", [])
    row["top7_risk_penalty_points"] = risk.get("penalty_points", 0.0)
    row["top7_clean_bonus_points"] = risk.get("bonus_points", 0.0)

    row["corq_top7_sort_score"] = top7_quality_score(row) if publishable else 0.0
    row["corq_value_gate_status"] = _vf4_value_gate_status(row)
    row["corq_low_odds_gate_status"] = _vf4_low_odds_gate_status(row)
    row["corq_risk_penalty"] = risk.get("penalty_points", 0.0)
    row["corq_market_support_bonus"] = _vf4_market_bonus(row)
    row["corq_top7_reject_reasons"] = reasons
    row["corq_rank_audit_tags"] = _vf4_rank_audit_tags(row, risk)
    row["top7_value_first_model_version"] = TOP7_VALUE_FIRST_MODEL_VERSION
    row["top7_quality_score"] = row["corq_top7_sort_score"]

    flags = row.get("corq_warning_flags")
    if not isinstance(flags, list):
        flags = []
    for tag in row.get("corq_rank_audit_tags") or []:
        if tag not in flags and ("RISK" in tag or "REJECT" in tag or "NEGATIVE" in tag or "LOW_ODDS" in tag):
            flags.append(tag)
    row["corq_warning_flags"] = flags
    return row


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    """Select up to top_n publishable rows only.

    No soft fallback fill. If only 4 rows pass the gates, TOP7 publishes 4 rows.
    """
    annotated = annotate_rows(rows)
    publishable = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen_matches = set()
    _append_unique_selection(selected, publishable, seen_matches, top_n)
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
    return not top7_reject_reasons(row)


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return select_top7(ranked, top_n=top_n)

# ============================================================
# CorQ TOP7 forced ranking override V5
# ============================================================
# Purpose:
# - TOP7 must be a ranking from the available daily pool, not an over-hard gate.
# - Keep hard rejects only for technical impossibilities.
# - Treat value, low odds, market/risk warnings, data depth and confidence as
#   score penalties or audit tags, not as reasons to publish only 1-2 picks.

CORQ_TOP7_SELECTION_MODEL_VERSION = "CORQ_TOP7_FORCE7_RANKING_V5"
CORQ_TOP7_FORCE_COUNT = 7

_CORQ_V5_FATAL_REJECTS = {
    "REJECT_TOP7_NOT_TODAY_MATCH",
    "REJECT_TOP7_STATUS_NOT_PREMATCH",
    "REJECT_TOP7_MISSING_ODDS",
    "REJECT_TOP7_DOUBLES",
    "REJECT_TOP7_INVALID_SIDE_ORIENTATION",
    "REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME",
}


def _corq_v5_match_key(row: Dict[str, Any]) -> str:
    for key in (
        "match_key",
        "event_key",
        "match_id",
        "event_id",
        "id",
        "fixture_id",
        "api_match_id",
    ):
        val = row.get(key)
        if val is not None and str(val).strip():
            return f"{key}:{val}"
    p1 = str(row.get("player") or row.get("pick_name") or row.get("pick") or "").strip().lower()
    p2 = str(row.get("opponent") or row.get("opp_name") or row.get("opponent_name") or "").strip().lower()
    start = str(row.get("match_time_utc") or row.get("start_time_utc") or row.get("scheduled_at") or row.get("match_time") or "").strip()
    tournament = str(row.get("tournament") or row.get("competition") or "").strip().lower()
    return f"fallback:{start}:{tournament}:{p1}:{p2}"


def _corq_v5_has_text(row: Dict[str, Any], needles: Sequence[str]) -> bool:
    hay_parts: List[str] = []
    for key in (
        "corq_warning_flags",
        "corq_rank_audit_tags",
        "support_tags",
        "risk_tags",
        "tags",
        "warnings",
        "thinq_tags",
        "market_tags",
    ):
        val = row.get(key)
        if isinstance(val, list):
            hay_parts.extend(str(x) for x in val)
        elif val is not None:
            hay_parts.append(str(val))
    hay = " | ".join(hay_parts).lower()
    return any(str(n).lower() in hay for n in needles)


def _corq_v5_numeric(row: Dict[str, Any], keys: Sequence[str], default: float = 0.0) -> float:
    for key in keys:
        val = _as_float(row.get(key), None)
        if val is not None:
            return float(val)
    return float(default)


def _corq_v5_fatal_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = list(top7_reject_reasons(row) or [])
    return [r for r in reasons if r in _CORQ_V5_FATAL_REJECTS]


def _corq_v5_soft_reasons(row: Dict[str, Any]) -> List[str]:
    reasons = list(top7_reject_reasons(row) or [])
    return [r for r in reasons if r not in _CORQ_V5_FATAL_REJECTS]


def _corq_v5_probability_margin_pp(row: Dict[str, Any], odds: Optional[float]) -> Optional[float]:
    prob = corq_probability(row)
    if odds is None or odds <= 1.0:
        return None
    implied = 1.0 / odds
    return (prob - implied) * 100.0


def _corq_v5_score(row: Dict[str, Any]) -> float:
    odds = pick_odds_value(row)
    prob = corq_probability(row)
    conf = thinq_confidence(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    margin = _corq_v5_probability_margin_pp(row, odds)
    base_quality = 0.0
    try:
        base_quality = float(top7_quality_score(row) or 0.0)
    except Exception:
        base_quality = 0.0

    score = 0.0
    score += base_quality * 0.35
    score += prob * 100.0 * 0.75
    score += conf * 12.0

    if odds is not None:
        if odds >= 1.90:
            score += 10.0
        elif odds >= 1.70:
            score += 6.0
        elif odds >= 1.55:
            score += 2.0
        else:
            score -= 6.0
        # Avoid letting very high price alone dominate ranking.
        if odds > 2.80:
            score -= min(12.0, (odds - 2.80) * 8.0)

    if margin is not None:
        score += max(-18.0, min(18.0, margin * 1.1))

    if vd is not None:
        score += max(-14.0, min(14.0, vd * 0.9))
    if ev is not None:
        score += max(-14.0, min(14.0, ev * 0.65))

    combined_depth = _corq_v5_numeric(row, [
        "combined_data_depth",
        "data_depth_combined",
        "pick_combined_data_depth",
        "model_data_depth",
    ], 0.0)
    pick_depth = _corq_v5_numeric(row, ["pick_data_depth", "data_depth", "thinq_pick_data_depth"], 0.0)
    form_depth = _corq_v5_numeric(row, ["form_data_depth", "pick_form_data_depth"], 0.0)
    score += combined_depth * 10.0 + pick_depth * 7.0 + form_depth * 4.0

    if _corq_v5_has_text(row, ["market with pick", "market_with_pick", "value_first_market_with_pick"]):
        score += 5.0
    if _corq_v5_has_text(row, ["pick strong", "opp weak", "surface support", "elo support", "form support"]):
        score += 4.0
    if _corq_v5_has_text(row, ["market against", "market_against"]):
        score -= 9.0
    if _corq_v5_has_text(row, ["opp strong", "high risk", "2+ risk", "risk_backup"]):
        score -= 8.0
    if _corq_v5_has_text(row, ["no value", "negative value"]):
        score -= 5.0

    # Previous hard rejects become soft penalties except technical fatal reasons.
    soft = _corq_v5_soft_reasons(row)
    soft_penalty = {
        "REJECT_TOP7_LOW_ODDS_FAVORITE_VALUE_GATE": 8.0,
        "REJECT_TOP7_LOW_ODDS_UNDER_1_40": 12.0,
        "REJECT_TOP7_CORQ_BELOW_50": 10.0,
        "REJECT_TOP7_THINQ_EDGE_AGAINST_PICK": 8.0,
        "REJECT_TOP7_LOW_PICK_DATA_DEPTH": 6.0,
        "REJECT_TOP7_LOW_THINQ_CONFIDENCE": 6.0,
        "REJECT_TOP7_LOW_FORM_DATA_DEPTH": 4.0,
        "REJECT_TOP7_ELO_UNAVAILABLE_LOW_DEPTH": 4.0,
    }
    score -= sum(soft_penalty.get(r, 3.0) for r in soft)
    return float(score)


def _corq_v5_tier(row: Dict[str, Any], score: float) -> str:
    odds = pick_odds_value(row)
    soft = set(_corq_v5_soft_reasons(row))
    risky = bool(soft) or _corq_v5_has_text(row, ["market against", "opp strong", "high risk", "no value"])
    if not risky and odds is not None and odds >= 1.70 and score >= 55:
        return "CORQ_CLEAN"
    if score >= 45:
        return "CORQ_PLAYABLE"
    if score >= 34:
        return "CORQ_LOW_EDGE"
    return "CORQ_RISK"


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    # Keep the existing annotation first, then reinterpret non-fatal rejects as
    # audit/potential penalties instead of final blockers.
    try:
        row = _VALUE_FIRST_V4_BASE_ANNOTATE_TOP7_QUALITY(row)
    except Exception:
        pass
    try:
        prior = deepcopy(row)
        row = globals().get("_VALUE_FIRST_V4_BASE_ANNOTATE_TOP7_QUALITY", lambda x: x)(row)
    except Exception:
        row = prior if "prior" in locals() else row

    fatal = _corq_v5_fatal_reasons(row)
    soft = _corq_v5_soft_reasons(row)
    selectable = not fatal
    score = _corq_v5_score(row) if selectable else -9999.0
    tier = _corq_v5_tier(row, score) if selectable else "CORQ_NOT_SELECTABLE"

    row["top7_filter_mode"] = CORQ_TOP7_SELECTION_MODEL_VERSION
    row["top7_selection_model_version"] = CORQ_TOP7_SELECTION_MODEL_VERSION
    row["top7_publishable"] = selectable
    row["eligible_for_top7"] = selectable
    row["corq_top7_selectable"] = selectable
    row["corq_top7_sort_score"] = score
    row["top7_quality_score"] = score
    row["corq_top7_tier"] = tier
    row["corq_top7_fatal_reject_reasons"] = fatal
    row["corq_top7_soft_penalty_reasons"] = soft
    row["corq_top7_reject_reasons"] = fatal
    row["corq_top7_audit_note"] = "soft_rejects_are_score_penalties_not_publish_blockers"

    flags = row.get("corq_warning_flags")
    if not isinstance(flags, list):
        flags = []
    for tag in [tier] + [f"SOFT_{r}" for r in soft] + [f"FATAL_{r}" for r in fatal]:
        if tag not in flags:
            flags.append(tag)
    row["corq_warning_flags"] = flags

    audit = row.get("corq_rank_audit_tags")
    if not isinstance(audit, list):
        audit = []
    for tag in [CORQ_TOP7_SELECTION_MODEL_VERSION, tier] + [f"PENALTY_{r}" for r in soft]:
        if tag not in audit:
            audit.append(tag)
    row["corq_rank_audit_tags"] = audit
    return row


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = [r for r in rows if r.get("corq_top7_selectable") is True or r.get("top7_publishable") is True]
    return sorted(
        candidates,
        key=lambda r: (
            float(r.get("corq_top7_sort_score") or r.get("top7_quality_score") or 0.0),
            value_delta_pp(r) if value_delta_pp(r) is not None else -999.0,
            expected_value_pct(r) if expected_value_pct(r) is not None else -999.0,
            corq_probability(r),
            thinq_confidence(r),
            pick_odds_value(r) or 0.0,
        ),
        reverse=True,
    )


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    annotated = annotate_rows(list(rows or []))
    ranked = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen = set()
    for row in ranked:
        key = _corq_v5_match_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= int(top_n or CORQ_TOP7_FORCE_COUNT):
            break

    for idx, row in enumerate(selected, start=1):
        row["top7_rank"] = idx
        row["corq_rank"] = idx
        row["top7_publishable"] = True
        row["eligible_for_top7"] = True
        row["corq_top7_forced_rank_selection"] = True
        row["top7_selection_count_target"] = int(top_n or CORQ_TOP7_FORCE_COUNT)
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


def is_publishable(row: Dict[str, Any]) -> bool:
    return not _corq_v5_fatal_reasons(row)


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return select_top7(ranked, top_n=top_n)

# ============================================================
# CorQ TOP7 balanced ranking override V6
# ============================================================
# Goal: always rank the best 7 technically valid picks when the daily pool has
# enough valid candidates, without swinging to either extreme. Only true hard
# blockers reject. Everything else becomes a transparent score adjustment.

CORQ_TOP7_SELECTION_MODEL_VERSION = "CORQ_TOP7_BALANCED_FORCE7_V6_ODDS140"
CORQ_MIN_PICK_ODDS_V6 = 1.40
CORQ_MIN_PROBABILITY_V6 = 0.50
CORQ_MIN_DATA_DEPTH_TARGET_V6 = 0.70
CORQ_MIN_CONFIDENCE_TARGET_V6 = 0.65
CORQ_VALUE_SOFT_FLOOR_V6 = -5.0

_CORQ_V6_TECHNICAL_FATAL_REJECTS = {
    "REJECT_TOP7_NOT_TODAY_MATCH",
    "REJECT_TOP7_STATUS_NOT_PREMATCH",
    "REJECT_TOP7_MISSING_ODDS",
    "REJECT_TOP7_DOUBLES",
    "REJECT_TOP7_INVALID_SIDE_ORIENTATION",
    "REJECT_TOP7_ODDS_ORIENTATION_UNCONFIRMED_EXTREME",
}


def _corq_v6_fatal_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    previous = list(top7_reject_reasons(row) or [])
    for reason in previous:
        if reason in _CORQ_V6_TECHNICAL_FATAL_REJECTS and reason not in reasons:
            reasons.append(reason)

    odds = pick_odds_value(row)
    if odds is None:
        if "REJECT_TOP7_MISSING_ODDS" not in reasons:
            reasons.append("REJECT_TOP7_MISSING_ODDS")
    elif odds < CORQ_MIN_PICK_ODDS_V6:
        reasons.append("REJECT_TOP7_ODDS_UNDER_1_40")

    if corq_probability(row) < CORQ_MIN_PROBABILITY_V6:
        reasons.append("REJECT_TOP7_CORQ_BELOW_50")

    if pick_thinq_edge(row) < 0.0:
        reasons.append("REJECT_TOP7_THINQ_EDGE_AGAINST_PICK")

    if elo_unavailable(row):
        reasons.append("REJECT_TOP7_ELO_UNAVAILABLE")

    # Preserve order and uniqueness.
    out: List[str] = []
    for reason in reasons:
        if reason not in out:
            out.append(reason)
    return out


def _corq_v6_soft_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    previous = list(top7_reject_reasons(row) or [])
    fatal = set(_corq_v6_fatal_reasons(row))
    disabled = {
        "REJECT_TOP7_LOW_ODDS_FAVORITE_VALUE_GATE",
    }
    for reason in previous:
        if reason in fatal or reason in disabled or reason in _CORQ_V6_TECHNICAL_FATAL_REJECTS:
            continue
        if reason not in reasons:
            reasons.append(reason)

    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if vd is not None and vd < CORQ_VALUE_SOFT_FLOOR_V6:
        reasons.append("PENALTY_VALUE_DELTA_UNDER_MINUS_5")
    elif ev is not None and ev < CORQ_VALUE_SOFT_FLOOR_V6:
        reasons.append("PENALTY_EXPECTED_VALUE_UNDER_MINUS_5")
    elif vd is None and ev is None:
        reasons.append("PENALTY_VALUE_DATA_MISSING")

    combined_depth = _corq_v6_depth(row)
    if combined_depth < CORQ_MIN_DATA_DEPTH_TARGET_V6:
        reasons.append("PENALTY_DATA_DEPTH_UNDER_70")

    conf = thinq_confidence(row)
    if conf < CORQ_MIN_CONFIDENCE_TARGET_V6:
        reasons.append("PENALTY_CONFIDENCE_UNDER_65")

    if _corq_v6_has_text(row, ["market against", "market_against"]):
        reasons.append("PENALTY_MARKET_AGAINST_PICK")
    if _corq_v6_has_text(row, ["opp strong", "opponent strong"]):
        reasons.append("PENALTY_OPP_STRONG")

    out: List[str] = []
    for reason in reasons:
        if reason not in fatal and reason not in out:
            out.append(reason)
    return out


def _corq_v6_has_text(row: Dict[str, Any], needles: Sequence[str]) -> bool:
    parts: List[str] = []
    for key in (
        "corq_warning_flags",
        "corq_rank_audit_tags",
        "support_tags",
        "risk_tags",
        "tags",
        "warnings",
        "thinq_tags",
        "market_tags",
        "data_notes",
    ):
        val = row.get(key)
        if isinstance(val, list):
            parts.extend(str(x) for x in val)
        elif val is not None:
            parts.append(str(val))
    hay = " | ".join(parts).lower()
    return any(str(n).lower() in hay for n in needles)


def _corq_v6_depth(row: Dict[str, Any]) -> float:
    candidates = [
        _as_float(row.get("combined_data_depth"), None),
        _as_float(row.get("data_depth_combined"), None),
        _as_float(row.get("pick_combined_data_depth"), None),
        _as_float(row.get("model_data_depth"), None),
        _as_float(row.get("pick_data_depth"), None),
        _as_float(row.get("data_depth"), None),
    ]
    vals = [float(x) for x in candidates if x is not None]
    if not vals:
        return 0.0
    return max(vals)


def _corq_v6_probability_margin_pp(row: Dict[str, Any], odds: Optional[float]) -> Optional[float]:
    if odds is None or odds <= 1.0:
        return None
    return (corq_probability(row) - (1.0 / odds)) * 100.0


def _corq_v6_score(row: Dict[str, Any]) -> float:
    odds = pick_odds_value(row)
    prob = corq_probability(row)
    conf = thinq_confidence(row)
    depth = _corq_v6_depth(row)
    edge = pick_thinq_edge(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    margin = _corq_v6_probability_margin_pp(row, odds)

    score = 0.0

    # Core model signal: still important, but not probability-only.
    score += prob * 100.0 * 0.95
    score += max(0.0, edge) * 100.0 * 0.55
    score += conf * 12.0
    score += depth * 10.0

    # Price preference: avoid very low odds, reward useful price zone, do not chase blind long odds.
    if odds is not None:
        if odds < 1.40:
            score -= 100.0
        elif odds < 1.45:
            score -= 8.0
        elif odds < 1.55:
            score -= 6.0
        elif odds < 1.70:
            score -= 2.0
        elif odds < 1.90:
            score += 3.0
        elif odds <= 2.30:
            score += 7.0
        elif odds <= 2.70:
            score += 4.0
        else:
            score -= min(10.0, (odds - 2.70) * 6.0)

    # Market/math edge stays useful but capped because current value quality is not trusted enough.
    if margin is not None:
        score += max(-8.0, min(10.0, margin * 0.65))
    if vd is not None:
        score += max(-4.0, min(8.0, vd * 0.45))
    if ev is not None:
        score += max(-4.0, min(8.0, ev * 0.35))

    # Positive evidence.
    if _corq_v6_has_text(row, ["market with pick", "market_with_pick"]):
        score += 4.0
    if _corq_v6_has_text(row, ["pick strong"]):
        score += 3.0
    if _corq_v6_has_text(row, ["opp weak", "opponent weak"]):
        score += 3.0
    if _corq_v6_has_text(row, ["elo support", "surface support", "form support", "h2h support"]):
        score += 3.0

    # Calibrated penalties, not reject.
    for reason in _corq_v6_soft_reasons(row):
        if reason == "PENALTY_MARKET_AGAINST_PICK":
            score -= 7.0
        elif reason == "PENALTY_OPP_STRONG":
            score -= 6.0
        elif reason in {"PENALTY_DATA_DEPTH_UNDER_70", "REJECT_TOP7_LOW_PICK_DATA_DEPTH"}:
            score -= 5.0
        elif reason in {"PENALTY_CONFIDENCE_UNDER_65", "REJECT_TOP7_LOW_THINQ_CONFIDENCE"}:
            score -= 5.0
        elif reason in {"PENALTY_VALUE_DELTA_UNDER_MINUS_5", "PENALTY_EXPECTED_VALUE_UNDER_MINUS_5"}:
            score -= 4.0
        elif reason == "PENALTY_VALUE_DATA_MISSING":
            score -= 1.5
        elif reason == "REJECT_TOP7_LOW_FORM_DATA_DEPTH":
            score -= 3.0
        else:
            score -= 2.0

    return float(score)


def _corq_v6_tier(row: Dict[str, Any], score: float) -> str:
    soft = set(_corq_v6_soft_reasons(row))
    if not soft and score >= 70.0:
        return "CORQ_CLEAN"
    if score >= 61.0:
        return "CORQ_PLAYABLE"
    if score >= 53.0:
        return "CORQ_LOW_EDGE"
    return "CORQ_RISK"


def annotate_top7_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    # Use the older annotation to keep existing fields/tags, then replace final
    # selection policy with the balanced V6 policy.
    try:
        row = _VALUE_FIRST_V4_BASE_ANNOTATE_TOP7_QUALITY(row)
    except Exception:
        pass

    fatal = _corq_v6_fatal_reasons(row)
    soft = _corq_v6_soft_reasons(row)
    selectable = not fatal
    score = _corq_v6_score(row) if selectable else -9999.0
    tier = _corq_v6_tier(row, score) if selectable else "CORQ_NOT_SELECTABLE"

    row["top7_filter_mode"] = CORQ_TOP7_SELECTION_MODEL_VERSION
    row["top7_selection_model_version"] = CORQ_TOP7_SELECTION_MODEL_VERSION
    row["top7_publishable"] = selectable
    row["eligible_for_top7"] = selectable
    row["corq_top7_selectable"] = selectable
    row["corq_top7_sort_score"] = score
    row["top7_quality_score"] = score
    row["corq_top7_tier"] = tier
    row["corq_top7_reject_reasons"] = fatal
    row["corq_top7_fatal_reject_reasons"] = fatal
    row["corq_top7_soft_penalty_reasons"] = soft
    row["corq_top7_audit_note"] = "balanced_force7_v6_soft_penalties_not_hard_rejects"
    row["corq_v6_min_odds"] = CORQ_MIN_PICK_ODDS_V6
    row["corq_v6_min_data_depth_target"] = CORQ_MIN_DATA_DEPTH_TARGET_V6
    row["corq_v6_min_confidence_target"] = CORQ_MIN_CONFIDENCE_TARGET_V6
    row["corq_v6_value_soft_floor"] = CORQ_VALUE_SOFT_FLOOR_V6

    flags = row.get("corq_warning_flags")
    if not isinstance(flags, list):
        flags = []
    for tag in [tier] + [f"SOFT_{r}" for r in soft] + [f"FATAL_{r}" for r in fatal]:
        if tag not in flags:
            flags.append(tag)
    row["corq_warning_flags"] = flags

    audit = row.get("corq_rank_audit_tags")
    if not isinstance(audit, list):
        audit = []
    for tag in [CORQ_TOP7_SELECTION_MODEL_VERSION, tier] + [f"PENALTY_{r}" for r in soft]:
        if tag not in audit:
            audit.append(tag)
    row["corq_rank_audit_tags"] = audit
    return row


def _corq_v6_match_key(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_key", "match_id", "event_id", "id", "fixture_id", "api_match_id"):
        val = row.get(key)
        if val is not None and str(val).strip():
            return f"{key}:{val}"
    p1 = str(row.get("player") or row.get("pick_name") or row.get("pick") or "").strip().lower()
    p2 = str(row.get("opponent") or row.get("opp_name") or row.get("opponent_name") or "").strip().lower()
    start = str(row.get("match_time_utc") or row.get("start_time_utc") or row.get("scheduled_at") or row.get("match_time") or "").strip()
    tournament = str(row.get("tournament") or row.get("competition") or "").strip().lower()
    return f"fallback:{start}:{tournament}:{p1}:{p2}"


def sort_publishable(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = [r for r in rows if r.get("corq_top7_selectable") is True or r.get("top7_publishable") is True]
    return sorted(
        candidates,
        key=lambda r: (
            float(r.get("corq_top7_sort_score") or r.get("top7_quality_score") or 0.0),
            corq_probability(r),
            thinq_confidence(r),
            pick_odds_value(r) or 0.0,
        ),
        reverse=True,
    )


def select_top7(rows: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT) -> List[Dict[str, Any]]:
    annotated = annotate_rows(list(rows or []))
    ranked = sort_publishable(annotated)
    selected: List[Dict[str, Any]] = []
    seen = set()
    for row in ranked:
        key = _corq_v6_match_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= int(top_n or TOP_N_DEFAULT):
            break

    for idx, row in enumerate(selected, start=1):
        row["top7_rank"] = idx
        row["corq_rank"] = idx
        row["top7_publishable"] = True
        row["eligible_for_top7"] = True
        row["corq_top7_forced_rank_selection"] = True
        row["top7_selection_count_target"] = int(top_n or TOP_N_DEFAULT)
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


def is_publishable(row: Dict[str, Any]) -> bool:
    return not _corq_v6_fatal_reasons(row)


def top7_from_ranking(ranked: Iterable[Dict[str, Any]], top_n: int = TOP_N_DEFAULT, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return select_top7(ranked, top_n=top_n)
