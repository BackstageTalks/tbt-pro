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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

TOP_N_DEFAULT = 7
TOP7_FILTER_MODE = "PUBLISHABLE_CORQ_THINQ_GUARD_V1"

MIN_CORQ_PROBABILITY = 0.50
MIN_PICK_THINQ_EDGE = 0.0
MIN_PICK_DATA_DEPTH = 0.40
MIN_ELO_DEPTH_IF_MISSING = 0.50
MIN_THINQ_CONFIDENCE = 0.50
EXTREME_UNKNOWN_ODDS_GAP_PCT = 1.50

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
    value = _first(
        row,
        [
            "thinq_probability_confidence",
            "thinq_confidence",
            "thinQ_confidence",
            "thinq_data_confidence",
        ],
        None,
    )
    if value is None:
        value = _get_nested(row, "thinq_probability_layer", "confidence")
    if value is None:
        value = _get_nested(row, "thinq", "confidence")
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

    This is not the same as ThinQ confidence.  It combines global ThinQ data
    confidence with signal strength in favor of the displayed pick.
    """
    edge = pick_thinq_edge(row)
    conf = thinq_confidence(row)
    if edge <= 0 or conf <= 0:
        return 0.0
    # Full depth once ThinQ edge reaches +10 percentage points.
    strength = min(edge / 0.10, 1.0)
    return max(0.0, min(conf * strength, 1.0))


def pick_data_depth(row: Dict[str, Any]) -> float:
    # Always recompute to avoid the older duplicate behavior where this field
    # simply copied ThinQ confidence.
    return computed_pick_data_depth(row)


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


def top7_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    cp = corq_probability(row)
    edge = pick_thinq_edge(row)
    depth = pick_data_depth(row)

    if not is_notstarted(row):
        reasons.append("REJECT_TOP7_STATUS_NOT_NOTSTARTED")
    if cp < MIN_CORQ_PROBABILITY:
        reasons.append("REJECT_TOP7_CORQ_BELOW_50")
    if edge < MIN_PICK_THINQ_EDGE:
        reasons.append("REJECT_TOP7_THINQ_EDGE_AGAINST_PICK")
    if depth < MIN_PICK_DATA_DEPTH:
        reasons.append("REJECT_TOP7_LOW_PICK_DATA_DEPTH")
    if thinq_confidence(row) < MIN_THINQ_CONFIDENCE:
        reasons.append("REJECT_TOP7_LOW_THINQ_CONFIDENCE")
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


def top7_quality_score(row: Dict[str, Any]) -> float:
    """Score among already publishable candidates.

    Odds are deliberately *not* a primary driver.  The score favors high final
    CorQ probability, actual pick support, ThinQ edge and data quality.
    """
    cp = corq_probability(row) * 100.0
    depth = pick_data_depth(row) * 100.0
    edge = max(pick_thinq_edge(row), 0.0) * 100.0
    conf = thinq_confidence(row) * 100.0
    return round(cp + 0.25 * depth + 0.20 * edge + 0.10 * conf, 4)


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
    row["pick_data_depth"] = round(depth, 6)
    row["stat_data_depth"] = round(depth, 6)
    row["top7_quality_score"] = top7_quality_score(row) if not reasons else 0.0
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
    """Return broad ALL audit view with TOP7 quality annotations.

    Legacy engine imports this name directly.  ALL must stay broad, so this
    function annotates rows but does not remove rejected/non-publishable rows.
    """
    return annotate_rows(list(predictions or []))


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

