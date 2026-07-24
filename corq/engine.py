"""CORQ daily runtime.

Broad runtime version. The key update here is THINQ orientation:
when a candidate side has pick/opponent, THINQ receives that side so ELO/H2H
edges are calculated for the candidate pick, not only for player1/home.
"""

from __future__ import annotations

import argparse
import inspect
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from corq.candidates import load_candidates
from corq.model import build_corq_prediction
from corq.outputs import save_all, save_run_manifest, save_top7
from corq.ranking import make_all_match_view, rank_corq, top7_from_ranking


def _load_thinq_service():
    try:
        from thinq.service import ThinqService  # type: ignore
        return ThinqService()
    except Exception:
        try:
            from thinq.thinq_service import ThinqService  # type: ignore
            return ThinqService()
        except Exception:
            return None


def _call_build_match_features(thinq_service: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    method = thinq_service.build_match_features
    try:
        signature = inspect.signature(method)
        accepted = set(signature.parameters.keys())
        filtered = {key: value for key, value in payload.items() if key in accepted}
        return method(**filtered)
    except Exception:
        # Fallback for old fixed signatures.
        return method(
            player1=payload.get("player1"),
            player2=payload.get("player2"),
            surface=payload.get("surface"),
            level=payload.get("level"),
            event_id=payload.get("event_id"),
            best_of=payload.get("best_of") or 3,
        )


def _enrich_with_thinq(record: Dict[str, Any], thinq_service: Any) -> Dict[str, Any]:
    if record.get("thinq") or thinq_service is None:
        return record
    player1 = record.get("player1")
    player2 = record.get("player2")
    if not player1 or not player2:
        return record
    try:
        payload = {
            "player1": str(player1),
            "player2": str(player2),
            "pick": record.get("pick"),
            "opponent": record.get("opponent"),
            "surface": record.get("surface"),
            "level": record.get("level"),
            "tournament_url": record.get("tournament_url"),
            "tour_type": record.get("tour_type"),
            "as_of_date": record.get("date") or date.today().isoformat(),
            "event_id": record.get("event_id") or record.get("eventId"),
            "player1_id": record.get("player1_id"),
            "player2_id": record.get("player2_id"),
            "tournament_id": record.get("tournament_id"),
            "best_of": int(record.get("best_of") or 3),
            "save_snapshot": False,
        }
        thinq = _call_build_match_features(thinq_service, payload)
        enriched = dict(record)
        enriched["thinq"] = thinq
        enriched["thinq_confidence"] = thinq.get("confidence") or thinq.get("thinq_confidence")
        return enriched
    except Exception as exc:
        enriched = dict(record)
        enriched["thinq_available"] = False
        enriched["thinq_error"] = str(exc)
        return enriched


def run_daily(input_path: Optional[str] = None, output_root: str = "outputs", run_date: Optional[str] = None) -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    candidates = load_candidates(input_path)
    thinq_service = _load_thinq_service()
    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        enriched = _enrich_with_thinq(candidate, thinq_service)
        scored.append(build_corq_prediction(enriched))
    all_view = make_all_match_view(scored)
    ranking = rank_corq(scored)
    top7 = top7_from_ranking(ranking, top_n=7)
    all_paths = save_all(all_view, run_date=run_date, output_root=output_root)
    top7_paths = save_top7(top7, run_date=run_date, output_root=output_root)
    manifest = {
        "runtime": "corq_daily_thinq_elo_h2h",
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date or date.today().isoformat(),
        "input_path": input_path,
        "candidate_count": len(candidates),
        "scored_count": len(scored),
        "all_count": len(all_view),
        "ranked_count": len(ranking),
        "top7_count": len(top7),
        "thinq_service_available": thinq_service is not None,
        "outputs": {"all": all_paths, "top7": top7_paths},
    }
    manifest_paths = save_run_manifest(manifest, run_date=run_date, output_root=output_root)
    manifest["outputs"]["manifest"] = manifest_paths
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CORQ daily runtime")
    parser.add_argument("--input", dest="input_path", default=None, help="Optional path to candidates/matches JSON")
    parser.add_argument("--output-root", default="outputs", help="Output root directory")
    parser.add_argument("--date", dest="run_date", default=None, help="Run date YYYY-MM-DD")
    args = parser.parse_args()
    manifest = run_daily(input_path=args.input_path, output_root=args.output_root, run_date=args.run_date)
    print("CORQ runtime finished")
    print(f"Candidates: {manifest['candidate_count']}")
    print(f"ALL: {manifest['all_count']}")
    print(f"TOP7: {manifest['top7_count']}")


if __name__ == "__main__":
    main()
