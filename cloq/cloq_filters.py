"""CloQ filters and scoring.

CloQ = Close Odds Quality.
It is a transparent view/filter over existing CorQ/ThinQ/MarQ predictions.
The goal is to study close-odds segments without changing TOP7 selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math


@dataclass(frozen=True)
class CloQConfig:
    min_odds: float = 1.70
    max_odds: float = 2.60
    min_odd_gap_pct: float = 0.10
    max_odd_gap_pct: float = 0.25
    min_corq_probability: float = 0.55
    min_thinq_probability: float = 0.55
    min_marq_probability: float = 0.50
    min_form_depth: float = 0.60
    min_stats_depth: float = 0.40
    max_mmx_conflict_pp: float = 18.0
    require_prematch: bool = True
    require_singles: bool = True


PREMATCH_STATUS_TYPES = {
    "notstarted", "not_started", "scheduled", "prematch", "pre_match", "upcoming", "pending"
}
BAD_STATUS_TYPES = {
    "inprogress", "in_progress", "live", "finished", "ended", "cancelled", "canceled",
    "postponed", "interrupted", "retired", "walkover", "abandoned"
}


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else default
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if text in {"", "-", "--", "—", "N/A", "n/a", "None", "null"}:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _as_probability(value: Any) -> Optional[float]:
    number = _to_float(value)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    return number if 0.0 <= number <= 1.0 else None


def _first_prob(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        value = _as_probability(row.get(key))
        if value is not None:
            return value
    return None


def _first_float(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


def _nested_get(mapping: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = mapping
    for part in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _status_is_prematch(row: Dict[str, Any]) -> bool:
    status_type = str(row.get("status_type") or row.get("status") or "").strip().lower()
    status_code = row.get("status_code")
    if status_code in (0, "0"):
        return True
    if status_type in PREMATCH_STATUS_TYPES:
        return True
    if status_type in BAD_STATUS_TYPES:
        return False
    return False


def compute_odd_gap_pct(row: Dict[str, Any]) -> Optional[float]:
    pick_odds = _first_float(row, ["pick_odds", "odds", "price", "pick_price"])
    opp_odds = _first_float(row, ["opponent_odds", "opp_odds", "opponent_price"])
    if pick_odds is None or opp_odds is None:
        p1 = _first_float(row, ["p1_odds", "odds_player1", "home_odds", "odds1", "price1"])
        p2 = _first_float(row, ["p2_odds", "odds_player2", "away_odds", "odds2", "price2"])
        pick_side = str(row.get("pick_side") or "").upper()
        if p1 is not None and p2 is not None:
            if pick_side in {"HOME", "PLAYER1", "P1"}:
                pick_odds, opp_odds = p1, p2
            elif pick_side in {"AWAY", "PLAYER2", "P2"}:
                pick_odds, opp_odds = p2, p1
    if pick_odds is None or opp_odds is None or pick_odds <= 1.0 or opp_odds <= 1.0:
        return None
    return abs(pick_odds - opp_odds) / min(pick_odds, opp_odds)


def _marq_prob(row: Dict[str, Any]) -> Optional[float]:
    value = _first_prob(row, [
        "corq_market_probability", "marq_pick_probability", "marq_probability", "pick_marq_probability",
        "pick_marq_pct", "marq_pick_pct", "pick_marq"
    ])
    if value is not None:
        return value
    marq = row.get("marq")
    if isinstance(marq, dict):
        for key in ["pick_probability", "pick_marq_probability", "pick_marq_pct", "pick_marq"]:
            value = _as_probability(marq.get(key))
            if value is not None:
                return value
    return None


def _thinq_prob(row: Dict[str, Any]) -> Optional[float]:
    value = _first_prob(row, [
        "thinq_pick_probability", "thinq_probability", "thinq_prob", "pick_thinq_probability",
        "corq_raw_model_probability"
    ])
    if value is not None:
        return value
    return _as_probability(_nested_get(row, ["thinq", "thinq_probability_layer", "pick_probability"]))


def _corq_prob(row: Dict[str, Any]) -> Optional[float]:
    return _first_prob(row, [
        "corq_calibrated_probability", "corq_probability", "corq", "probability", "estimated_probability"
    ])


def _form_depth(row: Dict[str, Any]) -> Optional[float]:
    return _first_prob(row, ["form_data_depth", "f_data_depth", "thinq_form_data_depth"])


def _stats_depth(row: Dict[str, Any]) -> Optional[float]:
    return _first_prob(row, ["s_data_depth", "sets_games_data_depth", "stats_data_depth"])


def _move_quality(row: Dict[str, Any]) -> Tuple[float, List[str]]:
    tags: List[str] = []
    move = str(row.get("marq_internal_move_signal") or row.get("marq_move_signal") or row.get("move") or "").strip().lower()
    clv_status = str(row.get("marq_internal_clv_status") or row.get("clv_status") or "").strip().lower()
    clv_pp = _to_float(row.get("marq_internal_clv_pp"), None)
    quality = 0.50
    if "toward" in move or "with" in move:
        quality += 0.20
        tags.append("Positive Move")
    elif "against" in move:
        quality -= 0.25
        tags.append("Move Against")
    elif "stable" in move:
        tags.append("Stable Move")
    elif "pending" in move or not move:
        tags.append("CLV Pending")
    if clv_pp is not None:
        if clv_pp >= 2.0:
            quality += 0.15
            tags.append("Positive CLV")
        elif clv_pp <= -2.0:
            quality -= 0.20
            tags.append("Negative CLV")
        else:
            tags.append("Flat CLV")
    elif "pending" in clv_status or not clv_status:
        tags.append("CLV Pending")
    return max(0.0, min(1.0, quality)), tags


def score_cloq_row(row: Dict[str, Any], config: CloQConfig = CloQConfig()) -> float:
    corq = _corq_prob(row) or 0.50
    thinq = _thinq_prob(row) or 0.50
    marq = _marq_prob(row) or 0.50
    f_depth = _form_depth(row) or 0.0
    s_depth = _stats_depth(row) or 0.0
    odd_gap = compute_odd_gap_pct(row)
    if odd_gap is None:
        gap_quality = 0.0
    else:
        center = (config.min_odd_gap_pct + config.max_odd_gap_pct) / 2.0
        span = max((config.max_odd_gap_pct - config.min_odd_gap_pct) / 2.0, 0.01)
        gap_quality = max(0.0, 1.0 - abs(odd_gap - center) / span)
    move_quality, _ = _move_quality(row)
    depth_quality = (f_depth + s_depth) / 2.0
    score = (
        0.30 * corq
        + 0.20 * thinq
        + 0.20 * marq
        + 0.10 * depth_quality
        + 0.10 * gap_quality
        + 0.10 * move_quality
    )
    return round(score * 100.0, 2)


def evaluate_cloq_row(row: Dict[str, Any], config: CloQConfig = CloQConfig()) -> Dict[str, Any]:
    reasons: List[str] = []
    tags: List[str] = []
    warnings: List[str] = []

    pick_odds = _first_float(row, ["pick_odds", "odds", "price", "pick_price"])
    corq = _corq_prob(row)
    thinq = _thinq_prob(row)
    marq = _marq_prob(row)
    f_depth = _form_depth(row)
    s_depth = _stats_depth(row)
    odd_gap = compute_odd_gap_pct(row)

    if config.require_prematch and not _status_is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if config.require_singles and bool(row.get("is_doubles")):
        reasons.append("CLOQ_REJECT_DOUBLES")
    if pick_odds is None:
        reasons.append("CLOQ_REJECT_MISSING_PICK_ODDS")
    else:
        if pick_odds < config.min_odds:
            reasons.append("CLOQ_REJECT_ODDS_BELOW_MIN")
        if pick_odds > config.max_odds:
            reasons.append("CLOQ_REJECT_ODDS_ABOVE_MAX")
    if odd_gap is None:
        reasons.append("CLOQ_REJECT_MISSING_ODD_GAP")
    else:
        if odd_gap < config.min_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_SMALL")
        if odd_gap > config.max_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_WIDE")
    if corq is None or corq < config.min_corq_probability:
        reasons.append("CLOQ_REJECT_CORQ_BELOW_MIN")
    if thinq is None or thinq < config.min_thinq_probability:
        reasons.append("CLOQ_REJECT_THINQ_BELOW_MIN")
    if marq is None:
        warnings.append("CLOQ_WARN_MARQ_MISSING")
    elif marq < config.min_marq_probability:
        reasons.append("CLOQ_REJECT_MARQ_BELOW_MIN")
    if f_depth is None:
        warnings.append("CLOQ_WARN_FORM_DEPTH_MISSING")
    elif f_depth < config.min_form_depth:
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")
    if s_depth is None:
        warnings.append("CLOQ_WARN_STATS_DEPTH_MISSING")
    elif s_depth < config.min_stats_depth:
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")

    if thinq is not None and marq is not None:
        conflict_pp = abs(thinq - marq) * 100.0
        if conflict_pp > config.max_mmx_conflict_pp:
            warnings.append("CLOQ_WARN_MMX_CONFLICT")
            tags.append("MMx Conflict")
        else:
            tags.append("MMx Aligned")

    move_quality, move_tags = _move_quality(row)
    tags.extend(move_tags)
    if marq is not None and marq >= 0.50:
        tags.append("MarQ Support")
    if odd_gap is not None and config.min_odd_gap_pct <= odd_gap <= config.max_odd_gap_pct:
        tags.append("Close Odds")
    h2h_sample = _first_float(row, ["thinq_h2h_total_matches", "h2h_total_matches"])
    if h2h_sample is not None and h2h_sample <= 1:
        tags.append("Low H2H Sample")

    result = dict(row)
    result.update({
        "cloq_score": score_cloq_row(row, config=config),
        "cloq_passed": len(reasons) == 0,
        "cloq_reasons": reasons,
        "cloq_warnings": warnings,
        "cloq_tags": sorted(set(tags)),
        "cloq_pick_odds": pick_odds,
        "cloq_odd_gap_pct": round(odd_gap * 100.0, 2) if odd_gap is not None else None,
        "cloq_corq_probability": round(corq * 100.0, 2) if corq is not None else None,
        "cloq_thinq_probability": round(thinq * 100.0, 2) if thinq is not None else None,
        "cloq_marq_probability": round(marq * 100.0, 2) if marq is not None else None,
        "cloq_form_depth": round(f_depth * 100.0, 2) if f_depth is not None else None,
        "cloq_stats_depth": round(s_depth * 100.0, 2) if s_depth is not None else None,
        "cloq_move_quality": round(move_quality * 100.0, 2),
        "cloq_filter_version": "CLOQ_FILTER_V1",
    })
    return result
