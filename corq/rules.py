"""CORQ ranking rules and risk guards."""

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
MIN_THINQ_CONFIDENCE = 0.15
MAX_ODDS_GAP_PCT = 2.50
MAX_UNCONFIRMED_ODDS_GAP_PCT = 1.50
MIN_MINUTES_BEFORE_START = 10


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
    confirmed_directions = {"DIRECT_TO_MATCH_PLAYERS", "REVERSED_TO_MATCH_PLAYERS", "CONFIRMED_BY_LABELS"}
    if direction in confirmed_directions:
        return False
    if record.get("odds_labels_confirmed") is True:
        return False
    return True


def apply_risk_adjustments(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    score = as_float(out.get("corq_score"), 0.0) or 0.0
    edge = as_float(out.get("corq_edge"), 0.0) or 0.0
    odds = as_float(out.get("odds") or out.get("pick_odds"))

    edge_bonus = max(min(edge * 0.25, 0.02), -0.02)
    penalty = 0.0
    flags: List[str] = list(out.get("corq_risk_flags") or [])

    if odds and odds < 1.60 and score >= 0.75 and edge >= 0.12:
        penalty += 0.06
        flags.append("LOW_ODDS_OVERCONFIDENCE")

    if odds and odds < 1.60 and edge >= 0.14:
        penalty += 0.04
        flags.append("LOW_ODDS_EXTREME_EDGE")

    odds_gap_pct = as_float(out.get("odds_gap_pct"))
    if odds_gap_pct is not None and odds_gap_pct >= MAX_UNCONFIRMED_ODDS_GAP_PCT and _odds_orientation_unconfirmed(out):
        # Risk flag only here. Hard reject is handled in evaluate_eligibility.
        flags.append("ODDS_ORIENTATION_UNCONFIRMED_EXTREME")

    adjusted = score + edge_bonus - penalty
    out["corq_edge_bonus"] = round(edge_bonus, 4)
    out["corq_risk_penalty"] = round(penalty, 4)
    out["corq_risk_flags"] = sorted(set(flags))
    out["corq_adjusted_score"] = round(max(min(adjusted, 0.99), 0.01), 4)
    return out


def evaluate_eligibility(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    reasons: List[str] = []

    status_type = _status_type(out)
    status_code = _status_code(out)
    if status_type not in {"notstarted", "not started", "scheduled", "unknown"}:
        reasons.append("REJECT_NOT_NOTSTARTED")
    if status_code not in (None, 0):
        reasons.append("REJECT_STATUS_NOT_OPEN")

    start_dt = _parse_datetime(out.get("match_start") or out.get("start_time"))
    if start_dt is None:
        reasons.append("REJECT_MISSING_START_TIME")
    else:
        cutoff = datetime.now(timezone.utc) + timedelta(minutes=MIN_MINUTES_BEFORE_START)
        if start_dt <= cutoff:
            reasons.append("REJECT_STARTED_OR_TOO_CLOSE")

    if out.get("is_doubles"):
        reasons.append("REJECT_DOUBLES")

    odds = as_float(out.get("odds") or out.get("pick_odds"))
    opponent_odds = as_float(out.get("opponent_odds"))

    if odds is None:
        reasons.append("REJECT_MISSING_ODDS")
    elif odds < MIN_TOP_ODDS:
        reasons.append("REJECT_LOW_ODDS")

    if opponent_odds is None:
        reasons.append("REJECT_MISSING_OPPONENT_ODDS")

    odds_gap_pct = as_float(out.get("odds_gap_pct"))
    if odds_gap_pct is None and odds and opponent_odds:
        odds_gap_pct = abs(odds - opponent_odds) / max(min(odds, opponent_odds), 0.0001)
    out["odds_gap_pct"] = round(odds_gap_pct, 4) if odds_gap_pct is not None else None

    if odds_gap_pct is not None and odds_gap_pct > MAX_ODDS_GAP_PCT:
        reasons.append("REJECT_EXTREME_ODDS_GAP")

    if odds_gap_pct is not None and odds_gap_pct >= MAX_UNCONFIRMED_ODDS_GAP_PCT and _odds_orientation_unconfirmed(out):
        reasons.append("REJECT_ODDS_ORIENTATION_UNCONFIRMED_EXTREME")

    surface = str(out.get("surface") or "").strip().lower()
    if not surface or surface == "unknown":
        reasons.append("REJECT_SURFACE_UNKNOWN")

    if not out.get("thinq_available", False):
        reasons.append("REJECT_NO_THINQ")

    thinq_conf = as_float(out.get("thinq_confidence"), 0.0) or 0.0
    if thinq_conf < MIN_THINQ_CONFIDENCE:
        reasons.append("REJECT_LOW_THINQ_CONFIDENCE")

    out["eligible_for_corq"] = len(reasons) == 0
    out["corq_reject_reasons"] = sorted(set(reasons))
    return out
