"""CloQ filter layer.

CloQ = Close Odds Quality shortlist.
This module is intentionally self-contained so the workflow can import:
    from cloq.filters import CloQConfig, DEFAULT_CONFIG, FILTER_VERSION,
        config_to_dict, filter_cloq_rows

Version V1.3: MarQ is optional/soft. CorQ and ThinQ remain hard filters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

FILTER_VERSION = "CLOQ_FILTER_V1_3_MARQ_OPTIONAL"


@dataclass(frozen=True)
class CloQConfig:
    min_odds: float = 1.70
    max_odds: float = 2.90
    min_odd_gap_pct: float = 0.00
    max_odd_gap_pct: float = 0.40
    min_corq_probability: float = 0.52
    min_thinq_probability: float = 0.52
    min_marq_probability: float = 0.30
    min_form_depth: float = 0.40
    min_stats_depth: float = 0.25
    max_mmx_conflict_pp: float = 18.0
    require_prematch: bool = True
    require_singles: bool = True


DEFAULT_CONFIG = CloQConfig()


def config_to_dict(config: Optional[CloQConfig] = None) -> Dict[str, Any]:
    """Return a JSON-serializable copy of CloQConfig.

    Kept as a public helper because cloq.engine imports it for manifest output.
    """
    return asdict(config or DEFAULT_CONFIG)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "")
            if cleaned in ("", "-", "—", "N/A", "n/a", "None", "null"):
                return None
            value = cleaned
        return float(value)
    except Exception:
        return None


def _prob(value: Any) -> Optional[float]:
    """Normalize probability to decimal 0..1.

    Accepts either decimal values, e.g. 0.58, or percentage values, e.g. 58.0.
    """
    num = _to_float(value)
    if num is None:
        return None
    if num > 1.5:
        num = num / 100.0
    if num < 0:
        return None
    if num > 1:
        return 1.0
    return num


def _first(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, "", "N/A", "n/a", "-", "—"):
            return row.get(key)
    return None


def _nested(row: Dict[str, Any], path: Iterable[str]) -> Any:
    cur: Any = row
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _status_is_prematch(row: Dict[str, Any]) -> bool:
    status_type = str(_first(row, ["status_type", "match_status", "status"]) or "").lower()
    status_code = _first(row, ["status_code", "match_status_code"])
    if status_code in (0, "0"):
        return True
    allowed = {"notstarted", "not_started", "scheduled", "prematch", "pre_match", "upcoming"}
    return status_type in allowed


def _is_doubles(row: Dict[str, Any]) -> bool:
    if row.get("is_doubles") is True:
        return True
    event_filters = _nested(row, ["raw", "eventFilters"])
    if isinstance(event_filters, dict):
        values = []
        for value in event_filters.values():
            if isinstance(value, list):
                values.extend(str(x).lower() for x in value)
            else:
                values.append(str(value).lower())
        if "doubles" in values:
            return True
    text = " ".join(str(row.get(k, "")).lower() for k in ("category", "level", "tournament"))
    return "doubles" in text


def _pick_odds(row: Dict[str, Any]) -> Optional[float]:
    return _to_float(_first(row, ["pick_odds", "odds", "price", "best_odds"]))


def _opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    return _to_float(_first(row, ["opponent_odds", "opp_odds", "opponent_price"]))


def _odd_gap_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = _to_float(_first(row, ["cloq_odd_gap_pct", "odd_gap_pct", "odds_gap_pct"]))
    if explicit is not None:
        return explicit / 100.0 if explicit > 1.5 else explicit
    pick = _pick_odds(row)
    opp = _opponent_odds(row)
    if pick is None or opp is None or min(pick, opp) <= 0:
        return None
    return abs(pick - opp) / min(pick, opp)


def _corq_probability(row: Dict[str, Any]) -> Optional[float]:
    return _prob(_first(row, [
        "corq_probability",
        "corq_calibrated_probability",
        "estimated_probability",
        "win_probability",
        "pick_probability",
        "corq",
    ]))


def _thinq_probability(row: Dict[str, Any]) -> Optional[float]:
    return _prob(_first(row, [
        "thinq_pick_probability",
        "thinq_probability",
        "thinq_prob",
        "thinq_probability_pct",
    ]) or _nested(row, ["thinq", "thinq_pick_probability"]) or _nested(row, ["thinq", "thinq_probability_layer", "pick_probability"]))


def _marq_probability(row: Dict[str, Any]) -> Optional[float]:
    return _prob(_first(row, [
        "marq_pick_probability",
        "pick_marq_probability",
        "marq_probability",
        "pick_marq_pct",
        "marq_pick_pct",
    ]))


def _form_depth(row: Dict[str, Any]) -> Optional[float]:
    return _prob(_first(row, ["form_data_depth", "f_data_depth", "thinq_form_data_depth"]))


def _stats_depth(row: Dict[str, Any]) -> Optional[float]:
    return _prob(_first(row, ["s_data_depth", "sets_games_data_depth", "stats_data_depth", "ta_depth"]))


def _mmx_conflict_pp(row: Dict[str, Any], thinq: Optional[float], marq: Optional[float]) -> Optional[float]:
    explicit = _to_float(_first(row, ["mmx_conflict_pp", "corq_mmx_conflict_pp"]))
    if explicit is not None:
        return abs(explicit)
    if thinq is None or marq is None:
        return None
    return abs(thinq - marq) * 100.0


def _score(row: Dict[str, Any], corq: Optional[float], thinq: Optional[float], marq: Optional[float], form_depth: Optional[float], stats_depth: Optional[float], gap: Optional[float]) -> float:
    """Simple sortable CloQ score, not a probability."""
    corq_v = corq if corq is not None else 0.50
    thinq_v = thinq if thinq is not None else 0.50
    marq_v = marq if marq is not None else 0.50
    form_v = form_depth if form_depth is not None else 0.0
    stats_v = stats_depth if stats_depth is not None else 0.0
    if gap is None:
        gap_quality = 0.50
    else:
        # Best around close-but-not-identical 10-25% gap, acceptable until 40%.
        if gap <= 0.25:
            gap_quality = 1.0
        elif gap <= 0.40:
            gap_quality = 0.70
        else:
            gap_quality = 0.25
    return round((0.30 * corq_v
        + 0.25 * thinq_v
        + 0.15 * marq_v
        + 0.10 * form_v
        + 0.10 * stats_v
        + 0.10 * gap_quality
    ) * 100.0, 2)


def evaluate_cloq_row(row: Dict[str, Any], config: Optional[CloQConfig] = None) -> Dict[str, Any]:
    config = config or DEFAULT_CONFIG
    reasons: List[str] = []
    warnings: List[str] = []
    tags: List[str] = []

    odds = _pick_odds(row)
    opponent_odds = _opponent_odds(row)
    gap = _odd_gap_pct(row)
    corq = _corq_probability(row)
    thinq = _thinq_probability(row)
    marq = _marq_probability(row)
    form_depth = _form_depth(row)
    stats_depth = _stats_depth(row)
    mmx_conflict = _mmx_conflict_pp(row, thinq, marq)

    if config.require_prematch and not _status_is_prematch(row):
        reasons.append("CLOQ_REJECT_STATUS_NOT_PREMATCH")
    if config.require_singles and _is_doubles(row):
        reasons.append("CLOQ_REJECT_DOUBLES")

    if odds is None:
        reasons.append("CLOQ_REJECT_ODDS_MISSING")
    else:
        if odds < config.min_odds:
            reasons.append("CLOQ_REJECT_ODDS_BELOW_MIN")
        if odds > config.max_odds:
            reasons.append("CLOQ_REJECT_ODDS_ABOVE_MAX")

    if gap is None:
        warnings.append("CLOQ_WARN_ODD_GAP_MISSING")
    else:
        if gap < config.min_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_NARROW")
        if gap > config.max_odd_gap_pct:
            reasons.append("CLOQ_REJECT_ODD_GAP_TOO_WIDE")
        if gap <= 0.25:
            tags.append("Close Odds")

    # CorQ and ThinQ remain hard filters.
    if corq is None:
        reasons.append("CLOQ_REJECT_CORQ_MISSING")
    elif corq < config.min_corq_probability:
        reasons.append("CLOQ_REJECT_CORQ_BELOW_MIN")

    if thinq is None:
        reasons.append("CLOQ_REJECT_THINQ_MISSING")
    elif thinq < config.min_thinq_probability:
        reasons.append("CLOQ_REJECT_THINQ_BELOW_MIN")

    # MarQ is optional/soft in V1.3.
    if marq is None:
        warnings.append("CLOQ_WARN_MARQ_MISSING")
        tags.append("MarQ Missing")
    elif marq < config.min_marq_probability:
        warnings.append("CLOQ_WARN_MARQ_WEAK")
        tags.append("MarQ Weak")
    elif marq < 0.50:
        tags.append("MarQ Neutral")
        tags.append("Thin Market")
    else:
        tags.append("MarQ Support")

    if form_depth is None:
        reasons.append("CLOQ_REJECT_FORM_DEPTH_MISSING")
    elif form_depth < config.min_form_depth:
        reasons.append("CLOQ_REJECT_LOW_FORM_DEPTH")

    if stats_depth is None:
        reasons.append("CLOQ_REJECT_STATS_DEPTH_MISSING")
    elif stats_depth < config.min_stats_depth:
        reasons.append("CLOQ_REJECT_LOW_STATS_DEPTH")

    if mmx_conflict is not None and mmx_conflict > config.max_mmx_conflict_pp:
        warnings.append("CLOQ_WARN_MMX_CONFLICT")
        tags.append("MMx Conflict")
    else:
        tags.append("MMx Aligned")

    # Extra tags from existing row quality.
    if str(row.get("marq_move", row.get("move", ""))).lower() in {"toward pick", "toward", "positive_move"}:
        tags.append("Positive Move")
    if row.get("clv") in (None, "", "Pending") or str(row.get("clv_status", "")).lower() == "pending":
        tags.append("CLV Pending")
    sample_quality = str(_first(row, ["thinq_h2h_sample_quality", "h2h_sample_quality"]) or "").upper()
    if "LOW" in sample_quality:
        tags.append("Low H2H Sample")

    passed = not reasons
    score = _score(row, corq, thinq, marq, form_depth, stats_depth, gap)

    out = dict(row)
    out.update({
        "cloq_filter_version": FILTER_VERSION,
        "cloq_passed": passed,
        "cloq_score": score,
        "cloq_reasons": reasons,
        "cloq_warnings": warnings,
        "cloq_tags": sorted(set(tags)),
        "cloq_pick_odds": odds,
        "cloq_opponent_odds": opponent_odds,
        "cloq_odd_gap_pct": round(gap * 100.0, 2) if gap is not None else None,
        "cloq_corq_probability": corq,
        "cloq_thinq_probability": thinq,
        "cloq_marq_probability": marq,
        "cloq_form_depth": form_depth,
        "cloq_stats_depth": stats_depth,
        "cloq_mmx_conflict_pp": mmx_conflict,
    })
    return out


def filter_cloq_rows(rows: Iterable[Dict[str, Any]], config: Optional[CloQConfig] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    config = config or DEFAULT_CONFIG
    evaluated = [evaluate_cloq_row(row, config=config) for row in rows]
    passed = [row for row in evaluated if row.get("cloq_passed")]
    rejected = [row for row in evaluated if not row.get("cloq_passed")]

    passed.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)
    rejected.sort(key=lambda r: (r.get("cloq_score") or 0.0), reverse=True)

    reason_counts: Dict[str, int] = {}
    warning_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    for row in evaluated:
        for reason in row.get("cloq_reasons") or []:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for warning in row.get("cloq_warnings") or []:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
        for tag in row.get("cloq_tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    manifest = {
        "filter_version": FILTER_VERSION,
        "config": config_to_dict(config),
        "source_rows": len(evaluated),
        "passed_rows": len(passed),
        "rejected_rows": len(rejected),
        "reason_counts": dict(sorted(reason_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
    }
    return passed, rejected, manifest
