"""CloQ High-Confidence Price model.

Concept:
- Find the highest available price that still looks like a realistic 50/50+ pick.
- Prefer odds >= 1.90, but reject blind underdogs.
- Require prediction data and objective supporting evidence such as ELO, H2H,
  surface/form, opponent weakness, market support, or high data depth.
- Value is still shown, but the model is driven by price + probability + evidence.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

MODEL_VERSION = "CLOQ_HIGH_CONFIDENCE_PRICE_V2"
MIN_PICK_ODDS = 1.70
PREFERRED_PICK_ODDS = 1.90
MAX_PICK_ODDS = 2.80
MIN_REALISTIC_PROBABILITY = 0.50

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
    p = pick_odds(row)
    o = opponent_odds(row)
    if not p or not o:
        return None
    base = min(p, o)
    if base <= 0:
        return None
    return round(abs(p - o) / base, 6)


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
    text = market_text(row)
    return "market with pick" in text or "with pick" in text


def market_against_pick(row: Dict[str, Any]) -> bool:
    text = market_text(row)
    return "market against pick" in text or "against pick" in text


def _edge(row: Dict[str, Any], *keys: str) -> Optional[float]:
    vals = [as_float(first_present(row, key), None) for key in keys]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    # If probabilities/ratios are 0-1, convert to pp-like scale for scoring.
    v = max(vals, key=lambda x: abs(x))
    if abs(v) <= 1.0:
        v *= 100.0
    return v


def elo_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "elo_edge", "pick_elo_edge", "overall_elo_edge", "surface_elo_edge", "elo_delta", "elo_diff")


def h2h_edge(row: Dict[str, Any]) -> Optional[float]:
    explicit = _edge(row, "h2h_edge", "h2h_pick_edge", "h2h_win_edge", "h2h_delta")
    if explicit is not None:
        return explicit
    pick_w = as_float(first_present(row, "h2h_pick_wins", "pick_h2h_wins", "h2h.wins"), None)
    opp_w = as_float(first_present(row, "h2h_opp_wins", "h2h_opponent_wins", "opp_h2h_wins", "h2h.losses"), None)
    if pick_w is not None and opp_w is not None:
        return pick_w - opp_w
    return None


def form_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "recent_form_edge", "short_form_edge", "form_edge", "l10_edge", "opponent_quality_edge")


def surface_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "surface_recent_form_edge", "surface_edge", "surface_elo_edge", "surface_form_edge")


def data_depth(row: Dict[str, Any]) -> float:
    vals = [
        as_float(first_present(row, "combined_data_depth", "top7_combined_data_depth", "data_depth"), None),
        as_float(first_present(row, "pick_data_depth", "top7_pick_data_depth"), None),
        as_float(first_present(row, "thinq_data_confidence", "top7_thinq_confidence", "confidence"), None),
    ]
    vals = [v for v in vals if v is not None]
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    if avg > 1.5:
        avg /= 100.0
    return max(0.0, min(1.0, avg))


def _tag_blob(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("tags", "audit_tags", "public_notes", "technical_flags", "corq_warning_flags", "top7_risk_tags", "top7_support_tags"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            parts.append(value)
    parts.append(market_text(row))
    return " | ".join(parts).lower().replace("_", " ")


def _has(row: Dict[str, Any], *tokens: str) -> bool:
    text = _tag_blob(row)
    return any(tok.lower() in text for tok in tokens)


def evidence_score(row: Dict[str, Any]) -> float:
    score = 0.0
    details = evidence_details(row)
    for item in details:
        score += float(item.get("points") or 0.0)
    return round(score, 3)


def evidence_details(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    ee = elo_edge(row)
    he = h2h_edge(row)
    fe = form_edge(row)
    se = surface_edge(row)
    depth = data_depth(row)

    if ee is not None:
        if ee >= 35: details.append({"tag": "ELO_STRONG", "points": 3.0, "value": ee})
        elif ee >= 15: details.append({"tag": "ELO_EDGE", "points": 1.5, "value": ee})
        elif ee <= -35: details.append({"tag": "ELO_AGAINST", "points": -3.0, "value": ee})
        elif ee <= -15: details.append({"tag": "ELO_WEAK", "points": -1.5, "value": ee})
    if he is not None:
        if he >= 2: details.append({"tag": "H2H_STRONG", "points": 3.0, "value": he})
        elif he > 0: details.append({"tag": "H2H_EDGE", "points": 1.5, "value": he})
        elif he <= -2: details.append({"tag": "H2H_AGAINST", "points": -3.0, "value": he})
        elif he < 0: details.append({"tag": "H2H_WEAK", "points": -1.5, "value": he})
    if fe is not None:
        if fe >= 15: details.append({"tag": "FORM_STRONG", "points": 2.0, "value": fe})
        elif fe > 0: details.append({"tag": "FORM_EDGE", "points": 1.0, "value": fe})
        elif fe <= -15: details.append({"tag": "FORM_AGAINST", "points": -2.0, "value": fe})
    if se is not None:
        if se >= 15: details.append({"tag": "SURFACE_STRONG", "points": 2.0, "value": se})
        elif se > 0: details.append({"tag": "SURFACE_EDGE", "points": 1.0, "value": se})
        elif se <= -15: details.append({"tag": "SURFACE_AGAINST", "points": -2.0, "value": se})

    if _has(row, "pick strong"):
        details.append({"tag": "PICK_STRONG", "points": 2.0})
    if _has(row, "opp weak", "opponent weak"):
        details.append({"tag": "OPP_WEAK", "points": 2.0})
    if market_with_pick(row):
        details.append({"tag": "MARKET_WITH_PICK", "points": 2.0})
    if market_against_pick(row):
        details.append({"tag": "MARKET_AGAINST_PICK", "points": -3.0})
    if _has(row, "opp strong", "opponent strong"):
        details.append({"tag": "OPP_STRONG", "points": -3.0})
    if _has(row, "pick weak"):
        details.append({"tag": "PICK_WEAK", "points": -3.0})
    if depth >= 0.70:
        details.append({"tag": "HIGH_DATA_DEPTH", "points": 1.5, "value": round(depth, 3)})
    elif depth and depth < 0.35:
        details.append({"tag": "LOW_DATA_DEPTH", "points": -2.0, "value": round(depth, 3)})
    return details


def price_bucket(row: Dict[str, Any]) -> str:
    odds = pick_odds(row) or 0.0
    if odds >= 2.40:
        return "HIGH_PRICE_2_40_PLUS"
    if odds >= 2.10:
        return "VALUE_PRICE_2_10_2_39"
    if odds >= 1.90:
        return "TARGET_PRICE_1_90_2_09"
    if odds >= 1.70:
        return "FALLBACK_PRICE_1_70_1_89"
    return "TOO_LOW"


def required_evidence(row: Dict[str, Any]) -> float:
    odds = pick_odds(row) or 0.0
    if odds >= 2.40:
        return 7.0
    if odds >= 2.10:
        return 5.0
    if odds >= 1.90:
        return 3.0
    return 2.0


def probability_margin_pp(row: Dict[str, Any]) -> Optional[float]:
    cp = corq_probability(row)
    be = break_even_probability(row)
    if cp is None or be is None:
        return None
    return round((cp - be) * 100.0, 4)


def cloq_reject_reasons(row: Dict[str, Any]) -> List[str]:
    """Hard gate only on objective availability/basic realism.

    V1 was too strict because it rejected candidates when evidence fields were
    absent or named differently in upstream data. V2 keeps only hard blockers as
    rejects and moves evidence weakness into risk tags and score penalties. This
    lets CloQ still rank 7 daily candidates from the available pool.
    """
    reasons: List[str] = []
    odds = pick_odds(row)
    cp = corq_probability(row)
    evs = evidence_score(row)

    if not is_prematch(row):
        reasons.append("REJECT_CLOQ_STATUS_NOT_PREMATCH")
    if is_doubles(row):
        reasons.append("REJECT_CLOQ_DOUBLES")
    if odds is None:
        reasons.append("REJECT_CLOQ_MISSING_PICK_ODDS")
    elif odds < MIN_PICK_ODDS:
        reasons.append("REJECT_CLOQ_ODDS_UNDER_1_70")
    elif odds > MAX_PICK_ODDS and evs < 5.0:
        reasons.append("REJECT_CLOQ_PRICE_TOO_HIGH_WITHOUT_EVIDENCE")
    if cp is None:
        reasons.append("REJECT_CLOQ_MISSING_PREDICTION_DATA")
    elif cp < MIN_REALISTIC_PROBABILITY:
        reasons.append("REJECT_CLOQ_MODEL_PROB_UNDER_50")
    return list(dict.fromkeys(reasons))


def cloq_support_tags(row: Dict[str, Any]) -> List[str]:
    tags = [price_bucket(row)]
    margin = probability_margin_pp(row)
    if margin is not None:
        if margin >= 4.0:
            tags.append("PROBABILITY_BUFFER_STRONG")
        elif margin >= 0.0:
            tags.append("PROBABILITY_OVER_BREAK_EVEN")
    for item in evidence_details(row):
        if float(item.get("points") or 0.0) > 0:
            tags.append(str(item.get("tag")))
    return list(dict.fromkeys(tags))


def cloq_risk_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    margin = probability_margin_pp(row)
    evs = evidence_score(row)
    req = required_evidence(row)
    if margin is not None and margin < 0:
        tags.append("PROBABILITY_UNDER_BREAK_EVEN_INFO")
    if evs < req:
        tags.append("INSUFFICIENT_EVIDENCE_INFO")
    if pick_odds(row) and pick_odds(row) >= 2.40:
        tags.append("HIGH_PRICE_RISK")
    for item in evidence_details(row):
        if float(item.get("points") or 0.0) < 0:
            tags.append(str(item.get("tag")))
    return list(dict.fromkeys(tags))


def cloq_decision(row: Dict[str, Any]) -> str:
    reasons = cloq_reject_reasons(row)
    if reasons:
        return "CLOQ_REJECTED"
    odds = pick_odds(row) or 0.0
    if odds >= PREFERRED_PICK_ODDS:
        return "CLOQ_HIGH_CONFIDENCE_PRICE"
    return "CLOQ_PRICE_FALLBACK"


def cloq_score(row: Dict[str, Any]) -> float:
    odds = pick_odds(row) or 0.0
    cp = corq_probability(row) or 0.0
    margin = probability_margin_pp(row)
    margin = margin if margin is not None else -8.0
    evs = evidence_score(row)
    depth = data_depth(row)

    # Price sweet spot: reward 1.90-2.30 most, allow 1.70-1.89 as fallback.
    if odds >= 2.40:
        price_points = 5.0
    elif odds >= 2.10:
        price_points = 7.0
    elif odds >= 1.90:
        price_points = 6.0
    elif odds >= 1.70:
        price_points = 2.0
    else:
        price_points = -20.0

    score = 0.0
    score += price_points
    score += max(min(margin, 12.0), -8.0) * 1.4
    score += evs * 2.0
    shortfall = max(0.0, required_evidence(row) - evs)
    score -= shortfall * 3.0
    score += cp * 20.0
    score += depth * 4.0
    if market_with_pick(row):
        score += 3.0
    if market_against_pick(row):
        score -= 5.0
    if odds > MAX_PICK_ODDS:
        score -= (odds - MAX_PICK_ODDS) * 8.0
    return round(score, 4)


def annotate_cloq(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    reasons = cloq_reject_reasons(row)
    out["cloq_model_version"] = MODEL_VERSION
    out["cloq_policy"] = "highest_realistic_price_50_50_plus_evidence_scored_not_hard_rejected"
    out["cloq_pick"] = pick_name(row)
    out["cloq_opponent"] = opponent_name(row)
    out["cloq_pick_odds"] = pick_odds(row)
    out["cloq_opponent_odds"] = opponent_odds(row)
    out["cloq_corq_probability"] = corq_probability(row)
    out["cloq_break_even_probability"] = break_even_probability(row)
    out["cloq_probability_margin_pp"] = probability_margin_pp(row)
    out["cloq_value_delta_pp"] = value_delta_pp(row)
    out["cloq_expected_value_pct"] = expected_value_pct(row)
    out["cloq_evidence_score"] = evidence_score(row)
    out["cloq_required_evidence_score"] = required_evidence(row)
    out["cloq_evidence_details"] = evidence_details(row)
    out["cloq_price_bucket"] = price_bucket(row)
    out["cloq_data_depth"] = data_depth(row)
    out["cloq_decision"] = cloq_decision(row)
    out["cloq_support_tags"] = cloq_support_tags(row)
    out["cloq_risk_tags"] = cloq_risk_tags(row)
    out["cloq_reject_reasons"] = reasons
    out["cloq_publishable"] = not reasons
    out["cloq_score"] = cloq_score(row) if not reasons else -9999.0
    return out


def match_identity(row: Dict[str, Any]) -> str:
    return str(first_present(row, "match_key", "event_id", "match_id", "id") or "".join(sorted([pick_name(row).lower(), opponent_name(row).lower()])))
