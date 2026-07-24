"""CORQ broad runtime rules.

Current phase: build stable runtime and web/audit flow first.
Do NOT tighten production filters too early.

Hard rejects are intentionally minimal:
- missing odds
- low odds
- doubles
- invalid side orientation
- missing/unknown surface only as soft warning for now

Everything else is captured as flags, not as hard rejection:
- MISSING_ELO
- NO_H2H_DATA
- RECENT_FORM_NO_DATA
- LOW_THINQ_CONFIDENCE
- DEFAULT_SCORE_VALUE_TRAP
- ODDS_ORIENTATION_UNCONFIRMED
- STARTED_OR_TOO_CLOSE

Final production filtering should be tightened later after runtime, web and
results flow are stable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def as_float(value: Any, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


MIN_TOP_ODDS = 1.40
MIN_MINUTES_BEFORE_START = 10
MAX_UNCONFIRMED_ODDS_GAP_PCT = 1.50


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            text = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def _status_type(record: Dict[str, Any]) -> str:
    if record.get("status_type"):
        return str(record.get("status_type")).strip().lower()
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    return str(status.get("type") or status.get("description") or "unknown").strip().lower()


def _status_code(record: Dict[str, Any]) -> Optional[int]:
    if record.get("status_code") not in (None, ""):
        try:
            return int(record.get("status_code"))
        except Exception:
            return None
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    try:
        return int(status.get("code"))
    except Exception:
        return None


def _odds_orientation_unconfirmed(record: Dict[str, Any]) -> bool:
    direction = str(record.get("odds_matching_direction") or "").strip().upper()
    confirmed_directions = {
        "DIRECT_TO_MATCH_PLAYERS",
        "REVERSED_TO_MATCH_PLAYERS",
        "CONFIRMED_BY_LABELS",
        "DIRECT_BY_NUMERIC_OUTCOME",
        "REVERSED_BY_NUMERIC_OUTCOME",
    }
    if direction in confirmed_directions:
        return False
    if record.get("odds_labels_confirmed") is True:
        return False
    return True


def _side_invalid(record: Dict[str, Any]) -> bool:
    side_audit = record.get("side_audit") if isinstance(record.get("side_audit"), dict) else {}
    thinq = record.get("thinq") if isinstance(record.get("thinq"), dict) else {}
    thinq_side = thinq.get("thinq_side") if isinstance(thinq.get("thinq_side"), dict) else record.get("thinq_side") if isinstance(record.get("thinq_side"), dict) else {}
    if side_audit and side_audit.get("side_valid") is False:
        return True
    if thinq_side and thinq_side.get("side_valid") is False:
        return True
    if record.get("side_locked") is False:
        return True
    return False


def _all_flags(record: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    for key in ("thinq_flags", "corq_risk_flags"):
        value = record.get(key)
        if isinstance(value, list):
            flags.extend(str(item) for item in value)
    thinq = record.get("thinq") if isinstance(record.get("thinq"), dict) else {}
    for key in ("flags", "thinq_flags"):
        value = thinq.get(key)
        if isinstance(value, list):
            flags.extend(str(item) for item in value)
    return sorted(set(flags))


def _edge_direction_flag(prefix: str, value: float) -> str:
    if value > 0:
        return f"{prefix}_PICK_EDGE"
    if value < 0:
        return f"{prefix}_OPP_EDGE"
    return f"{prefix}_NEUTRAL"


def apply_risk_adjustments(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    score = as_float(out.get("corq_score"), 0.0) or 0.0
    edge = as_float(out.get("corq_edge"), 0.0) or 0.0
    odds = as_float(out.get("odds") or out.get("pick_odds"))

    edge_bonus = max(min(edge * 0.25, 0.02), -0.02)
    penalty = 0.0
    flags: List[str] = list(out.get("corq_risk_flags") or [])

    # Keep legacy risk flags as diagnostics only during broad runtime phase.
    if odds and odds < 1.60 and score >= 0.75 and edge >= 0.12:
        flags.append("LOW_ODDS_OVERCONFIDENCE")
    if odds and odds < 1.60 and edge >= 0.14:
        flags.append("LOW_ODDS_EXTREME_EDGE")

    odds_gap_pct = as_float(out.get("odds_gap_pct"))
    if odds_gap_pct is not None and odds_gap_pct >= MAX_UNCONFIRMED_ODDS_GAP_PCT and _odds_orientation_unconfirmed(out):
        flags.append("ODDS_ORIENTATION_UNCONFIRMED_EXTREME")
    elif _odds_orientation_unconfirmed(out):
        flags.append("ODDS_ORIENTATION_UNCONFIRMED")

    all_flags = _all_flags(out)
    for data_flag in ("MISSING_ELO", "NO_H2H_DATA", "RECENT_FORM_NO_DATA", "RECENT_FORM_THIN_PICK", "RECENT_FORM_THIN_OPPONENT", "SURFACE_RECENT_FORM_THIN"):
        if data_flag in all_flags:
            flags.append(data_flag)

    thinq_conf = as_float(out.get("thinq_confidence"), 0.0) or 0.0
    if thinq_conf < 0.50:
        flags.append("LOW_THINQ_CONFIDENCE")

    if abs(score - 0.5) < 0.0001 and edge > 0.10:
        flags.append("DEFAULT_SCORE_VALUE_TRAP")

    if _side_invalid(out):
        flags.append("SIDE_ORIENTATION_INVALID")

    edges = out.get("thinq_edges") if isinstance(out.get("thinq_edges"), dict) else {}
    for key, prefix in (
        ("elo_edge", "ELO"),
        ("recent_form_edge", "RECENT_FORM"),
        ("surface_recent_form_edge", "SURFACE_FORM"),
        ("h2h_edge", "H2H"),
    ):
        value = as_float(edges.get(key), 0.0) or 0.0
        flags.append(_edge_direction_flag(prefix, value))

    adjusted = score + edge_bonus - penalty
    out["corq_edge_bonus"] = round(edge_bonus, 4)
    out["corq_risk_penalty"] = round(penalty, 4)
    out["corq_risk_flags"] = sorted(set(flags))
    out["corq_adjusted_score"] = round(max(min(adjusted, 0.99), 0.01), 4)
    return out


def evaluate_eligibility(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    reasons: List[str] = []
    warnings: List[str] = []

    status_type = _status_type(out)
    status_code = _status_code(out)
    if status_type not in {"notstarted", "not started", "scheduled", "unknown"}:
        warnings.append("WARN_NOT_NOTSTARTED")
    if status_code not in (None, 0):
        warnings.append("WARN_STATUS_NOT_OPEN")

    start_dt = _parse_datetime(out.get("match_start") or out.get("start_time"))
    if start_dt is None:
        warnings.append("WARN_MISSING_START_TIME")
    else:
        cutoff = datetime.now(timezone.utc) + timedelta(minutes=MIN_MINUTES_BEFORE_START)
        if start_dt <= cutoff:
            warnings.append("WARN_STARTED_OR_TOO_CLOSE")

    if out.get("is_doubles"):
        reasons.append("REJECT_DOUBLES")

    if _side_invalid(out):
        reasons.append("REJECT_SIDE_ORIENTATION_INVALID")

    odds = as_float(out.get("odds") or out.get("pick_odds"))
    opponent_odds = as_float(out.get("opponent_odds"))

    if odds is None:
        reasons.append("REJECT_MISSING_ODDS")
    elif odds < MIN_TOP_ODDS:
        reasons.append("REJECT_LOW_ODDS")

    if opponent_odds is None:
        warnings.append("WARN_MISSING_OPPONENT_ODDS")

    odds_gap_pct = as_float(out.get("odds_gap_pct"))
    if odds_gap_pct is None and odds and opponent_odds:
        odds_gap_pct = abs(odds - opponent_odds) / max(min(odds, opponent_odds), 0.0001)
    out["odds_gap_pct"] = round(odds_gap_pct, 4) if odds_gap_pct is not None else None

    if odds_gap_pct is not None and odds_gap_pct >= MAX_UNCONFIRMED_ODDS_GAP_PCT and _odds_orientation_unconfirmed(out):
        warnings.append("WARN_ODDS_ORIENTATION_UNCONFIRMED_EXTREME")

    surface = str(out.get("surface") or "").strip().lower()
    if not surface or surface == "unknown":
        warnings.append("WARN_SURFACE_UNKNOWN")

    if not out.get("thinq_available", False):
        warnings.append("WARN_NO_THINQ")

    thinq_conf = as_float(out.get("thinq_confidence"), 0.0) or 0.0
    if thinq_conf < 0.50:
        warnings.append("WARN_LOW_THINQ_CONFIDENCE")

    all_flags = _all_flags(out)
    if "MISSING_ELO" in all_flags:
        warnings.append("WARN_MISSING_ELO")
    if "NO_H2H_DATA" in all_flags:
        warnings.append("WARN_NO_H2H_DATA")
    if "RECENT_FORM_NO_DATA" in all_flags:
        warnings.append("WARN_RECENT_FORM_NO_DATA")

    score = as_float(out.get("corq_score"), 0.0) or 0.0
    edge = as_float(out.get("corq_edge"), 0.0) or 0.0
    if abs(score - 0.5) < 0.0001 and edge > 0.10:
        warnings.append("WARN_DEFAULT_SCORE_VALUE_TRAP")

    out["eligible_for_corq"] = len(reasons) == 0
    out["corq_reject_reasons"] = sorted(set(reasons))
    out["corq_warning_flags"] = sorted(set(warnings))
    return out
