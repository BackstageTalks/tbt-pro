"""CORQ daily runtime.

Current MVP:
1. Load match candidates from local JSON.
2. Enrich missing THINQ data if thinq.service.ThinqService exists.
3. Build CORQ score, edge and adjusted score.
4. Write ALL and TOP7 JSON outputs.

Next step after this MVP:
- connect RapidAPI PRO fixture/odds loader inside corq.candidates or thinq.loaders
"""

from __future__ import annotations

import argparse
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


def _enrich_with_thinq(record: Dict[str, Any], thinq_service: Any) -> Dict[str, Any]:
    if record.get("thinq") or thinq_service is None:
        return record

    player1 = record.get("player1")
    player2 = record.get("player2")
    if not player1 or not player2:
        return record

    try:
        thinq = thinq_service.build_match_features(
            player1=str(player1),
            player2=str(player2),
            surface=record.get("surface"),
            level=record.get("level"),
            tournament_url=record.get("tournament_url"),
            tour_type=record.get("tour_type"),
            as_of_date=record.get("date") or date.today().isoformat(),
            event_id=record.get("event_id") or record.get("eventId"),
            player1_id=record.get("player1_id"),
            player2_id=record.get("player2_id"),
            tournament_id=record.get("tournament_id"),
            best_of=int(record.get("best_of") or 3),
            save_snapshot=False,
        )
        enriched = dict(record)
        enriched["thinq"] = thinq
        enriched["thinq_confidence"] = thinq.get("confidence")
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
        "runtime": "corq_daily_mvp",
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
    parser = argparse.ArgumentParser(description="Run CORQ daily MVP runtime")
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
