"""CloQ filtering utilities.

CloQ = Close Odds Quality.

This module intentionally keeps CloQ as a lightweight shortlist layer. It does
not change CorQ ranking or ThinQ calculations. It only reads already generated
prediction rows and marks whether a row passes the CloQ filter.

Version V1.3 change:
- MarQ is no longer a hard reject.
- Missing MarQ adds CLOQ_WARN_MARQ_MISSING.
- Weak MarQ adds CLOQ_WARN_MARQ_WEAK.
- CorQ and ThinQ remain hard filters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

FILTER_VERSION = "CLOQ_FILTER_V1_3_MARQ_OPTIONAL"


@dataclass(frozen=True)
class CloQConfig:
    min_odds: float = 1.70
    max_odds: float = 2.90
    min_odd_gap_pct: float = 0.00
    max_odd_gap_pct: float = 0.40
    min_corq_probability: float = 0.52
    min_thinq_probability: float = 0.52
    # MarQ threshold is soft only from V1.3 onward.
    min_marq_probability: float = 0.30
    min_form_depth: float = 0.40
    min_stats_depth: float = 0.25
    max_mmx_conflict_pp: float = 18.0
    require_prematch: bool = True
    require_singles: bool = True


DEFAULT_CONFIG = CloQConfig()


def _get_nested(row: Mapping[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = row
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return default
        if part not in cur:
            return default
        cur = cur.get(part)
    return cur


def _first_present(row: Mapping[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if "." in name:
            value = _get_nested(row, name, None)
        else:
            value = row.get(name)
        if value not in (None, "", "N/A", "n/a", "-", "—"):
            return value
    return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, "", "N/A", "n/a", "-", "—"):
        return default
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "").replace("pp", "")
            if cleaned.startswith("+"):
                cleaned = cleaned[1:]
            return float(cleaned)
        return float(value)
    except Exception:
        return default


def _prob(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Normalize probability to 0..1.

    Inputs may arrive as 0.62, 62, or "62%" depending on the source layer.
    """
    x = _to_float(value, default)
    if x is None:
        return default
    if x > 1.000001:
        x = x / 100.0
    if x < 0:
        return default
    return max(0.0, min(1.0, x))


def _pct(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Normalize percentage-like value to 0..1."""
    return _prob(value, default)


def _is_prematch(row: Mapping[str, Any]) -> bool:
    status_type = str(_first_present(row, ["status_type", "status.type", "raw.status.type"], "")).lower()
    status_code = _to_float(_first_present(row, ["status_code", "raw.status.code"], None), None)
    if status_code == 0:
        return True
    return status_type in {
        "notstarted",
        "not_started",
        "not started",
        "scheduled",
        "prematch",
        "pre-match",
        "pending",
    }


def _is_singles(row: Mapping[str, Any]) -> bool:
    is_doubles = row.get("is_doubles")
    if isinstance(is_doubles, bool):
        return not is_doubles
    filters = _get_nested(row, "raw.eventFilters", {})
    if isinstance(filters, Mapping):
        categories = filters.get("category") or []
        if isinstance(categories, list) and any(str(x).lower() == "doubles" for x in categories):
            return False
    return True


def _odds(row: Mapping[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    pick_odds = _to_float(
        _first_present(row, ["pick_odds", "odds", "price", "home_odds", "away_odds"], None),
        None,
    )
    opponent_odds = _to_float(
        _first_present(row, ["opponent_odds", "opp_odds", "opponent_price"], None),
        None,
    )
    # Fallback when only home/away odds exist.
    if opponent_odds is None:
        pick_side = str(row.get("pick_side") or "").upper()
        home_odds = _to_float(row.get("home_odds"), None)
        away_odds = _to_float(row.get("away_odds"), None)
        if pick_side == "HOME" and away_odds is not None:
            opponent_odds = away_odds
        elif pick_side == "AWAY" and home_odds is not None:
            opponent_odds = home_odds
    return pick_odds, opponent_odds


def _odd_gap_pct(pick_odds: Optional[float], opponent_odds: Optional[float], row: Mapping[str, Any]) -> Optional[float]:
    existing = _to_float(row.get("odd_gap_pct", row.get("odds_gap_pct")), None)
    if existing is not None:
        # Already usually stored as ratio, but keep robust handling.
        return existing / 100.0 if existing > 1.000001 else existing
    if pick_odds is None or opponent_odds is None or pick_odds <= 0 or opponent_odds <= 0:
        return None
    denominator = min(pick_odds, opponent_odds)
    if denominator <= 0:
        return None
    return abs(pick_odds - opponent_odds) / denominator


def _corq_prob(row: Mapping[str, Any]) -> Optional[float]:
    return _prob(
        _first_present(
            row,
            [
                "corq_calibrated_probability",
                "corq_probability",
                "probability",
                "win_probability",
                "model_probability",
                "corq_pct",
            ],
            None,
        ),
        None,
    )


def _thinq_prob(row: Mapping[str, Any]) -> Optional[float]:
    return _prob(
        _first_present(
            row,
            [
                "thinq_pick_probability",
                "thinq_probability",
                "thinq.thinq_probability_layer.pick_probability",
                "thinq_probability_layer.pick_probability",
                "thinq_prob",
            ],
            None,
        ),
        None,
    )


def _marq_prob(row: Mapping[str, Any]) -> Optional[float]:
    return _prob(
        _first_present(
            row,
            [
                "marq_pick_probability",
                "pick_marq_probability",
                "marq_probability",
                "corq_market_probability",
                "market_pick_probability",
                "marq_prob",
            ],
            None,
        ),
        None,
    )


def _form_depth(row: Mapping[str, Any]) -> Optional[float]:
    return _pct(
        _first_present(
            row,
            [
                "form_data_depth",
                "f_data_depth",
                "recent_form.form_data_depth",
                "thinq.recent_form.form_data_depth",
            ],
            None,
        ),
        None,
    )


def _stats_depth(row: Mapping[str, Any]) -> Optional[float]:
    return _pct(
        _first_present(
            row,
            [
                "s_data_depth",
                "sets_games_data_depth",
                "stats_data_depth",
                "ta_depth",
                "thinq.ta_context.ta_pick_depth",
            ],
            None,
        ),
        None,
    )


def _score(
    corq: Optional[float],
    thinq: Optional[float],
    marq: Optional[float],
    form_depth: Optional[float],
    stats_depth: Optional[float],
    odd_gap: Optional[float],
    warnings: List[str],
) -> float:
    """Compute a soft CloQ ranking score, 0..100-ish.

    Hard filters decide pass/fail. This score is only for ordering passed rows.
    Missing MarQ is allowed; when missing, a neutral 0.50 market value is used
    for scoring to avoid over-penalizing missing market enrichment.
    """
    c = corq if corq is not None else 0.50
    t = thinq if thinq is not None else 0.50
    m = marq if marq is not None else 0.50
    f = form_depth if form_depth is not None else 0.0
    s = stats_depth if stats_depth is not None else 0.0
    # Prefer genuinely close odds up to the cap, but do not over-reward zero gap.
    if odd_gap is None:
        gap_quality = 0.50
    else:
        gap_quality = max(0.0, min(1.0, 1.0 - min(max(odd_gap - 0.10, 0.0), 0.40) / 0.40))
    penalty = 0.0
    if "CLOQ_WARN_MARQ_MISSING" in warnings:
        penalty += 2.0
    if "CLOQ_WARN_MARQ_WEAK" in warnings:
        penalty += 3.0
    if "CLOQ_WARN_MMX_CONFLICT" in warnings:
        penalty += 4.0
    return round(
        100.0
        * (
            0.30 * c
            + 0.25 * t
            + 0.15 * m
            + 0.12 * f
            + 0.10 * s
            + 0.08 * gap_quality
        )
        - penalty,
        2,
    )


def evaluate_cloq_row(row: Mapping[str, Any], config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    reasons: List[str] = []
    warnings: List[str] = []
    tags: List[str] = []

    pick_odds, opponent_odds = _odds(row)
    odd_gap = _odd_gap_pct(pick_odds, opponent_odds, row)
    corq = _corq_prob(row)
    thinq = _thinq_prob(row)
    marq = _marq_prob(row)
    form_depth = _form_depth(row)
    stats_depth = _stats_depth(row)

    if config.require_prematch and not _is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if config.require_singles and not _is_singles(row):
        reasons.append("CLOQ_REJECT_NOT_SINGLES")

    if pick_odds is None:
        reasons.append("CLOQ_REJECT_ODDS_MISSING")
    else:
        if pick_odds < config.min_odds:
            reasons.append("CLOQ_REJECT_ODDS_BELOW_MIN")
        if pick_odds > config.max_odds:
            reasons.append("CLOQ_REJECT_ODDS_ABOVE_MAX")

    if odd_gap is None:
        warnings.append("CLOQ_WARN_ODD_GAP_MISSING")
    else:
        if odd_gap < config.min_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_NARROW")
        if odd_gap > config.max_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_WIDE")

    # CorQ and ThinQ stay as hard filters.
    if corq is None:
        reasons.append("CLOQ_REJECT_CORQ_MISSING")
    elif corq < config.min_corq_probability:
        reasons.append("CLOQ_REJECT_CORQ_BELOW_MIN")

    if thinq is None:
        reasons.append("CLOQ_REJECT_THINQ_MISSING")
    elif thinq < config.min_thinq_probability:
        reasons.append("CLOQ_REJECT_THINQ_BELOW_MIN")

    # MarQ is optional from V1.3 onward.
    if marq is None:
        warnings.append("CLOQ_WARN_MARQ_MISSING")
        tags.append("MarQ Missing")
    elif marq < config.min_marq_probability:
        warnings.append("CLOQ_WARN_MARQ_WEAK")
        tags.append("MarQ Weak")
    elif marq >= 0.50:
        tags.append("MarQ Support")
    else:
        tags.append("MarQ Neutral")
        tags.append("Thin Market")

    if form_depth is None:
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")
    elif form_depth < config.min_form_depth:
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")

    if stats_depth is None:
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")
    elif stats_depth < config.min_stats_depth:
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")

    if odd_gap is not None and odd_gap <= config.max_odd_gap_pct:
        tags.append("Close Odds")
    if corq is not None and corq >= config.min_corq_probability:
        tags.append("CorQ OK")
    if thinq is not None and thinq >= config.min_thinq_probability:
        tags.append("ThinQ OK")

    if corq is not None and thinq is not None:
        diff_pp = abs(corq - thinq) * 100.0
        if diff_pp > config.max_mmx_conflict_pp:
            warnings.append("CLOQ_WARN_MMX_CONFLICT")
            tags.append("MMx Conflict")
        else:
            tags.append("MMx Aligned")

    if str(row.get("clv_status", "")).lower() in {"pending", ""} or row.get("clv") is None:
        tags.append("CLV Pending")

    passed = len(reasons) == 0
    row_score = _score(corq, thinq, marq, form_depth, stats_depth, odd_gap, warnings)

    return {
        "cloq_filter_version": FILTER_VERSION,
        "cloq_passed": passed,
        "cloq_score": row_score,
        "cloq_reasons": reasons,
        "cloq_warnings": warnings,
        "cloq_tags": sorted(dict.fromkeys(tags)),
        "cloq_odd_gap_pct": odd_gap,
        "cloq_pick_odds": pick_odds,
        "cloq_opponent_odds": opponent_odds,
        "cloq_corq_probability": corq,
        "cloq_thinq_probability": thinq,
        "cloq_marq_probability": marq,
        "cloq_form_depth": form_depth,
        "cloq_stats_depth": stats_depth,
    }


def enrich_cloq_row(row: Mapping[str, Any], config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    out = dict(row)
    out.update(evaluate_cloq_row(row, config=config))
    return out


def filter_cloq_rows(rows: Iterable[Mapping[str, Any]], config: CloQConfig = DEFAULT_CONFIG) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    passed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for row in rows:
        enriched = enrich_cloq_row(row, config=config)
        if enriched.get("cloq_passed"):
            passed.append(enriched)
        else:
            rejected.append(enriched)
    passed.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)
    rejected.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)
    return passed, rejected


def config_dict(config: CloQConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    return asdict(config)
