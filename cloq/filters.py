from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple
import math


@dataclass(frozen=True)
class CloQConfig:
    """CloQ V1.1 threshold set.

    CloQ is a close-odds shortlist layer. It is intentionally not a new model.
    It takes already generated CorQ/ThinQ/MarQ rows and applies transparent
    close-odds / quality checks.
    """

    min_odds: float = 1.70
    max_odds: float = 2.60
    min_odd_gap_pct: float = 0.00
    max_odd_gap_pct: float = 0.40
    min_corq_probability: float = 0.52
    min_thinq_probability: float = 0.52
    min_marq_probability: float = 0.48
    min_form_depth: float = 0.50
    min_stats_depth: float = 0.25
    max_mmx_conflict_pp: float = 18.0
    require_prematch: bool = True
    require_singles: bool = True


DEFAULT_CONFIG = CloQConfig()
FILTER_VERSION = "CLOQ_FILTER_V1_1"


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        if math.isnan(float(value)):
            return default
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text or text in {"-", "--", "—", "N/A", "na", "None"}:
            return default
        try:
            parsed = float(text)
            # Treat 55 as percent if the caller expects a probability; callers normalize.
            return parsed
        except ValueError:
            return default
    return default


def _prob(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _as_float(row.get(key))
        if value is None:
            continue
        # Accept both 0.55 and 55.0 forms.
        if value > 1.5:
            value = value / 100.0
        if 0.0 <= value <= 1.0:
            return value
    return None


def _nested_prob(row: Dict[str, Any], path: Tuple[str, ...]) -> Optional[float]:
    obj: Any = row
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    value = _as_float(obj)
    if value is None:
        return None
    if value > 1.5:
        value = value / 100.0
    if 0.0 <= value <= 1.0:
        return value
    return None


def _first_prob(row: Dict[str, Any], keys: Iterable[str], nested: Iterable[Tuple[str, ...]] = ()) -> Optional[float]:
    value = _prob(row, *keys)
    if value is not None:
        return value
    for path in nested:
        value = _nested_prob(row, path)
        if value is not None:
            return value
    return None


def _first_float(row: Dict[str, Any], keys: Iterable[str], default: Optional[float] = None) -> Optional[float]:
    for key in keys:
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return default


def _is_prematch(row: Dict[str, Any]) -> bool:
    status_type = str(row.get("status_type") or row.get("status") or "").lower()
    status_code = row.get("status_code")
    if status_code in (0, "0"):
        return True
    if status_type in {"notstarted", "not_started", "scheduled", "prematch", "not started"}:
        return True
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    raw_status_type = str(status.get("type") or status.get("description") or "").lower()
    raw_status_code = status.get("code")
    if raw_status_code in (0, "0"):
        return True
    return raw_status_type in {"notstarted", "not_started", "scheduled", "prematch", "not started"}


def _is_singles(row: Dict[str, Any]) -> bool:
    if row.get("is_doubles") is True:
        return False
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    event_filters = raw.get("eventFilters") if isinstance(raw.get("eventFilters"), dict) else {}
    category = event_filters.get("category")
    if isinstance(category, list) and any(str(x).lower() == "doubles" for x in category):
        return False
    return True


def _odd_gap_pct(row: Dict[str, Any], pick_odds: Optional[float], opponent_odds: Optional[float]) -> Optional[float]:
    existing = _as_float(row.get("odd_gap_pct"), None)
    if existing is None:
        existing = _as_float(row.get("odds_gap_pct"), None)
    if existing is not None:
        # Some rows store 0.167, some 16.7.
        return existing / 100.0 if existing > 1.0 else existing
    if pick_odds and opponent_odds and min(pick_odds, opponent_odds) > 0:
        return abs(pick_odds - opponent_odds) / min(pick_odds, opponent_odds)
    return None


def evaluate_cloq_row(row: Dict[str, Any], config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """Return row copy enriched with CloQ pass/fail, reasons, warnings and score."""
    out = dict(row)
    reasons: List[str] = []
    warnings: List[str] = []
    tags: List[str] = []

    pick_odds = _first_float(row, ["pick_odds", "odds", "price", "home_odds", "odds1"])
    opponent_odds = _first_float(row, ["opponent_odds", "opp_odds", "away_odds", "odds2"])
    corq = _first_prob(row, [
        "corq_probability", "corq_calibrated_probability", "corq", "win_probability", "model_probability"
    ])
    thinq = _first_prob(
        row,
        ["thinq_pick_probability", "thinq_probability", "thinq_prob", "thinq_probability_pct"],
        nested=[("thinq", "thinq_probability_layer", "pick_probability"), ("thinq", "pick_probability")],
    )
    marq = _first_prob(row, [
        "marq_pick_probability", "pick_marq_probability", "pick_marq", "marq_probability", "corq_market_probability"
    ])
    if marq is None:
        # Fallback from market odds if available.
        if pick_odds and opponent_odds and pick_odds > 0 and opponent_odds > 0:
            p_imp = 1.0 / pick_odds
            o_imp = 1.0 / opponent_odds
            denom = p_imp + o_imp
            if denom > 0:
                marq = p_imp / denom

    form_depth = _first_prob(row, ["form_data_depth", "f_data_depth", "thinq_form_data_depth"])
    stats_depth = _first_prob(row, ["s_data_depth", "sets_games_data_depth", "stats_data_depth"])
    odd_gap = _odd_gap_pct(row, pick_odds, opponent_odds)

    if config.require_prematch and not _is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if config.require_singles and not _is_singles(row):
        reasons.append("CLOQ_REJECT_NOT_SINGLES")
    if pick_odds is None or pick_odds < config.min_odds:
        reasons.append("CLOQ_REJECT_ODDS_BELOW_MIN")
    if pick_odds is not None and pick_odds > config.max_odds:
        reasons.append("CLOQ_REJECT_ODDS_ABOVE_MAX")
    if odd_gap is None:
        warnings.append("CLOQ_WARN_ODD_GAP_MISSING")
    else:
        if odd_gap < config.min_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_SMALL")
        if odd_gap > config.max_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_WIDE")
    if corq is None or corq < config.min_corq_probability:
        reasons.append("CLOQ_REJECT_CORQ_BELOW_MIN")
    if thinq is None or thinq < config.min_thinq_probability:
        reasons.append("CLOQ_REJECT_THINQ_BELOW_MIN")
    if marq is None or marq < config.min_marq_probability:
        reasons.append("CLOQ_REJECT_MARQ_BELOW_MIN")
    if form_depth is None or form_depth < config.min_form_depth:
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")
    if stats_depth is None or stats_depth < config.min_stats_depth:
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")

    if odd_gap is not None and odd_gap <= config.max_odd_gap_pct:
        tags.append("Close Odds")
    if marq is not None and marq >= 0.50:
        tags.append("MarQ Support")
    if corq is not None and thinq is not None and abs((corq - thinq) * 100.0) <= config.max_mmx_conflict_pp:
        tags.append("MMx Aligned")
    if corq is not None and marq is not None and abs((corq - marq) * 100.0) > config.max_mmx_conflict_pp:
        warnings.append("CLOQ_WARN_MMX_CONFLICT")
        tags.append("MMx Conflict")
    if str(row.get("clv") or row.get("marq_clv") or "").lower() in {"pending", "no snapshot", ""}:
        tags.append("CLV Pending")
    if row.get("thinq_h2h_sample_quality") == "LOW_SAMPLE" or row.get("h2h_sample_quality") == "LOW_SAMPLE":
        tags.append("Low H2H Sample")

    # Score is a ranking helper, not a hard model probability.
    def nz(value: Optional[float], fallback: float) -> float:
        return fallback if value is None else value

    gap_quality = 0.5
    if odd_gap is not None:
        # Reward close enough but not too chaotic markets. Center around 18%.
        gap_quality = max(0.0, min(1.0, 1.0 - abs(odd_gap - 0.18) / 0.40))
    score = (
        0.30 * nz(corq, 0.50)
        + 0.20 * nz(thinq, 0.50)
        + 0.20 * nz(marq, 0.50)
        + 0.10 * nz(form_depth, 0.50)
        + 0.10 * nz(stats_depth, 0.50)
        + 0.10 * gap_quality
    )

    out.update({
        "cloq_filter_version": FILTER_VERSION,
        "cloq_passed": not reasons,
        "cloq_reasons": reasons,
        "cloq_warnings": warnings,
        "cloq_tags": tags,
        "cloq_score": round(score * 100.0, 2),
        "cloq_odd_gap_pct": round(odd_gap * 100.0, 2) if odd_gap is not None else None,
        "cloq_pick_odds": pick_odds,
        "cloq_opponent_odds": opponent_odds,
        "cloq_corq_probability": round(corq * 100.0, 2) if corq is not None else None,
        "cloq_thinq_probability": round(thinq * 100.0, 2) if thinq is not None else None,
        "cloq_marq_probability": round(marq * 100.0, 2) if marq is not None else None,
        "cloq_form_depth": round(form_depth * 100.0, 2) if form_depth is not None else None,
        "cloq_stats_depth": round(stats_depth * 100.0, 2) if stats_depth is not None else None,
    })
    return out


# Backwards-compatible aliases used by older engine versions.
evaluate_row = evaluate_cloq_row


def filter_cloq_rows(rows: Iterable[Dict[str, Any]], config: CloQConfig = DEFAULT_CONFIG) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    passed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for row in rows:
        evaluated = evaluate_cloq_row(row, config)
        if evaluated.get("cloq_passed"):
            passed.append(evaluated)
        else:
            rejected.append(evaluated)
    passed.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)
    rejected.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)
    return passed, rejected


filter_rows = filter_cloq_rows


def config_to_dict(config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    return asdict(config)
