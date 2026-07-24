"""
CORQ eligibility and risk rules.

Architecture rule:
- THINQ provides intelligence inputs.
- CORQ computes final probability and ranking.
- TOP7 is only the first 7 rows from CORQ ranking.

This module is intentionally defensive: missing / invalid data should mark the
prediction as ineligible for production ranking, but should not crash the daily build.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

MIN_TOP_ODDS = 1.40
MAX_TOP_ODDS = 3.50
MAX_ODDS_GAP_PCT = 2.50
MIN_THINQ_CONFIDENCE = 0.15

REJECT_DOUBLES = "REJECT_DOUBLES"
REJECT_MISSING_PICK_ODDS = "REJECT_MISSING_PICK_ODDS"
REJECT_MISSING_OPPONENT_ODDS = "REJECT_MISSING_OPPONENT_ODDS"
REJECT_LOW_ODDS = "REJECT_LOW_ODDS"
REJECT_HIGH_ODDS = "REJECT_HIGH_ODDS"
REJECT_EXTREME_ODDS_GAP = "REJECT_EXTREME_ODDS_GAP"
REJECT_NO_CORQ_PROBABILITY = "REJECT_NO_CORQ_PROBABILITY"
REJECT_NO_THINQ = "REJECT_NO_THINQ"
REJECT_LOW_THINQ_CONFIDENCE = "REJECT_LOW_THINQ_CONFIDENCE"
REJECT_SURFACE_UNKNOWN = "REJECT_SURFACE_UNKNOWN"


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_probability(value: Any) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    if number < 0.0 or number > 1.0:
        return None
    return number


def is_doubles_match(prediction: Dict[str, Any]) -> bool:
    if bool(prediction.get("is_doubles")):
        return True
    match_type = str(prediction.get("match_type") or prediction.get("matchType") or "").lower()
    if "double" in match_type:
        return True
    tournament = str(prediction.get("tournament") or "").lower()
    if "double" in tournament:
        return True
    for key in ("player1", "player2", "pick", "opponent", "match"):
        value = str(prediction.get(key) or "")
        if " / " in value or "/" in value:
            return True
    return False


def get_pick_odds(prediction: Dict[str, Any]) -> float | None:
    for key in ("pick_odds", "odds", "marq_current_pick_odds", "marq_initial_pick_odds"):
        value = safe_float(prediction.get(key))
        if value is not None:
            return value
    return None


def get_opponent_odds(prediction: Dict[str, Any]) -> float | None:
    for key in ("opponent_odds", "marq_current_opponent_odds", "marq_initial_opponent_odds"):
        value = safe_float(prediction.get(key))
        if value is not None:
            return value
    return None


def get_odds_gap_pct(prediction: Dict[str, Any], pick_odds: float | None = None, opponent_odds: float | None = None) -> float | None:
    explicit = safe_float(prediction.get("odds_gap_pct"))
    if explicit is not None:
        return explicit
    pick_odds = pick_odds if pick_odds is not None else get_pick_odds(prediction)
    opponent_odds = opponent_odds if opponent_odds is not None else get_opponent_odds(prediction)
    if pick_odds is None or opponent_odds is None:
        return None
    minimum = min(pick_odds, opponent_odds)
    if minimum <= 0:
        return None
    return abs(pick_odds - opponent_odds) / minimum


def get_corq_probability(prediction: Dict[str, Any]) -> float | None:
    for key in (
        "corq_probability",
        "corq_q_probability",
        "corq_thinq_adjusted_probability",
        "corq_ai_probability",
        "probability",
    ):
        prob = normalize_probability(prediction.get(key))
        if prob is not None:
            return prob
    return None


def get_thinq_available(prediction: Dict[str, Any]) -> bool:
    if prediction.get("thinq_available") is True:
        return True
    thinq = prediction.get("thinq")
    if isinstance(thinq, dict) and thinq.get("available") is True:
        return True
    # Backward-compatible legacy model probability is not enough for new THINQ,
    # but keeps early clean runtime from rejecting everything when THINQ is still being wired.
    if prediction.get("thinq_confidence") is not None:
        return True
    return False


def get_thinq_confidence(prediction: Dict[str, Any]) -> float | None:
    for key in ("thinq_confidence", "thinq_conf", "thinq_data_quality_score"):
        value = safe_float(prediction.get(key))
        if value is not None:
            if value > 1.0:
                value = value / 100.0
            return max(0.0, min(1.0, value))
    thinq = prediction.get("thinq")
    if isinstance(thinq, dict):
        value = safe_float(thinq.get("confidence"))
        if value is not None:
            if value > 1.0:
                value = value / 100.0
            return max(0.0, min(1.0, value))
    return None


def evaluate_corq_eligibility(prediction: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if is_doubles_match(prediction):
        reasons.append(REJECT_DOUBLES)

    pick_odds = get_pick_odds(prediction)
    opponent_odds = get_opponent_odds(prediction)
    if pick_odds is None:
        reasons.append(REJECT_MISSING_PICK_ODDS)
    else:
        if pick_odds < MIN_TOP_ODDS:
            reasons.append(REJECT_LOW_ODDS)
        if pick_odds > MAX_TOP_ODDS:
            reasons.append(REJECT_HIGH_ODDS)

    if opponent_odds is None:
        reasons.append(REJECT_MISSING_OPPONENT_ODDS)

    odds_gap_pct = get_odds_gap_pct(prediction, pick_odds, opponent_odds)
    if odds_gap_pct is not None and odds_gap_pct > MAX_ODDS_GAP_PCT:
        reasons.append(REJECT_EXTREME_ODDS_GAP)

    if get_corq_probability(prediction) is None:
        reasons.append(REJECT_NO_CORQ_PROBABILITY)

    if not get_thinq_available(prediction):
        reasons.append(REJECT_NO_THINQ)
    else:
        conf = get_thinq_confidence(prediction)
        if conf is not None and conf < MIN_THINQ_CONFIDENCE:
            reasons.append(REJECT_LOW_THINQ_CONFIDENCE)

    surface = str(prediction.get("surface") or "").strip().lower()
    if surface in {"", "unknown", "none", "null"}:
        reasons.append(REJECT_SURFACE_UNKNOWN)

    return (len(reasons) == 0), reasons


def apply_corq_eligibility(prediction: Dict[str, Any]) -> Dict[str, Any]:
    eligible, reasons = evaluate_corq_eligibility(prediction)
    prediction = dict(prediction)
    prediction["eligible_for_corq"] = eligible
    prediction["eligible_for_top7"] = eligible
    prediction["corq_reject_reasons"] = reasons
    prediction["corq_rules"] = {
        "min_top_odds": MIN_TOP_ODDS,
        "max_top_odds": MAX_TOP_ODDS,
        "max_odds_gap_pct": MAX_ODDS_GAP_PCT,
        "min_thinq_confidence": MIN_THINQ_CONFIDENCE,
    }
    return prediction
