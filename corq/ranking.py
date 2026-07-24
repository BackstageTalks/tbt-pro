# CORQ ranking - TOP7 is first 7 from CORQ ranking
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Tuple

MIN_TOP_ODDS = 1.40
MAX_ODDS_GAP_PCT = 2.50
MIN_THINQ_CONFIDENCE = 0.15


def _as_float(value, default=None):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def _match_key(rec: Dict[str, Any]) -> str:
    for key in ('event_id', 'eventId', 'match_id', 'match_key'):
        if rec.get(key):
            return str(rec.get(key))
    p1 = str(rec.get('player1') or rec.get('pick') or '').lower().strip()
    p2 = str(rec.get('player2') or rec.get('opponent') or '').lower().strip()
    names = sorted([p1, p2])
    return '::'.join(names + [str(rec.get('tournament') or '').lower().strip()])


def evaluate_eligibility(rec: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    if rec.get('is_doubles'):
        reasons.append('REJECT_DOUBLES')
    pick_odds = _as_float(rec.get('pick_odds') or rec.get('odds'))
    opponent_odds = _as_float(rec.get('opponent_odds'))
    if pick_odds is None:
        reasons.append('REJECT_MISSING_ODDS')
    elif pick_odds < MIN_TOP_ODDS:
        reasons.append('REJECT_LOW_ODDS')
    if opponent_odds is None:
        reasons.append('REJECT_MISSING_OPPONENT_ODDS')
    gap = _as_float(rec.get('odds_gap_pct'))
    if gap is None and pick_odds and opponent_odds:
        gap = abs(pick_odds - opponent_odds) / max(min(pick_odds, opponent_odds), 0.0001)
    if gap is not None and gap > MAX_ODDS_GAP_PCT:
        reasons.append('REJECT_EXTREME_ODDS_GAP')
    surface = str(rec.get('surface') or '').strip().lower()
    if not surface or surface == 'unknown':
        reasons.append('REJECT_SURFACE_UNKNOWN')
    if not rec.get('thinq_available', True):
        reasons.append('REJECT_NO_THINQ')
    thinq_conf = _as_float(rec.get('thinq_confidence'), 0.0) or 0.0
    if thinq_conf < MIN_THINQ_CONFIDENCE:
        reasons.append('REJECT_LOW_THINQ_CONFIDENCE')

    out = dict(rec)
    out['corq_reject_reasons'] = sorted(set(list(out.get('corq_reject_reasons') or []) + reasons))
    out['eligible_for_corq'] = len(out['corq_reject_reasons']) == 0
    out['eligible_for_top7'] = out['eligible_for_corq']
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
    ranked = sorted(eligible, key=lambda r: (_as_float(r.get('corq_adjusted_score'), 0.0) or 0.0, _as_float(r.get('corq_probability'), 0.0) or 0.0), reverse=True)
    for idx, rec in enumerate(ranked, start=1):
        rec['corq_rank'] = idx
    return ranked


def make_all_match_view(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evaluated = [evaluate_eligibility(r) for r in records]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in evaluated:
        grouped.setdefault(_match_key(r), []).append(r)
    result: List[Dict[str, Any]] = []
    for key, items in grouped.items():
        selected = sorted(items, key=lambda r: (_as_float(r.get('corq_adjusted_score'), 0.0) or 0.0, _as_float(r.get('corq_probability'), 0.0) or 0.0), reverse=True)[0]
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
                'corq_reject_reasons': i.get('corq_reject_reasons'),
            } for i in items
        ]
        result.append(selected)
    return sorted(result, key=lambda r: (_as_float(r.get('corq_adjusted_score'), 0.0) or 0.0), reverse=True)


def top7_from_ranking(ranked: List[Dict[str, Any]], top_n: int = 7) -> List[Dict[str, Any]]:
    return ranked[:top_n]
