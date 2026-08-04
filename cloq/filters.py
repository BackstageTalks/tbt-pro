"""Value-first CloQ filters and scoring helpers.

CloQ uses real fields already produced by the CorQ daily runtime. It does not
invent probabilities, odds, value or market data. Missing values stay missing
and are exposed as reject reasons or audit fields.

Design intent for V1:
- Value is the first-class signal.
- Close odds are a soft bonus only, not a hard 15% gate.
- No penalty is applied for wide odds gap in this phase.
- Short favourites with clearly negative value are blocked from CloQ shortlist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

MIN_PICK_ODDS = 1.40
SHORT_PRICE_LIMIT = 1.50
VALUE_POSITIVE_PP = 0.0
VALUE_NEUTRAL_FLOOR_PP = -2.0
EV_NEUTRAL_FLOOR_PCT = -3.0
NEGATIVE_VALUE_HARD_PP = -5.0
NEGATIVE_EV_HARD_PCT = -8.0
MIN_CLOQ_MODEL_PROBABILITY = 0.45
MIN_CLOQ_THINQ_EDGE = 0.0
LONG_ODDS_LIMIT = 3.50
LONG_ODDS_MIN_MODEL_PROBABILITY = 0.50
LONG_ODDS_MIN_THINQ_EDGE = 0.03
VALUE_DELTA_SCORE_CAP_PP = 8.0
EXPECTED_VALUE_SCORE_CAP_PCT = 25.0

OPEN_STATUS_TYPES = {
    "notstarted",
    "not_started",
    "scheduled",
    "open",
    "prematch",
    "pre-match",
    "upcoming",
    "pending",
    "",
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


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-", "N/A", "NA", "None", "null"):
            return default
        if isinstance(value, bool):
            return float(value)
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
    return str(first_present(row, "pick", "cloq_pick", "player", "player1", "home") or "—")


def opponent_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "opponent", "opp", "player2", "away") or "—")


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
        "corq_score",
    ), None)


def thinq_edge(row: Dict[str, Any]) -> float:
    value = as_float(first_present(row, "pick_thinq_edge", "thinq_edge", "thinq_total_edge", "top7_pick_thinq_edge"), None)
    if value is not None:
        return value / 100.0 if abs(value) > 1.5 else value
    prob = probability(first_present(row, "thinq_pick_probability", "thinq_probability", "top7_thinq_pick_probability"), None)
    return (prob - 0.50) if prob is not None else 0.0


def thinq_confidence(row: Dict[str, Any]) -> float:
    return probability(first_present(row, "thinq_data_confidence", "thinq_confidence", "thinq_probability_confidence", "confidence"), 0.0) or 0.0


def data_depth(row: Dict[str, Any]) -> float:
    for key in ("pick_data_depth", "stat_data_depth", "s_data_depth", "sets_games_data_depth"):
        value = probability(row.get(key), None)
        if value is not None:
            return value
    return thinq_confidence(row)


def form_depth(row: Dict[str, Any]) -> float:
    return probability(first_present(row, "form_data_depth", "form_confidence", "thinq_form_confidence"), 0.0) or 0.0


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
        return 0.0, "unknown"
    if gap <= 0.15:
        return 3.0, "close_value"
    if gap <= 0.25:
        return 1.5, "playable_close"
    if gap <= 0.40:
        return 0.0, "neutral_gap"
    return 0.0, "open_gap"


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
    text = " ".join(str(first_present(row, key) or "") for key in ("match_type", "type", "event_type", "category"))
    return "double" in text.lower()


def market_with_pick(row: Dict[str, Any]) -> bool:
    text = " | ".join(str(first_present(row, key) or "") for key in (
        "marq_final", "marq_final_display", "final_marq", "market_final", "marq_market_final"
    )).lower().replace("_", " ")
    return "market with pick" in text


def market_against_pick(row: Dict[str, Any]) -> bool:
    text = " | ".join(str(first_present(row, key) or "") for key in (
        "marq_final", "marq_final_display", "final_marq", "market_final", "marq_market_final"
    )).lower().replace("_", " ")
    return "market against pick" in text


def value_status(row: Dict[str, Any]) -> str:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if vd is not None and vd >= VALUE_POSITIVE_PP:
        return "VALUE_POSITIVE"
    if ev is not None and ev >= 0:
        return "VALUE_POSITIVE"
    if (vd is not None and vd >= VALUE_NEUTRAL_FLOOR_PP) and (ev is None or ev >= EV_NEUTRAL_FLOOR_PCT):
        return "VALUE_NEUTRAL"
    return "VALUE_NEGATIVE"


def cloq_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    odds = pick_odds(row)
    cp = corq_probability(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if not is_prematch(row):
        reasons.append("REJECT_CLOQ_STATUS_NOT_PREMATCH")
    if is_doubles(row):
        reasons.append("REJECT_CLOQ_DOUBLES")
    if odds is None:
        reasons.append("REJECT_CLOQ_MISSING_PICK_ODDS")
    elif odds < MIN_PICK_ODDS:
        reasons.append("REJECT_CLOQ_ODDS_UNDER_1_40")
    if cp is None:
        reasons.append("REJECT_CLOQ_MISSING_CORQ_PROBABILITY")
    if vd is None and ev is None:
        reasons.append("REJECT_CLOQ_MISSING_VALUE_DATA")

    # V2 guard: CloQ is a playable value shortlist, not a pure underdog/lottery screen.
    # Positive value alone is not enough if the model still gives the pick a low win chance.
    edge = thinq_edge(row)
    if cp is not None and cp < MIN_CLOQ_MODEL_PROBABILITY:
        reasons.append("REJECT_CLOQ_LOW_MODEL_PROBABILITY")
    if edge < MIN_CLOQ_THINQ_EDGE:
        reasons.append("REJECT_CLOQ_THINQ_EDGE_NOT_SUPPORTIVE")
    if market_against_pick(row) and (cp is None or cp < 0.55):
        reasons.append("REJECT_CLOQ_MARKET_AGAINST_LOW_MODEL_SUPPORT")
    if odds is not None and odds >= LONG_ODDS_LIMIT and (cp is None or cp < LONG_ODDS_MIN_MODEL_PROBABILITY or edge < LONG_ODDS_MIN_THINQ_EDGE):
        reasons.append("REJECT_CLOQ_LONG_ODDS_LOW_MODEL_SUPPORT")

    if odds is not None and odds < SHORT_PRICE_LIMIT and ((vd is not None and vd <= NEGATIVE_VALUE_HARD_PP) or (ev is not None and ev <= NEGATIVE_EV_HARD_PCT)):
        reasons.append("REJECT_CLOQ_SHORT_PRICE_NEGATIVE_VALUE_TRAP")
    if value_status(row) == "VALUE_NEGATIVE" and ((vd is not None and vd <= NEGATIVE_VALUE_HARD_PP) or (ev is not None and ev <= NEGATIVE_EV_HARD_PCT)):
        reasons.append("REJECT_CLOQ_HARD_NEGATIVE_VALUE")
    return list(dict.fromkeys(reasons))


def cloq_support_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    edge = thinq_edge(row)
    cp = corq_probability(row)
    close_bonus, bucket = close_odds_bonus(row)
    if vd is not None and vd >= 0:
        tags.append("VALUE_DELTA_POSITIVE")
    if ev is not None and ev >= 0:
        tags.append("EXPECTED_VALUE_POSITIVE")
    if value_status(row) == "VALUE_NEUTRAL":
        tags.append("VALUE_NEUTRAL")
    if edge > 0:
        tags.append("THINQ_EDGE_SUPPORT")
    if cp is not None and cp >= 0.55:
        tags.append("CORQ_PROB_SUPPORT")
    if market_with_pick(row):
        tags.append("MARKET_WITH_PICK")
    if close_bonus > 0:
        tags.append(bucket.upper())
    return list(dict.fromkeys(tags))


def cloq_risk_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    odds = pick_odds(row)
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    if value_status(row) == "VALUE_NEGATIVE":
        tags.append("VALUE_NEGATIVE")
    if vd is not None and vd <= NEGATIVE_VALUE_HARD_PP:
        tags.append("NEGATIVE_VALUE_HARD")
    if ev is not None and ev <= NEGATIVE_EV_HARD_PCT:
        tags.append("NEGATIVE_EV_HARD")
    if odds is not None and odds < SHORT_PRICE_LIMIT:
        tags.append("SHORT_PRICE")
    if market_against_pick(row):
        tags.append("MARKET_AGAINST_PICK")
    if odds is not None and odds >= LONG_ODDS_LIMIT:
        tags.append("LONG_ODDS_VALUE_RISK")
    if data_depth(row) < 0.45 or form_depth(row) < 0.40 or thinq_confidence(row) < 0.50:
        tags.append("LOW_DATA_CONFIDENCE")
    return list(dict.fromkeys(tags))


def cloq_score(row: Dict[str, Any]) -> float:
    vd = value_delta_pp(row)
    ev = expected_value_pct(row)
    cp = corq_probability(row) or 0.0
    edge = max(thinq_edge(row), 0.0)
    depth = data_depth(row)
    fdepth = form_depth(row)
    conf = thinq_confidence(row)
    close_bonus, _ = close_odds_bonus(row)

    score = 0.0
    if vd is not None:
        # Cap upside so extreme underdog prices do not dominate CloQ only by math.
        score += max(min(vd, VALUE_DELTA_SCORE_CAP_PP), -10.0) * 2.2
    if ev is not None:
        score += max(min(ev, EXPECTED_VALUE_SCORE_CAP_PCT), -20.0) * 0.35
    score += close_bonus
    score += max(cp - 0.50, 0.0) * 26.0
    score += max(cp - MIN_CLOQ_MODEL_PROBABILITY, 0.0) * 8.0
    score += edge * 20.0
    score += depth * 4.0
    score += fdepth * 2.0
    score += conf * 1.5

    if market_with_pick(row):
        score += 2.0
    if market_against_pick(row):
        score -= 5.0

    risks = cloq_risk_tags(row)
    score -= 1.0 * len(risks)
    if "NEGATIVE_VALUE_HARD" in risks:
        score -= 4.0
    if "NEGATIVE_EV_HARD" in risks:
        score -= 3.0
    if "SHORT_PRICE" in risks and "VALUE_NEGATIVE" in risks:
        score -= 3.0
    if "LONG_ODDS_VALUE_RISK" in risks:
        score -= 4.0
    return round(score, 4)


def annotate_cloq(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    bonus, bucket = close_odds_bonus(row)
    reasons = cloq_reject_reasons(row)
    out["cloq_model_version"] = "CLOQ_VALUE_FIRST_V2"
    out["cloq_pick"] = pick_name(row)
    out["cloq_opponent"] = opponent_name(row)
    out["cloq_pick_odds"] = pick_odds(row)
    out["cloq_opponent_odds"] = opponent_odds(row)
    out["cloq_corq_probability"] = corq_probability(row)
    out["cloq_break_even_probability"] = break_even_probability(row)
    out["cloq_value_delta_pp"] = value_delta_pp(row)
    out["cloq_expected_value_pct"] = expected_value_pct(row)
    out["cloq_value_status"] = value_status(row)
    out["cloq_odds_gap_pct"] = odds_gap_pct(row)
    out["cloq_odds_gap_bucket"] = bucket
    out["cloq_close_bonus"] = bonus
    out["cloq_support_tags"] = cloq_support_tags(row)
    out["cloq_risk_tags"] = cloq_risk_tags(row)
    out["cloq_reject_reasons"] = reasons
    out["cloq_publishable"] = not reasons
    out["cloq_score"] = cloq_score(row) if not reasons else -9999.0
    return out


def match_identity(row: Dict[str, Any]) -> str:
    return str(first_present(row, "match_key", "event_id", "match_id", "id") or "|".join(sorted([pick_name(row).lower(), opponent_name(row).lower()])))
