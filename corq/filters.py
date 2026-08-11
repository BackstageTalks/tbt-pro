"""CloQ High-Odds Data-Covered filters.

Model intent:
- Find players with odds >= 1.70 that still look like realistic winner candidates.
- Avoid random underdogs, coin-flips with no data, and missing-data selections.
- Use ThinQ + MarQ + data depth + support evidence to decide whether a higher price is data-covered.

Important project rule:
- Do not synthesize missing odds, probabilities, player names, or evidence.
- If required data is missing, expose it through cloq_reject_reasons / audit fields.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

MODEL_VERSION = "CLOQ_HIGH_ODDS_DATA_COVERED_V5_AUDIT_CLEANUP"
MIN_PICK_ODDS = 1.70
MAX_PICK_ODDS = 2.50

ODDS_BANDS = (
    (1.70, 1.90, "PRIME_1_70_1_90", 0.505, 0.45, -6.0, 0),
    (1.90, 2.20, "EXTENDED_1_90_2_20", 0.515, 0.50, -5.0, 1),
    (2.20, 2.50, "HIGH_VARIANCE_2_20_2_50", 0.530, 0.55, -3.0, 2),
)

OPEN_STATUS_TYPES = {"", "notstarted", "not_started", "scheduled", "open", "prematch", "pre-match", "upcoming", "pending"}
BLOCKED_STATUS_TYPES = {"finished", "ended", "complete", "completed", "inprogress", "in_progress", "live", "started", "cancelled", "canceled", "postponed", "retired", "walkover", "interrupted", "suspended", "abandoned"}
MISSING_VALUES = {None, "", "—", "-", "N/A", "NA", "None", "none", "null"}


def is_missing_value(value: Any) -> bool:
    """Return True for configured missing sentinels without crashing on dict/list values."""
    try:
        return value in MISSING_VALUES
    except TypeError:
        return False


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if is_missing_value(value):
            return default
        return float(str(value).strip().replace("%", "").replace(",", "."))
    except Exception:
        return default


def probability(value: Any, default: Optional[float] = None) -> Optional[float]:
    number = as_float(value, None)
    if number is None:
        return default
    if number > 1.5:
        number /= 100.0
    return number if 0.0 <= number <= 1.0 else default


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
            if ok and not is_missing_value(cur):
                return cur
        else:
            value = row.get(key)
            if not is_missing_value(value):
                return value
    return None


def pick_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "pick", "top7_pick", "corq_pick", "cloq_pick", "selected_pick", "selection", "selected_player", "predicted_winner", "winner_pick", "player", "player1", "home", "prediction_snapshot.corq.pick") or "").strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(first_present(row, "opponent", "opp", "player2", "away", "top7_opponent", "corq_opponent", "cloq_opponent", "prediction_snapshot.corq.opponent") or "").strip()


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    return as_float(first_present(row, "top7_pick_odds", "pick_odds", "corq_pick_odds", "cloq_pick_odds", "selected_pick_odds", "selected_odds", "market_odds", "closing_odds", "current_odds", "decimal_odds", "odds", "odds_decimal", "prediction_snapshot.corq.odds"), None)


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    return as_float(first_present(row, "opponent_odds", "opp_odds", "top7_opponent_odds", "corq_opponent_odds", "cloq_opponent_odds", "opponent_price", "opp_price", "away_odds", "prediction_snapshot.corq.opponent_odds"), None)


def corq_probability(row: Dict[str, Any]) -> Optional[float]:
    return probability(first_present(row, "top7_corq_probability", "top7_pick_probability", "corq_final_probability", "corq_final", "corq_probability", "corq_calibrated_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "pick_probability", "predicted_probability", "probability", "prediction_snapshot.corq.calibrated_probability", "prediction_snapshot.corq.probability"), None)


def thinq_probability(row: Dict[str, Any]) -> Optional[float]:
    return probability(first_present(row, "thinq_probability", "thinq_prob", "thinq_pick_probability", "top7_thinq_probability", "thinq_final", "thinq_model_probability", "thinq_win_probability", "prediction_snapshot.thinq.probability", "prediction_snapshot.corq.thinq_probability"), None)


def primary_probability(row: Dict[str, Any]) -> Optional[float]:
    tp = thinq_probability(row)
    return tp if tp is not None else corq_probability(row)


def marq_probability(row: Dict[str, Any]) -> Optional[float]:
    return probability(first_present(row, "marq_probability", "marq_prob", "marq_pick_probability", "pick_marq_probability", "marq_crowd_pick_pct", "marq_no_vig_probability", "marq_pick_no_vig_probability", "marq_v2_market_probability", "corq_market_probability", "top7_marq_probability", "cloq_marq_probability", "prediction_snapshot.marq.probability", "prediction_snapshot.corq.marq_probability"), None)


def break_even_probability(row: Dict[str, Any]) -> Optional[float]:
    odds = pick_odds(row)
    return None if odds is None or odds <= 0 else 1.0 / odds


def probability_margin_pp(row: Dict[str, Any]) -> Optional[float]:
    model_p = primary_probability(row)
    be = break_even_probability(row)
    if model_p is None or be is None:
        return None
    return round((model_p - be) * 100.0, 4)


def value_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(first_present(row, "corq_value_delta_pp", "value_delta_pp", "cloq_value_delta_pp", "marq_v2_value_delta_pp"), None)
    if explicit is not None:
        return explicit
    cp = corq_probability(row)
    be = break_even_probability(row)
    if cp is None or be is None:
        return None
    return round((cp - be) * 100.0, 4)


def expected_value_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(first_present(row, "expected_value_pct", "ev_pct", "cloq_expected_value_pct", "marq_v2_expected_value_pct"), None)
    if explicit is not None:
        return explicit
    cp = corq_probability(row)
    odds = pick_odds(row)
    if cp is None or odds is None:
        return None
    return round((cp * odds - 1.0) * 100.0, 4)


def status_type(row: Dict[str, Any]) -> str:
    raw = first_present(row, "status_type", "match_status_type", "status")
    raw_obj = row.get("raw")
    if not raw and isinstance(raw_obj, dict):
        raw_status = raw_obj.get("status")
        if isinstance(raw_status, dict):
            raw = raw_status.get("type") or raw_status.get("description")
    return str(raw or "").strip().lower().replace(" ", "_")


def status_code(row: Dict[str, Any]) -> Optional[int]:
    value = first_present(row, "status_code", "match_status_code")
    raw_obj = row.get("raw")
    if value is None and isinstance(raw_obj, dict):
        raw_status = raw_obj.get("status")
        if isinstance(raw_status, dict):
            value = raw_status.get("code")
    try:
        return int(float(value)) if value not in MISSING_VALUES else None
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
    return " | ".join(str(first_present(row, key) or "") for key in ("marq_final", "marq_final_display", "final_marq", "market_final", "marq_market_final", "market_read", "marq_signal", "marq_v2_signal")).lower().replace("_", " ")


def market_with_pick(row: Dict[str, Any]) -> bool:
    text = market_text(row)
    return "market with pick" in text or "with pick" in text


def market_against_pick(row: Dict[str, Any]) -> bool:
    text = market_text(row)
    return "market against pick" in text or "against pick" in text


def market_neutral(row: Dict[str, Any]) -> bool:
    text = market_text(row)
    return "neutral" in text or "fair" in text


def _edge(row: Dict[str, Any], *keys: str) -> Optional[float]:
    vals = [as_float(first_present(row, key), None) for key in keys]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    v = max(vals, key=lambda x: abs(x))
    if abs(v) <= 1.0:
        v *= 100.0
    return v


def elo_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "elo_edge", "pick_elo_edge", "overall_elo_edge", "surface_elo_edge", "elo_delta", "elo_diff")


def h2h_edge(row: Dict[str, Any]) -> Optional[float]:
    explicit = _edge(row, "h2h_edge", "h2h_pick_edge", "h2h_win_edge", "h2h_delta", "p_h2h_edge")
    if explicit is not None:
        return explicit
    pick_w = as_float(first_present(row, "h2h_pick_wins", "pick_h2h_wins", "h2h.wins"), None)
    opp_w = as_float(first_present(row, "h2h_opp_wins", "h2h_opponent_wins", "opp_h2h_wins", "h2h.losses"), None)
    if pick_w is not None and opp_w is not None:
        return pick_w - opp_w
    return None


def form_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "recent_form_edge", "short_form_edge", "form_edge", "l10_edge", "opponent_quality_edge", "p_form_edge")


def surface_edge(row: Dict[str, Any]) -> Optional[float]:
    return _edge(row, "surface_recent_form_edge", "surface_edge", "surface_elo_edge", "surface_form_edge", "p_surface_edge")


def data_depth(row: Dict[str, Any]) -> float:
    vals = [
        as_float(first_present(row, "combined_data_depth", "top7_combined_data_depth", "data_depth", "cloq_data_depth"), None),
        as_float(first_present(row, "pick_data_depth", "top7_pick_data_depth", "s_data_depth"), None),
        as_float(first_present(row, "thinq_data_confidence", "top7_thinq_confidence", "confidence", "thinq_confidence"), None),
        as_float(first_present(row, "form_data_depth", "f_data_depth"), None),
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
    for key in ("tags", "audit_tags", "public_notes", "technical_flags", "corq_warning_flags", "top7_risk_tags", "top7_support_tags", "risk_tags", "support_tags", "cloq_support_tags"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            parts.append(value)
    parts.append(market_text(row))
    return "  ".join(parts).lower().replace("_", " ")


def _has(row: Dict[str, Any], *tokens: str) -> bool:
    text = _tag_blob(row)
    return any(tok.lower() in text for tok in tokens)


def price_bucket(row: Dict[str, Any]) -> str:
    odds = pick_odds(row) or 0.0
    for lo, hi, name, *_ in ODDS_BANDS:
        if lo <= odds < hi or (abs(odds - MAX_PICK_ODDS) < 1e-9 and hi == MAX_PICK_ODDS):
            return name
    if odds < MIN_PICK_ODDS:
        return "TOO_LOW"
    return "TOO_HIGH"


def band_thresholds(row: Dict[str, Any]) -> Dict[str, Any]:
    odds = pick_odds(row) or 0.0
    for lo, hi, name, min_primary, min_depth, min_gap, min_support in ODDS_BANDS:
        if lo <= odds < hi or (abs(odds - MAX_PICK_ODDS) < 1e-9 and hi == MAX_PICK_ODDS):
            return {"bucket": name, "min_primary": min_primary, "min_depth": min_depth, "min_gap_pp": min_gap, "min_support_tags": min_support}
    return {"bucket": "OUT_OF_RANGE", "min_primary": 1.0, "min_depth": 1.0, "min_gap_pp": 999.0, "min_support_tags": 99}


def evidence_details(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    def add(tag: str, points: float, value: Any = None) -> None:
        details.append({"tag": tag, "points": round(points, 3), "value": value})

    pp = primary_probability(row)
    mp = marq_probability(row)
    ee = elo_edge(row)
    he = h2h_edge(row)
    fe = form_edge(row)
    se = surface_edge(row)
    depth = data_depth(row)

    if pp is not None:
        if pp >= 0.58:
            add("MODEL_STRONG_SUPPORT", 3.0, round(pp, 4))
        elif pp >= 0.54:
            add("MODEL_SUPPORT", 2.0, round(pp, 4))
        elif pp >= 0.50:
            add("MODEL_LIGHT_SUPPORT", 1.0, round(pp, 4))
        else:
            add("MODEL_AGAINST", -4.0, round(pp, 4))
    if mp is not None:
        if mp >= 0.58:
            add("MARQ_STRONG_SUPPORT", 2.0, round(mp, 4))
        elif mp >= 0.52:
            add("MARQ_SUPPORT", 1.2, round(mp, 4))
        elif mp >= 0.50:
            add("MARQ_LIGHT_SUPPORT", 0.6, round(mp, 4))
        elif mp < 0.47:
            add("MARQ_AGAINST", -2.5, round(mp, 4))

    for value, tag_pos, tag_light, tag_neg, strong, light, neg, pts in [
        (ee, "ELO_SUPPORT", "ELO_LIGHT_SUPPORT", "ELO_AGAINST", 5, 2, -5, 2.0),
        (he, "H2H_SUPPORT", "H2H_LIGHT_SUPPORT", "H2H_AGAINST", 2, 0.1, -2, 1.7),
        (fe, "FORM_SUPPORT", "FORM_LIGHT_SUPPORT", "FORM_AGAINST", 3, 0.1, -3, 1.5),
        (se, "SURFACE_SUPPORT", "SURFACE_LIGHT_SUPPORT", "SURFACE_AGAINST", 3, 0.1, -3, 1.2),
    ]:
        if value is None:
            continue
        if value >= strong:
            add(tag_pos, pts, value)
        elif value > light:
            add(tag_light, pts * 0.45, value)
        elif value <= neg:
            add(tag_neg, -pts, value)

    if market_with_pick(row):
        add("MARKET_WITH_PICK", 1.2, None)
    elif market_neutral(row):
        add("MARKET_NEUTRAL", 0.6, None)
    elif market_against_pick(row):
        add("MARKET_AGAINST_PICK", -2.5, None)

    if _has(row, "pick strong", "pick_strong"):
        add("PICK_STRONG", 1.2, None)
    if _has(row, "opp weak", "opponent weak", "opp_weak"):
        add("OPP_WEAK", 1.2, None)
    if _has(row, "opp strong", "opponent strong", "opp_strong"):
        add("OPP_STRONG", -2.0, None)
    if _has(row, "pick weak", "pick_weak"):
        add("PICK_WEAK", -2.0, None)

    if depth >= 0.75:
        add("DATA_COVERED_STRONG", 1.8, round(depth, 4))
    elif depth >= 0.50:
        add("DATA_COVERED", 1.0, round(depth, 4))
    elif depth > 0:
        add("LOW_DATA_DEPTH", -2.5, round(depth, 4))
    return details


def evidence_score(row: Dict[str, Any]) -> float:
    return round(sum(float(item.get("points") or 0.0) for item in evidence_details(row)), 3)


def support_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = [price_bucket(row)]
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


def risk_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    margin = probability_margin_pp(row)
    if margin is not None and margin < 0:
        tags.append("PROBABILITY_UNDER_BREAK_EVEN_INFO")
    if pick_odds(row) and pick_odds(row) >= 2.20:
        tags.append("HIGH_VARIANCE_PRICE_BAND")
    for item in evidence_details(row):
        if float(item.get("points") or 0.0) < 0:
            tags.append(str(item.get("tag")))
    return list(dict.fromkeys(tags))


def cloq_reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    pick = pick_name(row)
    opp = opponent_name(row)
    odds = pick_odds(row)
    opp_odds = opponent_odds(row)
    pp = primary_probability(row)
    tp = thinq_probability(row)
    cp = corq_probability(row)
    mp = marq_probability(row)
    depth = data_depth(row)
    thresholds = band_thresholds(row)
    margin = probability_margin_pp(row)
    supports = support_tags(row)
    positive_support_count = len([tag for tag in supports if tag not in {"TOO_LOW", "TOO_HIGH", "OUT_OF_RANGE"}])

    if not pick or pick == "—":
        reasons.append("CLOQ_REJECT_MISSING_PICK")
    if not opp or opp == "—":
        reasons.append("CLOQ_REJECT_MISSING_OPPONENT")
    if not is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if is_doubles(row):
        reasons.append("CLOQ_REJECT_DOUBLES")
    odds_out_of_cloq_range = False
    if odds is None:
        reasons.append("CLOQ_REJECT_MISSING_PICK_ODDS")
        odds_out_of_cloq_range = True
    elif odds < MIN_PICK_ODDS:
        reasons.append("CLOQ_REJECT_ODDS_UNDER_1_70")
        odds_out_of_cloq_range = True
    elif odds > MAX_PICK_ODDS:
        reasons.append("CLOQ_REJECT_ODDS_OVER_2_50")
        odds_out_of_cloq_range = True

    # Audit cleanup: when the price is outside the CloQ model range, do not add
    # secondary threshold/support/depth blockers based on an out-of-range band.
    # The row is already non-publishable for the decisive reason above.
    if odds_out_of_cloq_range:
        return list(dict.fromkeys(reasons))

    if pp is None:
        reasons.append("CLOQ_REJECT_MISSING_PREDICTION_DATA")
    elif pp < 0.50:
        reasons.append("CLOQ_REJECT_MODEL_BELOW_50")
    elif pp < thresholds["min_primary"]:
        reasons.append("CLOQ_REJECT_MODEL_BELOW_BAND_MINIMUM")

    if cp is None:
        reasons.append("CLOQ_REJECT_MISSING_CORQ_PROBABILITY")
    if tp is None:
        reasons.append("CLOQ_INFO_MISSING_THINQ")

    has_market_read = market_with_pick(row) or market_neutral(row) or market_against_pick(row)
    if mp is None and not has_market_read:
        reasons.append("CLOQ_INFO_MISSING_MARQ")

    if depth <= 0:
        reasons.append("CLOQ_REJECT_MISSING_DATA_DEPTH")
    elif depth < thresholds["min_depth"]:
        # For prime band, allow 45-50 only if model + market/evidence are not weak.
        if not (price_bucket(row) == "PRIME_1_70_1_90" and depth >= 0.45 and pp is not None and pp >= 0.54 and positive_support_count >= 1):
            reasons.append("CLOQ_REJECT_LOW_DATA_DEPTH")

    if margin is None:
        reasons.append("CLOQ_INFO_MISSING_MODEL_GAP")
    elif margin < thresholds["min_gap_pp"]:
        # Model gap is a hard blocker only for high variance band. Below that it remains a quality/risk signal.
        if price_bucket(row) == "HIGH_VARIANCE_2_20_2_50":
            reasons.append("CLOQ_REJECT_MODEL_GAP_TOO_NEGATIVE")

    if positive_support_count < int(thresholds["min_support_tags"]):
        if not (price_bucket(row) == "PRIME_1_70_1_90" and pp is not None and pp >= 0.55 and depth >= 0.50):
            reasons.append("CLOQ_REJECT_NOT_ENOUGH_SUPPORT_TAGS")

    if odds is not None and opp_odds is not None and odds >= opp_odds:
        # Higher-priced pick is allowed only when the model has positive support,
        # enough data depth and at least one positive support tag. MarQ against is
        # a risk/info signal when the model is still above the protected floor.
        if pp is None or pp < 0.52 or depth < 0.50 or positive_support_count < 1:
            reasons.append("CLOQ_REJECT_RANDOM_UNDERDOG")
        if mp is not None and mp < 0.50 and not market_with_pick(row):
            if pp is None or pp < 0.52:
                reasons.append("CLOQ_REJECT_UNDERDOG_MARKET_NOT_SUPPORTIVE")
            else:
                reasons.append("CLOQ_INFO_UNDERDOG_MARKET_NOT_SUPPORTIVE")

    if market_against_pick(row):
        if pp is None or pp < 0.52:
            reasons.append("CLOQ_REJECT_MARKET_AGAINST_WEAK_MODEL")
        else:
            reasons.append("CLOQ_INFO_MARKET_AGAINST_PICK")

    if _has(row, "opp strong", "opponent strong", "opp_strong") and _has(row, "pick weak", "pick_weak"):
        reasons.append("CLOQ_REJECT_OPP_STRONG_PICK_WEAK")

    return list(dict.fromkeys(reasons))


def cloq_decision(row: Dict[str, Any]) -> str:
    reasons = [r for r in cloq_reject_reasons(row) if not r.startswith("CLOQ_INFO_")]
    if reasons:
        return "CLOQ_REJECTED"
    bucket = price_bucket(row)
    if bucket == "PRIME_1_70_1_90":
        return "CLOQ_PRIME"
    if bucket == "EXTENDED_1_90_2_20":
        return "CLOQ_EXTENDED"
    return "CLOQ_HIGH_VARIANCE"


def cloq_score(row: Dict[str, Any]) -> float:
    odds = pick_odds(row) or 0.0
    pp = primary_probability(row) or 0.0
    mp = marq_probability(row)
    cp = corq_probability(row) or 0.0
    depth = data_depth(row)
    margin = probability_margin_pp(row)
    margin = margin if margin is not None else -6.0
    evs = evidence_score(row)
    bucket = price_bucket(row)
    bucket_bonus = {"EXTENDED_1_90_2_20": 12.0, "PRIME_1_70_1_90": 10.0, "HIGH_VARIANCE_2_20_2_50": 7.0}.get(bucket, 0.0)
    price_quality = bucket_bonus + min(max((odds - 1.70) * 4.0, 0.0), 3.0)
    margin_score = max(min(margin * 0.7, 8.0), -9.0)
    evidence_component = max(min(evs * 1.25, 12.0), -12.0)
    marq_component = ((mp if mp is not None else 0.50) - 0.50) * 30.0
    risk_penalty = len([r for r in risk_tags(row) if r in {"OPP_STRONG", "PICK_WEAK", "MARKET_AGAINST_PICK", "LOW_DATA_DEPTH"}]) * 2.5
    if "HIGH_VARIANCE_PRICE_BAND" in risk_tags(row):
        risk_penalty += 1.5
    score = pp * 58.0 + cp * 16.0 + marq_component + depth * 18.0 + price_quality + margin_score + evidence_component - risk_penalty
    return round(score, 4)


def annotate_cloq(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    reasons = cloq_reject_reasons(row)
    hard_reasons = [r for r in reasons if not r.startswith("CLOQ_INFO_")]
    out["cloq_model_version"] = MODEL_VERSION
    out["cloq_policy"] = "odds_1_70_to_2_50_data_covered_primary_model_marq_depth_no_random_underdogs"
    out["cloq_pick"] = pick_name(row)
    out["cloq_opponent"] = opponent_name(row)
    out["cloq_pick_odds"] = pick_odds(row)
    out["cloq_opponent_odds"] = opponent_odds(row)
    out["cloq_primary_probability"] = primary_probability(row)
    out["cloq_thinq_probability"] = thinq_probability(row)
    out["cloq_marq_probability"] = marq_probability(row)
    out["cloq_corq_probability"] = corq_probability(row)
    out["cloq_break_even_probability"] = break_even_probability(row)
    out["cloq_model_gap_pp"] = probability_margin_pp(row)
    out["cloq_value_delta_pp"] = value_delta_pp(row)
    out["cloq_expected_value_pct"] = expected_value_pct(row)
    out["cloq_evidence_score"] = evidence_score(row)
    out["cloq_evidence_details"] = evidence_details(row)
    out["cloq_price_bucket"] = price_bucket(row)
    out["cloq_data_depth"] = data_depth(row)
    out["cloq_thresholds"] = band_thresholds(row)
    out["cloq_decision"] = cloq_decision(row)
    out["cloq_support_tags"] = support_tags(row)
    out["cloq_risk_tags"] = risk_tags(row)
    out["cloq_reject_reasons"] = reasons
    out["cloq_publishable"] = not hard_reasons
    out["cloq_score"] = cloq_score(row) if not hard_reasons else -9999.0
    return out


def match_identity(row: Dict[str, Any]) -> str:
    return str(first_present(row, "match_key", "event_id", "match_id", "id") or "::".join(sorted([pick_name(row).lower(), opponent_name(row).lower()])))
