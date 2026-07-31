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
    """Return ThinQ pick win probability, not confidence."""
    value = _first(row, ["thinq_pick_probability", "thinq_probability"], None)
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "pick_probability")
    if value is None:
        value = _get_nested(row, "thinq", "thinq_probability_layer", "pick_probability")
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
        reasons.append("REJECT_TOP7_STATUS_NOT_NOTSTARTED")
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

    row["top7_filter_mode"] = TOP7_FILTER_MODE
    row["top7_publishable"] = not reasons
    row["eligible_for_top7"] = not reasons
    row["top7_quality_reject_reasons"] = reasons
    row["top7_reject_reasons"] = reasons
    row["top7_status_type_normalized"] = status_type(row)
    row["top7_status_code"] = status_code(row)
    row["top7_corq_probability"] = round(cp, 6)
    row["top7_pick_thinq_edge"] = round(edge, 6)
    row["top7_thinq_confidence"] = round(conf, 6)
    row["top7_thinq_data_confidence"] = round(conf, 6)
    row["top7_thinq_pick_probability"] = round(thinq_pick_probability(row), 6)
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
    for row in publishable:
        key = (
            row.get("match_key")
            or row.get("event_id")
            or row.get("id")
            or "|".join(sorted([str(row.get("player1") or row.get("home") or ""), str(row.get("player2") or row.get("away") or "")]))
        )
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
    """Return publishable TOP7 rows from an already ranked list."""
    rows = annotate_rows(list(ranked or []))
    publishable = sort_publishable(rows)
    selected: List[Dict[str, Any]] = []
    seen_matches = set()
    for row in publishable:
        key = (
            row.get("match_key")
            or row.get("event_id")
            or row.get("id")
            or "|".join(sorted([str(row.get("player1") or row.get("home") or ""), str(row.get("player2") or row.get("away") or "")]))
        )
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

