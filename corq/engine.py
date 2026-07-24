"""Clean CORQ engine.

Flow:
fetch_matches -> normalize -> odds -> candidate expansion -> THINQ -> CORQ -> ranking -> web
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List
import importlib

from match_normalizer import normalize_match
from .odds import enrich_odds
from .candidates import build_pick_candidates
from .model import CorqModel
from .ranking import rank_predictions, top_n_from_ranked, select_one_prediction_per_match
from .outputs import publish_outputs


def _extract_match_list(data: Any) -> List[Dict[str, Any]] | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["matches", "events", "data", "fixtures", "items"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return None


def load_raw_matches() -> List[Dict[str, Any]]:
    fetch = importlib.import_module("fetch_matches")

    for name in ["get_today_matches", "fetch_matches", "get_matches", "load_matches", "main"]:
        func = getattr(fetch, name, None)
        if callable(func):
            data = func()
            matches = _extract_match_list(data)
            if matches is not None:
                return matches

    get_for_date = getattr(fetch, "get_matches_for_date", None)
    if callable(get_for_date):
        target_date = None
        betting_day = getattr(fetch, "betting_day", None)
        if callable(betting_day):
            try:
                target_date = betting_day()
            except Exception:
                target_date = None
        if target_date is not None:
            data = get_for_date(target_date)
            matches = _extract_match_list(data)
            if matches is not None:
                return matches

    available = [
        name for name in ["get_today_matches", "fetch_matches", "get_matches", "load_matches", "main", "get_matches_for_date"]
        if callable(getattr(fetch, name, None))
    ]
    raise RuntimeError(
        "fetch_matches.py does not expose a supported match loading function returning matches. "
        f"Callable candidates found: {available}"
    )


def build_thinq(match: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from thinq.service import ThinqService
        return ThinqService().analyse_match(match)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "confidence": 0.0,
            "surface": {
                "surface": match.get("surface") or "Unknown",
                "surface_raw": match.get("surface_raw") or match.get("surface"),
                "surface_source": "thinq_runtime_error_fallback",
                "surface_model_bucket": "Overall",
                "thinq_selected_elo_type": "overall_elo",
            },
            "edges": {},
            "h2h": {
                "status": "ERROR_NON_BLOCKING",
                "edge": 0.0,
                "confidence": 0.0,
                "reason": str(exc),
                "flags": ["H2H_SKIPPED_THINQ_RUNTIME_ERROR"],
            },
            "flags": ["THINQ_RUNTIME_ERROR"],
        }


def _flatten_thinq(candidate: Dict[str, Any], thinq: Dict[str, Any]) -> None:
    surface = thinq.get("surface") or {}
    candidate["surface"] = surface.get("surface") or candidate.get("surface") or "Unknown"
    candidate["surface_raw"] = surface.get("surface_raw")
    candidate["surface_source"] = surface.get("surface_source")
    candidate["surface_model_bucket"] = surface.get("surface_model_bucket")
    candidate["thinq_selected_elo_type"] = surface.get("thinq_selected_elo_type")
    candidate["thinq_available"] = bool(thinq.get("available"))
    candidate["thinq_error"] = thinq.get("error")
    candidate["thinq_confidence"] = thinq.get("confidence")
    candidate["thinq_edges"] = thinq.get("edges") or {}
    h2h = thinq.get("h2h") or {}
    candidate["thinq_h2h_status"] = h2h.get("status")
    candidate["thinq_h2h_edge"] = h2h.get("edge")
    candidate["thinq_h2h_source"] = h2h.get("source")
    candidate["thinq_h2h_confidence"] = h2h.get("confidence")


def build_predictions(raw_matches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    model = CorqModel()
    predictions: List[Dict[str, Any]] = []
    for raw in raw_matches:
        base_match = normalize_match(raw)
        base_match = enrich_odds(base_match)
        candidates = build_pick_candidates(base_match)
        for candidate in candidates:
            thinq = build_thinq(candidate)
            candidate["thinq"] = thinq
            _flatten_thinq(candidate, thinq)
            predictions.append(model.score(candidate, thinq))
    return predictions


def main() -> None:
    raw_matches = load_raw_matches()
    candidate_predictions = build_predictions(raw_matches)

    # ALL is now match-level: one selected CORQ side per real match, with side audit kept in JSON.
    all_predictions = select_one_prediction_per_match(candidate_predictions)

    ranked = rank_predictions(candidate_predictions)
    top7 = top_n_from_ranked(ranked, 7)
    publish_outputs(all_predictions, ranked, top7)
    try:
        from web.render import render_all_pages
        render_all_pages(all_predictions=all_predictions, corq_predictions=ranked, top7=top7)
    except Exception as exc:
        print(f"WEB_RENDER_NON_BLOCKING_ERROR: {exc}")
    print(
        "CORQ CLEAN RUNTIME OK: "
        f"matches={len(raw_matches)} candidates={len(candidate_predictions)} "
        f"all_matches={len(all_predictions)} ranked={len(ranked)} top7={len(top7)}"
    )


if __name__ == "__main__":
    main()
