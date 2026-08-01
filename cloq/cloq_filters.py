"""CloQ filters.

CloQ is a close-odds quality layer over enriched CorQ rows. It is not a new
prediction model. It selects and ranks already enriched rows using odds range,
model support, market support, model-market alignment and data depth.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional
import math


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else default
    text = str(value).strip().replace('%', '')
    if text in {'', '-', '--', 'N/A', 'None', 'null'}:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _pct_to_unit(value: Any) -> Optional[float]:
    number = _to_float(value)
    if number is None:
        return None
    return number / 100.0 if number > 1.0 else number


def _first_float(row: Dict[str, Any], keys: Iterable[str]) -> Optional[float]:
    for key in keys:
        val = _to_float(row.get(key))
        if val is not None:
            return val
    return None


def _first_unit(row: Dict[str, Any], keys: Iterable[str]) -> Optional[float]:
    for key in keys:
        val = _pct_to_unit(row.get(key))
        if val is not None:
            return val
    return None


def _norm_status(row: Dict[str, Any]) -> str:
    for key in ('status_type', 'status', 'match_status', 'event_status'):
        value = row.get(key)
        if value:
            return str(value).strip().lower().replace(' ', '_')
    code = row.get('status_code')
    if str(code) == '0':
        return 'notstarted'
    return 'unknown'


def _is_prematch(row: Dict[str, Any]) -> bool:
    return _norm_status(row) in {'notstarted', 'not_started', 'scheduled', 'prematch', 'upcoming', 'unknown'}


def _is_singles(row: Dict[str, Any]) -> bool:
    if bool(row.get('is_doubles')):
        return False
    raw = row.get('raw') or {}
    filters = raw.get('eventFilters') if isinstance(raw, dict) else None
    if isinstance(filters, dict):
        category = filters.get('category')
        if isinstance(category, list) and any(str(x).lower() == 'doubles' for x in category):
            return False
    return True


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
    max_model_market_gap_pp: float = 18.0
    require_prematch: bool = True
    require_singles: bool = True
    allow_clv_pending: bool = True
    max_rows: int = 20
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def odd_gap_pct(row: Dict[str, Any]) -> Optional[float]:
    pick_odds = _first_float(row, ['pick_odds', 'odds', 'price', 'pick_price'])
    opp_odds = _first_float(row, ['opponent_odds', 'opp_odds', 'opponent_price'])
    if pick_odds and opp_odds and pick_odds > 0 and opp_odds > 0:
        return abs(pick_odds - opp_odds) / min(pick_odds, opp_odds)
    existing = _to_float(row.get('odds_gap_pct'))
    if existing is None:
        return None
    return existing if existing <= 1 else existing / 100.0


def extract_cloq_values(row: Dict[str, Any]) -> Dict[str, Any]:
    corq = _first_unit(row, ['corq_calibrated_probability', 'corq_probability', 'estimated_probability', 'probability', 'model_probability', 'corq'])
    thinq = _first_unit(row, ['thinq_pick_probability', 'thinq_probability', 'thinq_prob', 'thinq_win_probability'])
    marq = _first_unit(row, ['corq_market_probability', 'marq_market_probability', 'marq_crowd_pick_pct', 'pick_marq_probability', 'marq_pick_probability'])
    form_depth = _first_unit(row, ['form_data_depth', 'f_data_depth', 'recent_form_depth'])
    stats_depth = _first_unit(row, ['s_data_depth', 'sets_games_data_depth', 'stats_data_depth'])
    odds = _first_float(row, ['pick_odds', 'odds', 'price'])
    gap = odd_gap_pct(row)
    clv = _first_float(row, ['marq_internal_clv_pp', 'internal_clv_pp', 'clv_pp', 'corq_clv_pp'])
    move = row.get('marq_move_signal') or row.get('marq_internal_move_signal') or row.get('move') or ''
    mm_gap = abs(thinq - marq) * 100.0 if thinq is not None and marq is not None else None
    return {
        'odds': odds,
        'odd_gap_pct': gap,
        'corq_probability': corq,
        'thinq_probability': thinq,
        'marq_probability': marq,
        'form_data_depth': form_depth,
        'stats_data_depth': stats_depth,
        'clv_pp': clv,
        'move_signal': str(move),
        'model_market_gap_pp': mm_gap,
        'status': _norm_status(row),
        'is_prematch': _is_prematch(row),
        'is_singles': _is_singles(row),
    }


def cloq_score(values: Dict[str, Any], warnings: Optional[List[str]] = None, passed: bool = True) -> float:
    warnings = warnings or []
    corq = values.get('corq_probability') or 0.50
    thinq = values.get('thinq_probability') or 0.50
    marq = values.get('marq_probability') or 0.50
    form_depth = values.get('form_data_depth') or 0.0
    stats_depth = values.get('stats_data_depth') or 0.0
    gap = values.get('odd_gap_pct')
    if gap is None:
        gap_quality = 0.50
    else:
        gap_quality = max(0.0, 1.0 - abs(gap - 0.175) / 0.175)
    move_quality = 0.50
    move_signal = str(values.get('move_signal') or '').lower()
    if 'toward' in move_signal or 'with' in move_signal:
        move_quality = 0.75
    elif 'against' in move_signal:
        move_quality = 0.25
    clv = values.get('clv_pp')
    if clv is not None:
        move_quality = max(0.0, min(1.0, 0.50 + float(clv) / 10.0))
    depth = 0.65 * form_depth + 0.35 * stats_depth
    score = (0.30 * corq + 0.20 * thinq + 0.20 * marq + 0.10 * depth + 0.10 * gap_quality + 0.10 * move_quality) * 100.0
    score -= min(12.0, len(warnings) * 2.0)
    if not passed:
        score -= 15.0
    return round(max(0.0, min(100.0, score)), 1)


def evaluate_row(row: Dict[str, Any], config: CloQConfig = CloQConfig()) -> Dict[str, Any]:
    values = extract_cloq_values(row)
    reasons: List[str] = []
    warnings: List[str] = []
    tags: List[str] = []
    odds = values['odds']
    if odds is None:
        reasons.append('CLOQ_REJECT_MISSING_ODDS')
    elif odds < config.min_odds:
        reasons.append('CLOQ_REJECT_ODDS_BELOW_MIN')
    elif odds > config.max_odds:
        reasons.append('CLOQ_REJECT_ODDS_ABOVE_MAX')
    else:
        tags.append('Close Odds')
    gap = values['odd_gap_pct']
    if gap is None:
        warnings.append('CLOQ_WARN_MISSING_ODD_GAP')
    elif gap < config.min_odd_gap_pct:
        reasons.append('CLOQ_REJECT_ODD_GAP_TOO_SMALL')
    elif gap > config.max_odd_gap_pct:
        reasons.append('CLOQ_REJECT_ODD_GAP_TOO_WIDE')
    else:
        tags.append('Balanced Market')
    if config.require_prematch and not values['is_prematch']:
        reasons.append('CLOQ_REJECT_NOT_PREMATCH')
    if config.require_singles and not values['is_singles']:
        reasons.append('CLOQ_REJECT_NOT_SINGLES')
    corq = values['corq_probability']
    if corq is None:
        reasons.append('CLOQ_REJECT_MISSING_CORQ')
    elif corq < config.min_corq_probability:
        reasons.append('CLOQ_REJECT_CORQ_BELOW_MIN')
    thinq = values['thinq_probability']
    if thinq is None:
        warnings.append('CLOQ_WARN_MISSING_THINQ')
    elif thinq < config.min_thinq_probability:
        reasons.append('CLOQ_REJECT_THINQ_BELOW_MIN')
    marq = values['marq_probability']
    if marq is None:
        warnings.append('CLOQ_WARN_MISSING_MARQ')
    elif marq < config.min_marq_probability:
        reasons.append('CLOQ_REJECT_MARQ_BELOW_MIN')
    else:
        tags.append('MarQ Support')
    form_depth = values['form_data_depth']
    if form_depth is None:
        warnings.append('CLOQ_WARN_MISSING_FORM_DEPTH')
    elif form_depth < config.min_form_depth:
        reasons.append('CLOQ_REJECT_LOW_FORM_DEPTH')
    stats_depth = values['stats_data_depth']
    if stats_depth is None:
        warnings.append('CLOQ_WARN_MISSING_STATS_DEPTH')
    elif stats_depth < config.min_stats_depth:
        warnings.append('CLOQ_WARN_LOW_STATS_DEPTH')
    mm_gap = values['model_market_gap_pp']
    if mm_gap is not None:
        if mm_gap <= config.max_model_market_gap_pp:
            tags.append('MMx Aligned')
        else:
            warnings.append('CLOQ_WARN_MMX_CONFLICT')
            tags.append('MMx Conflict')
    move_signal = values['move_signal'].lower()
    if 'against' in move_signal:
        warnings.append('CLOQ_WARN_MARKET_MOVE_AGAINST')
    elif 'toward' in move_signal or 'with' in move_signal:
        tags.append('Market With Pick')
    clv = values['clv_pp']
    if clv is None and config.allow_clv_pending:
        tags.append('CLV Pending')
    elif clv is not None and clv >= 1.0:
        tags.append('Positive CLV')
    elif clv is not None and clv <= -1.0:
        warnings.append('CLOQ_WARN_NEGATIVE_CLV')
    passed = not reasons
    return {
        'cloq_passed': passed,
        'cloq_score': cloq_score(values, warnings=warnings, passed=passed),
        'cloq_reject_reasons': reasons,
        'cloq_warnings': warnings,
        'cloq_tags': tags,
        'cloq_values': values,
        'cloq_config': config.to_dict(),
    }


def apply_cloq(rows: Iterable[Dict[str, Any]], config: CloQConfig = CloQConfig()) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        enriched = dict(row)
        enriched.update(evaluate_row(row, config=config))
        out.append(enriched)
    out.sort(key=lambda r: (bool(r.get('cloq_passed')), float(r.get('cloq_score') or 0.0)), reverse=True)
    return out


def select_cloq(rows: Iterable[Dict[str, Any]], config: CloQConfig = CloQConfig()) -> List[Dict[str, Any]]:
    return [r for r in apply_cloq(rows, config) if r.get('cloq_passed')][:config.max_rows]
