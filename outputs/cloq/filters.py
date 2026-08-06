"""Simple value-first CloQ filters.

CloQ rules in this version:
- pick odds >= 1.70
- odds gap <= 15%, calculated against the smaller of pick/opponent odds
- value must not be negative when value data is available
- if value data is missing, do not fabricate it; publish only with NO_VALUE_DATA
- prematch singles only
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

MODEL_VERSION = "CLOQ_SIMPLE_VALUE_V5"
MIN_PICK_ODDS = 1.70
MAX_ODDS_GAP_PCT = 0.15
DEFAULT_MAX_PICK_ODDS = 3.50

OPEN_STATUS_TYPES = {
    "", "notstarted", "not_started", "scheduled", "open", "prematch",
    "pre-match", "upcoming", "pending",
}

BLOCKED_STATUS_TYPES = {
    "finished", "ended", "complete", "completed", "inprogress", "in_progress",
    "live", "started", "cancelled", "canceled", "postponed", "retired",
    "walkover", "interrupted", "suspended",
}


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-", "N/A", "NA", "None", "null"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def probability(value: Any, default: Optional[float] = None) -> Optional[float]:
    number = as_float(value, None)
    if number is None:
        return default
    if number > 1.5:
        number /= 100.0
    if 0.0 <= number <= 1.0:
        return number
    return default


def first_present(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if "." in key:
            cur: Any = row
            ok = True
            for part in key.split("."):
                if not isinstance(cur, dict):
                    ok = False
                    break
                cur = cur.get(part)
            if ok and cur not in (None, "", "—", "-"):
                return cur
        else:
            value = row.get(key)
            if value not in (None, "", "—", "-"):
                return value
    return None


def pick_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "pick", "cloq_pick", "player", "player1", "home") or "—").strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "opponent", "opp", "player2", "away") or "—").strip()


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    return as_float(first_present(row, "pick_odds", "cloq_pick_odds", "selected_odds", "odds", "odds_decimal", "decimal_odds"), None)


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    return as_float(first_present(row, "opponent_odds", "opp_odds", "cloq_opponent_odds", "opponent_price"), None)


def corq_probability(row: Dict[str, Any]) -> Optional[float]:
    return probability(first_present(
        row,
        "corq_calibrated_probability",
        "corq_estimated_win_probability",
        "corq_probability",
        "win_probability",
        "estimated_win_probability",
        "probability",
    ), None)


def break_even_probability(row: Dict[str, Any]) -> Optional[float]:
    odds = pick_odds(row)
    if not odds or odds <= 0:
        return None
    return 1.0 / odds


def value_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(first_present(row, "corq_value_delta_pp", "value_delta_pp", "cloq_value_delta_pp"), None)
    if explicit is not None:
        return explicit
    cp = corq_probability(row)
    be = break_even_probability(row)
    if cp is None or be is None:
        return None
    return round((cp - be) * 100.0, 4)


def expected_value_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(first_present(row, "expected_value_pct", "ev_pct", "cloq_expected_value_pct"), None)
    if explicit is not None:
        return explicit
    cp = corq_probability(row)
    odds = pick_odds(row)
    if cp is None or not odds:
        return None
    return round((cp * odds - 1.0) * 100.0, 4)


def odds_gap_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(first_present(row, "odds_gap_pct", "cloq_odds_gap_pct"), None)
    if explicit is not None:
        return explicit
    p = pick_odds(row)
    o = opponent_odds(row)
    if not p or not o:
        return None
    base = min(p, o)
    if base <= 0:
        return None
    return round(abs(p - o) / base, 6)


def close_odds_bonus(row: Dict[str, Any]) -> Tuple[float, str]:
    gap = odds_gap_pct(row)
    if gap is None:
        return 0.0, "missing_gap"
    if gap <= 0.05:
        return 3.0, "very_close"
    if gap <= 0.10:
        return 2.0, "close"
    if gap <= MAX_ODDS_GAP_PCT:
        return 1.0, "playable_close"
    return 0.0, "wide_gap"


def status_type(row: Dict[str, Any]) -> str:
    raw = first_present(row, "status_type", "match_status_type", "status")
    if not raw and isinstance(row.get("raw"), dict):
        raw_status = row.get("raw", {}).get("status")
        if isinstance(raw_status, dict):
            raw = raw_status.get("type") or raw_status.get("description")
    return str(raw or "").strip().lower().replace(" ", "_")


def status_code(row: Dict[str, Any]) -> Optional[int]:
    value = first_present(row, "status_code", "match_status_code")
    if value is None and isinstance(row.get("raw"), dict):
        raw_status = row.get("raw", {}).get("status")
        if isinstance(raw_status, dict):
            value = raw_status.get("code")
    try:
        return int(float(value)) if value not in (None, "") else None
    except Exception:
        return None


def is_prematch(row: Dict[str, Any]) -> bool:
    st = status_type(row)
    code = status_code(row)
    if st in BLOCKED_STATUS_TYPES:
        return False
    if st in OPEN_STATUS_TYPES:
        return True
    return str(code) == "0" and st not in BLOCKED_STATUS_TYPES


def is_doubles(row: Dict[str, Any]) -> bool:
    if row.get("is_doubles") is True:
        return True
    text = " ".join(str(first_present(row, key) or "") for key in ("match_type", "type", "event_type", "category", "competition", "tournament"))
    return "double" in text.lower()


def market_text(row: Dict[str, Any]) -> str:
    return " | ".join(str(first_present(row, key) or "") for key in (
        "marq_final", "marq_final_display", "final_marq", "market_final", "marq_market_final", "market_read"
    )).lower().replace("_", " ")


def market_with_pick(row: Dict[str, Any]) -> bool:
    return "market with pick" in market_text(row)


def market_against_pick(row: Dict[str, Any]) -> bool:
    return "market against pick" in market_text(row)


def value_status(row: Dict[str, Any]) -> str:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if vd is None and ev is None:
        return "NO_VALUE_DATA"
    if (vd is not None and vd < 0) or (ev is not None and ev < 0):
        return "VALUE_NEGATIVE"
    if (vd is not None and vd >= 3.0) or (ev is not None and ev >= 3.0):
        return "VALUE_POSITIVE"
    return "VALUE_NON_NEGATIVE"


def cloq_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    odds = pick_odds(row)
    gap = odds_gap_pct(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)

    if not is_prematch(row):
        reasons.append("REJECT_CLOQ_STATUS_NOT_PREMATCH")
    if is_doubles(row):
        reasons.append("REJECT_CLOQ_DOUBLES")
    if odds is None:
        reasons.append("REJECT_CLOQ_MISSING_PICK_ODDS")
    elif odds < MIN_PICK_ODDS:
        reasons.append("REJECT_CLOQ_ODDS_UNDER_1_70")
    if gap is None:
        reasons.append("REJECT_CLOQ_MISSING_ODDS_GAP")
    elif gap > MAX_ODDS_GAP_PCT:
        reasons.append("REJECT_CLOQ_ODDS_GAP_OVER_15")
    if (vd is not None and vd < 0) or (ev is not None and ev < 0):
        reasons.append("REJECT_CLOQ_NEGATIVE_VALUE")
    # Missing value is not a hard reject if all structural checks pass.
    return list(dict.fromkeys(reasons))


def cloq_support_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    bonus, bucket = close_odds_bonus(row)
    if vd is None and ev is None:
        tags.append("NO_VALUE_DATA")
    else:
        if vd is not None and vd >= 0:
            tags.append("VALUE_DELTA_NON_NEGATIVE")
        if ev is not None and ev >= 0:
            tags.append("EXPECTED_VALUE_NON_NEGATIVE")
        if vd is not None and vd >= 3.0:
            tags.append("VALUE_DELTA_POSITIVE")
        if ev is not None and ev >= 3.0:
            tags.append("EXPECTED_VALUE_POSITIVE")
    if market_with_pick(row):
        tags.append("MARKET_WITH_PICK")
    if market_against_pick(row):
        tags.append("MARKET_AGAINST_PICK_INFO")
    if bonus > 0:
        tags.append(bucket.upper())
    return list(dict.fromkeys(tags))


def cloq_risk_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    if value_status(row) == "NO_VALUE_DATA":
        tags.append("NO_VALUE_DATA")
    if market_against_pick(row):
        tags.append("MARKET_AGAINST_PICK")
    gap = odds_gap_pct(row)
    if gap is not None and gap > 0.10:
        tags.append("ODDS_GAP_NEAR_LIMIT")
    return list(dict.fromkeys(tags))


def cloq_decision(row: Dict[str, Any]) -> str:
    reasons = cloq_reject_reasons(row)
    if reasons:
        return "CLOQ_REJECTED"
    if value_status(row) == "NO_VALUE_DATA":
        return "CLOQ_NO_VALUE_DATA"
    if cloq_risk_tags(row):
        return "CLOQ_VALUE_INFO"
    return "CLOQ_CLEAN"


def cloq_score(row: Dict[str, Any]) -> float:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    cp = corq_probability(row) or 0.0
    gap = odds_gap_pct(row)
    odds = pick_odds(row) or 0.0
    close_bonus, _ = close_odds_bonus(row)

    score = 0.0
    if vd is not None:
        score += max(vd, 0.0) * 3.0
    if ev is not None:
        score += max(ev, 0.0) * 0.8
    if vd is None and ev is None:
        score -= 2.0
    score += cp * 5.0
    score += close_bonus * 2.0
    score += min(max(odds - MIN_PICK_ODDS, 0.0), 1.0)
    if gap is not None:
        score += max(0.0, MAX_ODDS_GAP_PCT - gap) * 20.0
    if market_with_pick(row):
        score += 2.0
    if market_against_pick(row):
        score -= 1.0
    return round(score, 4)


def annotate_cloq(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    bonus, bucket = close_odds_bonus(row)
    reasons = cloq_reject_reasons(row)
    decision = cloq_decision(row)
    supports = cloq_support_tags(row)
    risks = cloq_risk_tags(row)
    out["cloq_model_version"] = MODEL_VERSION
    out["cloq_policy"] = "odds>=1.70,value_non_negative_or_no_value_data,odds_gap<=15pct_using_min_odds"
    out["cloq_pick"] = pick_name(row)
    out["cloq_opponent"] = opponent_name(row)
    out["cloq_pick_odds"] = pick_odds(row)
    out["cloq_opponent_odds"] = opponent_odds(row)
    out["cloq_corq_probability"] = corq_probability(row)
    out["cloq_break_even_probability"] = break_even_probability(row)
    out["cloq_value_delta_pp"] = value_delta_pp(row)
    out["cloq_expected_value_pct"] = expected_value_pct(row)
    out["cloq_value_status"] = value_status(row)
    out["cloq_decision"] = decision
    out["cloq_odds_gap_pct"] = odds_gap_pct(row)
    out["cloq_odds_gap_group"] = bucket
    out["cloq_close_bonus"] = bonus
    out["cloq_support_tags"] = supports
    out["cloq_risk_tags"] = risks
    out["cloq_reject_reasons"] = reasons
    out["cloq_publishable"] = not reasons
    out["cloq_score"] = cloq_score(row) if not reasons else -9999.0
    if value_status(row) == "NO_VALUE_DATA" and not reasons:
        out["cloq_selected_reason"] = "no_value_data_but_odds_and_gap_ok"
    return out


def match_identity(row: Dict[str, Any]) -> str:
    return str(first_present(row, "match_key", "event_id", "match_id", "id") or "".join(sorted([pick_name(row).lower(), opponent_name(row).lower()])))
