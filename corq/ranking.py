"""CORQ ranking.

TOP7 is simply the first 7 eligible rows from CORQ ranking.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from corq.rules import apply_risk_adjustments, evaluate_eligibility, as_float


def match_key(record: Dict[str, Any]) -> str:
    for key in ("event_id", "eventId", "match_id", "match_key"):
        if record.get(key):
            return str(record.get(key))
    p1 = str(record.get("player1") or record.get("pick") or "").lower().strip()
    p2 = str(record.get("player2") or record.get("opponent") or "").lower().strip()
    tournament = str(record.get("tournament") or "").lower().strip()
    names = sorted([p1, p2])
    return "::".join(names + [tournament])


def dedupe_by_match(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for record in records:
        key = match_key(record)
        current = best.get(key)
        score = as_float(record.get("corq_adjusted_score"), 0.0) or 0.0
        current_score = as_float(current.get("corq_adjusted_score"), -1.0) if current else -1.0
        if current is None or score > current_score:
            best[key] = dict(record)
    return list(best.values())


def prepare_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared = []
    for record in records:
        adjusted = apply_risk_adjustments(record)
        evaluated = evaluate_eligibility(adjusted)
        prepared.append(evaluated)
    return prepared


def rank_corq(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared = prepare_records(records)
    eligible = [row for row in prepared if row.get("eligible_for_corq")]
    eligible = dedupe_by_match(eligible)
    eligible.sort(
        key=lambda row: (
            as_float(row.get("corq_adjusted_score"), 0.0) or 0.0,
            as_float(row.get("corq_score"), 0.0) or 0.0,
            as_float(row.get("corq_edge"), 0.0) or 0.0,
        ),
        reverse=True,
    )
    for idx, row in enumerate(eligible, start=1):
        row["corq_rank"] = idx
    return eligible


def make_all_match_view(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared = prepare_records(records)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in prepared:
        grouped.setdefault(match_key(row), []).append(row)

    result: List[Dict[str, Any]] = []
    for key, items in grouped.items():
        selected = sorted(
            items,
            key=lambda row: (
                as_float(row.get("corq_adjusted_score"), 0.0) or 0.0,
                as_float(row.get("corq_score"), 0.0) or 0.0,
            ),
            reverse=True,
        )[0]
        selected = dict(selected)
        selected["corq_match_identity"] = key
        selected["corq_candidate_selected"] = True
        selected["corq_side_candidates"] = [
            {
                "pick": item.get("pick"),
                "opponent": item.get("opponent"),
                "odds": item.get("odds"),
                "corq_score": item.get("corq_score"),
                "corq_edge": item.get("corq_edge"),
                "corq_adjusted_score": item.get("corq_adjusted_score"),
                "eligible_for_corq": item.get("eligible_for_corq"),
                "corq_reject_reasons": item.get("corq_reject_reasons"),
            }
            for item in items
        ]
        result.append(selected)

    result.sort(key=lambda row: as_float(row.get("corq_adjusted_score"), 0.0) or 0.0, reverse=True)
    return result


def top7_from_ranking(ranked: List[Dict[str, Any]], top_n: int = 7) -> List[Dict[str, Any]]:
    return ranked[:top_n]
