# CORQ model - uses THINQ intelligence to produce ranking probability
from __future__ import annotations
from typing import Any, Dict, List


def _as_float(value, default=None):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class CorqModel:
    def score(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(record)
        thinq = out.get('thinq') if isinstance(out.get('thinq'), dict) else {}
        thinq_conf = _as_float(out.get('thinq_confidence') or thinq.get('confidence'), 0.0) or 0.0
        elo_edge = _as_float(out.get('thinq_elo_edge') or (thinq.get('edges') or {}).get('elo_edge'), 0.0) or 0.0
        h2h_edge = _as_float(out.get('thinq_h2h_edge') or (thinq.get('edges') or {}).get('h2h_edge'), 0.0) or 0.0
        pick_odds = _as_float(out.get('pick_odds') or out.get('odds'))
        opponent_odds = _as_float(out.get('opponent_odds'))

        # Core raw probability starts from neutral and uses THINQ intelligence.
        thinq_total_adjustment = clamp((elo_edge + h2h_edge) * clamp(thinq_conf, 0.0, 1.0), -0.10, 0.10)
        corq_raw_probability = clamp(0.50 + thinq_total_adjustment, 0.05, 0.95)

        # Add a small market sanity anchor from decimal odds when available, not as MARQ.
        if pick_odds and opponent_odds and pick_odds > 1 and opponent_odds > 1:
            imp_pick = (1.0 / pick_odds)
            imp_opp = (1.0 / opponent_odds)
            market_prob = imp_pick / (imp_pick + imp_opp)
            corq_probability = clamp(0.70 * corq_raw_probability + 0.30 * market_prob, 0.05, 0.95)
        else:
            corq_probability = corq_raw_probability

        # Ranking score: probability + small value/odds score - penalties.
        implied = (1.0 / pick_odds) if pick_odds and pick_odds > 1 else None
        value_edge = (corq_probability - implied) if implied is not None else 0.0
        value_bonus = clamp(value_edge * 0.25, -0.03, 0.03)
        risk_penalty = 0.0
        flags: List[str] = list(out.get('corq_risk_flags') or [])
        if thinq_conf < 0.15:
            risk_penalty += 0.03
            flags.append('LOW_THINQ_CONFIDENCE')
        if pick_odds and pick_odds < 1.40:
            risk_penalty += 0.08
            flags.append('LOW_ODDS')

        corq_adjusted_score = clamp(corq_probability + value_bonus - risk_penalty, 0.0, 1.0)

        out.update({
            'corq_raw_probability': round(corq_raw_probability, 4),
            'thinq_total_adjustment': round(thinq_total_adjustment, 4),
            'corq_probability': round(corq_probability, 4),
            'probability': round(corq_probability, 4),
            'corq_value_edge': round(value_edge, 4) if value_edge is not None else None,
            'corq_risk_penalty': round(risk_penalty, 4),
            'corq_adjusted_score': round(corq_adjusted_score, 4),
            'corq_risk_flags': sorted(set(flags)),
        })
        return out


# compatibility helper
def score_prediction(record: Dict[str, Any]) -> Dict[str, Any]:
    return CorqModel().score(record)
