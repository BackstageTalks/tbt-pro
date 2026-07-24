# CORQ ranking - TOP7 is first 7 production-eligible rows from CORQ ranking
from __future__ import annotations
from typing import Any, Dict, Iterable, List

MIN_TOP_ODDS = 1.40
MAX_ODDS_GAP_PCT = 2.50
MIN_THINQ_CONFIDENCE = 0.15

# ALL stays broad/audit. TOP7 is production-only.
# These are the only match status values allowed into production TOP7.
TOP7_ALLOWED_STATUS_TYPES = {
    'notstarted',
    'not_started',
    'not started',
    'scheduled',
    'open',
    'pre',
    'prematch',
    'pre_match',
    'upcoming',
}
TOP7_BLOCKED_STATUS_TYPES = {
    'inprogress',
    'in_progress',
    'live',
    'started',
    'running',
    'finished',
    'ended',
    'closed',
    'cancelled',
    'canceled',
    'postponed',
    'interrupted',
    'retired',
    'walkover',
    'abandoned',
}
# If start time is very close, keep it out of TOP7 production output.
# This stays conservative and still leaves ALL broad.
TOP7_MIN_SECONDS_BEFORE_START = 0


def _as_float(value, default=None):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def _as_int(value, default=None):
    try:
        if value is None or value == '':
            return default
        return int(value)
    except Exception:
        return default


def _norm_text(value: Any) -> str:
    text = str(value or '').strip().lower()
    return text.replace('-', '_').replace(' ', '_')


def _status_type(rec: Dict[str, Any]) -> str:
    for key in ('status_type', 'statusType', 'match_status_type'):
        if rec.get(key):
            return _norm_text(rec.get(key))
    status = rec.get('status')
    if isinstance(status, dict):
        for key in ('type', 'description', 'status_type'):
            if status.get(key):
                return _norm_text(status.get(key))
    raw = rec.get('raw')
    if isinstance(raw, dict):
        raw_status = raw.get('status')
        if isinstance(raw_status, dict):
            for key in ('type', 'description'):
                if raw_status.get(key):
                    return _norm_text(raw_status.get(key))
    return ''


def _status_code(rec: Dict[str, Any]):
    for key in ('status_code', 'statusCode'):
        value = _as_int(rec.get(key))
        if value is not None:
            return value
    status = rec.get('status')
    if isinstance(status, dict):
        value = _as_int(status.get('code'))
        if value is not None:
            return value
    raw = rec.get('raw')
    if isinstance(raw, dict):
        raw_status = raw.get('status')
        if isinstance(raw_status, dict):
            value = _as_int(raw_status.get('code'))
            if value is not None:
                return value
    return None


def _is_status_top7_production_ready(rec: Dict[str, Any]) -> bool:
    status_type = _status_type(rec)
    status_code = _status_code(rec)

    if status_type in TOP7_BLOCKED_STATUS_TYPES:
        return False
    if status_type in TOP7_ALLOWED_STATUS_TYPES:
        return True

    # RapidAPI/Sofa style common codes seen in current data:
    # 100 = ended/finished, 8/10 = in progress periods.
    if status_code in {100, 8, 9, 10, 11, 12, 13}:
        return False

    # Unknown status must not enter production TOP7.
    return False


def _top7_status_reject_reason(rec: Dict[str, Any]) -> str:
    status_type = _status_type(rec) or 'unknown'
    status_code = _status_code(rec)
    if status_type in {'finished', 'ended'} or status_code == 100:
        return 'REJECT_TOP7_STATUS_FINISHED'
    if status_type in {'inprogress', 'in_progress', 'live', 'started', 'running'} or status_code in {8, 9, 10, 11, 12, 13}:
        return 'REJECT_TOP7_STATUS_INPROGRESS'
    if status_type in {'cancelled', 'canceled'}:
        return 'REJECT_TOP7_STATUS_CANCELLED'
    if status_type in {'postponed', 'interrupted', 'retired', 'walkover', 'abandoned'}:
        return 'REJECT_TOP7_STATUS_NOT_PLAYABLE'
    return f'REJECT_TOP7_STATUS_{status_type.upper()}'


def _match_key(rec: Dict[str, Any]) -> str:
    for key in ('event_id', 'eventId', 'match_id', 'match_key'):
        if rec.get(key):
            return str(rec.get(key))
    p1 = str(rec.get('player1') or rec.get('pick') or '').lower().strip()
    p2 = str(rec.get('player2') or rec.get('opponent') or '').lower().strip()
    names = sorted([p1, p2])
    return '::'.join(names + [str(rec.get('tournament') or '').lower().strip()])


def evaluate_eligibility(rec: Dict[str, Any]) -> Dict[str, Any]:
    corq_reasons: List[str] = []
    if rec.get('is_doubles'):
        corq_reasons.append('REJECT_DOUBLES')
    pick_odds = _as_float(rec.get('pick_odds') or rec.get('odds'))
    opponent_odds = _as_float(rec.get('opponent_odds'))
    if pick_odds is None:
        corq_reasons.append('REJECT_MISSING_ODDS')
    elif pick_odds < MIN_TOP_ODDS:
        corq_reasons.append('REJECT_LOW_ODDS')
    if opponent_odds is None:
        corq_reasons.append('REJECT_MISSING_OPPONENT_ODDS')
    gap = _as_float(rec.get('odds_gap_pct'))
    if gap is None and pick_odds and opponent_odds:
        gap = abs(pick_odds - opponent_odds) / max(min(pick_odds, opponent_odds), 0.0001)
    if gap is not None and gap > MAX_ODDS_GAP_PCT:
        corq_reasons.append('REJECT_EXTREME_ODDS_GAP')
    surface = str(rec.get('surface') or '').strip().lower()
    if not surface or surface == 'unknown':
        corq_reasons.append('REJECT_SURFACE_UNKNOWN')
    if not rec.get('thinq_available', True):
        corq_reasons.append('REJECT_NO_THINQ')
    thinq_conf = _as_float(rec.get('thinq_confidence'), 0.0) or 0.0
    if thinq_conf < MIN_THINQ_CONFIDENCE:
        corq_reasons.append('REJECT_LOW_THINQ_CONFIDENCE')

    out = dict(rec)
    prior_corq = list(out.get('corq_reject_reasons') or [])
    out['corq_reject_reasons'] = sorted(set(prior_corq + corq_reasons))
    out['eligible_for_corq'] = len(out['corq_reject_reasons']) == 0

    top7_reasons = list(out['corq_reject_reasons'])
    if not _is_status_top7_production_ready(out):
        top7_reasons.append(_top7_status_reject_reason(out))

    out['top7_reject_reasons'] = sorted(set(top7_reasons))
    out['eligible_for_top7'] = len(out['top7_reject_reasons']) == 0
    out['top7_status_type_normalized'] = _status_type(out) or None
    out['top7_status_code'] = _status_code(out)
    out['top7_filter_mode'] = 'PRODUCTION_NOT_STARTED_ONLY'
    return out


def dedupe_by_match(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        key = _match_key(rec)
        current = best.get(key)
        score = _as_float(rec.get('corq_adjusted_score'), 0.0) or 0.0
        cur_score = _as_float(current.get('corq_adjusted_score'), -1.0) if current else -1.0
        if current is None or score > cur_score:
            best[key] = dict(rec)
    return list(best.values())


def rank_corq(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evaluated = [evaluate_eligibility(r) for r in records]
    eligible = [r for r in evaluated if r.get('eligible_for_corq')]
    eligible = dedupe_by_match(eligible)
    ranked = sorted(
        eligible,
        key=lambda r: (
            _as_float(r.get('corq_adjusted_score'), 0.0) or 0.0,
            _as_float(r.get('corq_probability'), 0.0) or 0.0,
        ),
        reverse=True,
    )
    for idx, rec in enumerate(ranked, start=1):
        rec['corq_rank'] = idx
    return ranked


def make_all_match_view(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # ALL intentionally remains broad and includes TOP7 reject reasons for audit.
    evaluated = [evaluate_eligibility(r) for r in records]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in evaluated:
        grouped.setdefault(_match_key(r), []).append(r)
    result: List[Dict[str, Any]] = []
    for key, items in grouped.items():
        selected = sorted(
            items,
            key=lambda r: (
                _as_float(r.get('corq_adjusted_score'), 0.0) or 0.0,
                _as_float(r.get('corq_probability'), 0.0) or 0.0,
            ),
            reverse=True,
        )[0]
        selected = dict(selected)
        selected['corq_match_identity'] = key
        selected['corq_candidate_selected'] = True
        selected['corq_side_candidates'] = [
            {
                'pick': i.get('pick'),
                'opponent': i.get('opponent'),
                'corq_probability': i.get('corq_probability'),
                'corq_adjusted_score': i.get('corq_adjusted_score'),
                'eligible_for_corq': i.get('eligible_for_corq'),
                'eligible_for_top7': i.get('eligible_for_top7'),
                'corq_reject_reasons': i.get('corq_reject_reasons'),
                'top7_reject_reasons': i.get('top7_reject_reasons'),
            } for i in items
        ]
        result.append(selected)
    return sorted(result, key=lambda r: (_as_float(r.get('corq_adjusted_score'), 0.0) or 0.0), reverse=True)


def top7_from_ranking(ranked: List[Dict[str, Any]], top_n: int = 7) -> List[Dict[str, Any]]:
    # TOP7 is production-only. It never relaxes or backfills with live/finished rows.
    filtered = [r for r in ranked if evaluate_eligibility(r).get('eligible_for_top7')]
    result: List[Dict[str, Any]] = []
    for idx, rec in enumerate(filtered[:top_n], start=1):
        out = dict(rec)
        evaluated = evaluate_eligibility(out)
        out.update({
            'corq_source_rank': rec.get('corq_rank'),
            'corq_rank': idx,
            'top7_rank': idx,
            'eligible_for_top7': evaluated.get('eligible_for_top7'),
            'top7_reject_reasons': evaluated.get('top7_reject_reasons'),
            'top7_status_type_normalized': evaluated.get('top7_status_type_normalized'),
            'top7_status_code': evaluated.get('top7_status_code'),
            'top7_filter_mode': 'PRODUCTION_NOT_STARTED_ONLY',
        })
        result.append(out)
    return result
