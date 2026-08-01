"""CloQ filters - Close Odds Quality layer.

Target path in repository:
    cloq/filters.py

CloQ is intentionally a lightweight view/filter over existing CorQ/ThinQ/MarQ
outputs. It does not change CorQ ranking or model probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

CLOQ_FILTER_VERSION = "CLOQ_FILTER_V1_1"


@dataclass(frozen=True)
class CloqConfig:
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


DEFAULT_CONFIG = asdict(CloqConfig())


def get_default_config() -> Dict[str, Any]:
    return dict(DEFAULT_CONFIG)


def _first_value(row: Mapping[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, "", "N/A", "n/a", "—", "-"):
            return row.get(key)
    return default


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, "", "N/A", "n/a", "—", "-"):
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace("pp", "")
        return float(value)
    except Exception:
        return default


def _prob(value: Any, default: float = 0.0) -> float:
    """Return probability in 0..1 scale from either 0..1 or 0..100 input."""
    number = _as_float(value, None)
    if number is None:
        return default
    if number > 1.5:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def _pct_0_1(value: Any, default: float = 0.0) -> float:
    return _prob(value, default=default)


def _status_is_prematch(row: Mapping[str, Any]) -> bool:
    status_type = str(_first_value(row, ["status_type", "status", "match_status"], "")).lower()
    status_code = _as_float(_first_value(row, ["status_code"], None), None)
    if status_code == 0:
        return True
    if status_type in {"notstarted", "not_started", "scheduled", "prematch", "upcoming"}:
        return True
    return False


def _is_doubles(row: Mapping[str, Any]) -> bool:
    value = row.get("is_doubles")
    if isinstance(value, bool):
        return value
    text = str(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    category = str(_first_value(row, ["category", "event_category", "match_category"], "")).lower()
    return "double" in category


def _odds(row: Mapping[str, Any]) -> Tuple[float, float]:
    pick_odds = _as_float(_first_value(row, ["pick_odds", "odds", "p1_odds", "home_odds", "odds1"], None), 0.0) or 0.0
    opp_odds = _as_float(_first_value(row, ["opponent_odds", "opp_odds", "p2_odds", "away_odds", "odds2"], None), 0.0) or 0.0
    return pick_odds, opp_odds


def compute_odd_gap_pct(row: Mapping[str, Any]) -> float:
    existing = _as_float(_first_value(row, ["cloq_odd_gap_pct", "odd_gap_pct", "odds_gap_pct"], None), None)
    if existing is not None:
        if existing > 1.5:
            existing = existing / 100.0
        return max(0.0, existing)
    pick_odds, opp_odds = _odds(row)
    if pick_odds <= 0 or opp_odds <= 0:
        return 0.0
    base = min(pick_odds, opp_odds)
    if base <= 0:
        return 0.0
    return abs(pick_odds - opp_odds) / base


def _corq_probability(row: Mapping[str, Any]) -> float:
    return _prob(_first_value(row, [
        "corq_calibrated_probability", "corq_probability", "corq_prob", "corq", "model_probability"
    ], 0.0))


def _thinq_probability(row: Mapping[str, Any]) -> float:
    return _prob(_first_value(row, [
        "thinq_pick_probability", "thinq_probability", "thinq_prob", "thinq", "thinq_probability_pct"
    ], 0.0))


def _marq_probability(row: Mapping[str, Any]) -> float:
    return _prob(_first_value(row, [
        "corq_market_probability", "marq_pick_probability", "pick_marq_probability", "pick_marq", "marq_prob", "marq_probability"
    ], 0.0))


def _form_depth(row: Mapping[str, Any]) -> float:
    return _pct_0_1(_first_value(row, ["form_data_depth", "f_data_depth", "thinq_form_data_depth"], 0.0))


def _stats_depth(row: Mapping[str, Any]) -> float:
    return _pct_0_1(_first_value(row, [
        "s_data_depth", "sets_games_data_depth", "stats_data_depth", "ta_depth", "api_serve_stats_depth"
    ], 0.0))


def _mmx_conflict_pp(row: Mapping[str, Any], thinq_prob: float, marq_prob: float) -> float:
    existing = _as_float(_first_value(row, ["mmx_conflict_pp", "corq_mmx_conflict_pp"], None), None)
    if existing is not None:
        return abs(existing)
    return abs(thinq_prob - marq_prob) * 100.0


def _score(row: Mapping[str, Any], config: Mapping[str, Any]) -> float:
    corq = _corq_probability(row)
    thinq = _thinq_probability(row)
    marq = _marq_probability(row)
    form_depth = _form_depth(row)
    stats_depth = _stats_depth(row)
    gap = compute_odd_gap_pct(row)

    min_gap = float(config.get("min_odd_gap_pct", 0.0))
    max_gap = float(config.get("max_odd_gap_pct", 0.40))
    if max_gap <= min_gap:
        gap_quality = 1.0
    elif gap < min_gap:
        gap_quality = max(0.0, gap / max(min_gap, 0.0001))
    elif gap > max_gap:
        gap_quality = max(0.0, 1.0 - ((gap - max_gap) / max(max_gap, 0.0001)))
    else:
        gap_quality = 1.0

    move_bonus = 0.0
    move = str(_first_value(row, ["marq_move", "move", "marq_internal_move_signal"], "")).lower()
    clv = _as_float(_first_value(row, ["marq_internal_clv_pp", "internal_clv_pp", "clv_pp"], 0.0), 0.0) or 0.0
    if "toward" in move or clv > 0:
        move_bonus = min(1.0, max(0.0, abs(clv) / 5.0))
    elif "against" in move or clv < 0:
        move_bonus = -min(1.0, max(0.0, abs(clv) / 5.0)) * 0.5

    raw = (
        0.30 * corq +
        0.20 * thinq +
        0.20 * marq +
        0.10 * form_depth +
        0.10 * stats_depth +
        0.07 * gap_quality +
        0.03 * move_bonus
    )
    return round(max(0.0, min(1.0, raw)) * 100.0, 2)


def evaluate_row(row: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)

    pick_odds, opp_odds = _odds(row)
    gap = compute_odd_gap_pct(row)
    corq = _corq_probability(row)
    thinq = _thinq_probability(row)
    marq = _marq_probability(row)
    form_depth = _form_depth(row)
    stats_depth = _stats_depth(row)
    mmx_conflict_pp = _mmx_conflict_pp(row, thinq, marq)

    reasons: List[str] = []
    warnings: List[str] = []
    tags: List[str] = []

    if cfg.get("require_prematch", True) and not _status_is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if cfg.get("require_singles", True) and _is_doubles(row):
        reasons.append("CLOQ_REJECT_DOUBLES")

    if pick_odds < float(cfg["min_odds"]):
        reasons.append("CLOQ_REJECT_ODDS_BELOW_MIN")
    if pick_odds > float(cfg["max_odds"]):
        reasons.append("CLOQ_REJECT_ODDS_ABOVE_MAX")

    if gap < float(cfg["min_odd_gap_pct"]):
        reasons.append("CLOQ_REJECT_ODD_GAP_TOO_SMALL")
    if gap > float(cfg["max_odd_gap_pct"]):
        reasons.append("CLOQ_REJECT_ODD_GAP_TOO_WIDE")

    if corq < float(cfg["min_corq_probability"]):
        reasons.append("CLOQ_REJECT_CORQ_BELOW_MIN")
    if thinq < float(cfg["min_thinq_probability"]):
        reasons.append("CLOQ_REJECT_THINQ_BELOW_MIN")
    if marq < float(cfg["min_marq_probability"]):
        reasons.append("CLOQ_REJECT_MARQ_BELOW_MIN")
    if form_depth < float(cfg["min_form_depth"]):
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")
    if stats_depth < float(cfg["min_stats_depth"]):
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")

    if mmx_conflict_pp > float(cfg["max_mmx_conflict_pp"]):
        warnings.append("CLOQ_WARN_MMX_CONFLICT")

    if pick_odds >= float(cfg["min_odds"]):
        tags.append("Close Odds")
    if float(cfg["min_odd_gap_pct"]) <= gap <= float(cfg["max_odd_gap_pct"]):
        tags.append("Gap OK")
    if marq >= float(cfg["min_marq_probability"]):
        tags.append("MarQ Support")
    if corq >= float(cfg["min_corq_probability"]) and thinq >= float(cfg["min_thinq_probability"]):
        tags.append("Model Support")
    if mmx_conflict_pp <= float(cfg["max_mmx_conflict_pp"]):
        tags.append("MMx Aligned")
    else:
        tags.append("MMx Conflict")

    move = str(_first_value(row, ["marq_move", "move", "marq_internal_move_signal"], "")).lower()
    if "toward" in move:
        tags.append("Move Toward")
    elif "against" in move:
        tags.append("Move Against")
    else:
        tags.append("Stable Move")

    if _first_value(row, ["marq_internal_clv_pp", "internal_clv_pp", "clv_pp"], None) in (None, "", "N/A"):
        tags.append("CLV Pending")

    return {
        "cloq_filter_version": CLOQ_FILTER_VERSION,
        "cloq_passed": not reasons,
        "cloq_reasons": reasons,
        "cloq_warnings": warnings,
        "cloq_tags": tags,
        "cloq_score": _score(row, cfg),
        "cloq_odd_gap_pct": round(gap, 4),
        "cloq_pick_odds": pick_odds,
        "cloq_opponent_odds": opp_odds,
        "cloq_corq_probability": round(corq, 4),
        "cloq_thinq_probability": round(thinq, 4),
        "cloq_marq_probability": round(marq, 4),
        "cloq_form_depth": round(form_depth, 4),
        "cloq_stats_depth": round(stats_depth, 4),
        "cloq_mmx_conflict_pp": round(mmx_conflict_pp, 2),
        "cloq_config": cfg,
    }


def enrich_row(row: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    out = dict(row)
    out.update(evaluate_row(row, config=config))
    return out


def filter_rows(rows: Iterable[Mapping[str, Any]], config: Optional[Mapping[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    passed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    reason_counts: Dict[str, int] = {}
    warning_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}

    for row in rows:
        enriched = enrich_row(row, config=config)
        for reason in enriched.get("cloq_reasons", []):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for warning in enriched.get("cloq_warnings", []):
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
        for tag in enriched.get("cloq_tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if enriched.get("cloq_passed"):
            passed.append(enriched)
        else:
            rejected.append(enriched)

    passed.sort(key=lambda r: r.get("cloq_score", 0.0), reverse=True)
    rejected.sort(key=lambda r: r.get("cloq_score", 0.0), reverse=True)
    manifest = {
        "filter_version": CLOQ_FILTER_VERSION,
        "config": dict(DEFAULT_CONFIG if config is None else {**DEFAULT_CONFIG, **dict(config)}),
        "source_rows": len(passed) + len(rejected),
        "passed_rows": len(passed),
        "rejected_rows": len(rejected),
        "reason_counts": reason_counts,
        "warning_counts": warning_counts,
        "tag_counts": tag_counts,
    }
    return passed, rejected, manifest


# Backward-compatible aliases for older engine imports.
evaluate_cloq_row = evaluate_row
apply_filter = evaluate_row
apply_cloq_filter = evaluate_row
score_row = _score
build_cloq_record = enrich_row
