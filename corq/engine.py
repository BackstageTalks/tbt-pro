"""CORQ daily runtime with side safety.

Hard rule:
- player1 = home/API first side
- player2 = away/API second side
- pick/opponent are derived from pick_side by corq.sides
- THINQ receives pick/opponent and side audit for candidate-side calculations
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
from corq.sides import repair_candidate_side, build_side_audit


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
        return method(
            player1=payload.get("player1"),
            player2=payload.get("player2"),
            surface=payload.get("surface"),
            level=payload.get("level"),
            event_id=payload.get("event_id"),
            best_of=payload.get("best_of") or 3,
        )




def _raw_team_id(record: Dict[str, Any], side: str) -> Any:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    key = "homeTeam" if side == "HOME" else "awayTeam"
    team = raw.get(key) if isinstance(raw.get(key), dict) else {}
    if team.get("id") not in (None, ""):
        return team.get("id")
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return info.get("id")

def _enrich_with_thinq(record: Dict[str, Any], thinq_service: Any) -> Dict[str, Any]:
    safe_record = repair_candidate_side(record)
    safe_record["side_audit"] = build_side_audit(safe_record)

    if safe_record.get("thinq") or thinq_service is None:
        return safe_record
    player1 = safe_record.get("player1")
    player2 = safe_record.get("player2")
    if not player1 or not player2:
        return safe_record
    try:
        payload = {
            "player1": str(player1),
            "player2": str(player2),
            "pick": safe_record.get("pick"),
            "opponent": safe_record.get("opponent"),
            "pick_side": safe_record.get("pick_side"),
            "opponent_side": safe_record.get("opponent_side"),
            "side_audit": safe_record.get("side_audit"),
            "surface": safe_record.get("surface"),
            "level": safe_record.get("level"),
            "tournament_url": safe_record.get("tournament_url"),
            "tour_type": safe_record.get("tour_type"),
            "as_of_date": safe_record.get("date") or date.today().isoformat(),
            "event_id": safe_record.get("event_id") or safe_record.get("eventId"),
            "player1_id": safe_record.get("player1_id") or _raw_team_id(safe_record, "HOME"),
            "player2_id": safe_record.get("player2_id") or _raw_team_id(safe_record, "AWAY"),
            "tournament_id": safe_record.get("tournament_id"),
            "best_of": int(safe_record.get("best_of") or 3),
            "save_snapshot": False,
        }
        thinq = _call_build_match_features(thinq_service, payload)
        enriched = dict(safe_record)
        enriched["thinq"] = thinq
        enriched["thinq_side"] = thinq.get("thinq_side") or safe_record.get("side_audit")
        enriched["thinq_confidence"] = thinq.get("confidence") or thinq.get("thinq_confidence")
        return enriched
    except Exception as exc:
        enriched = dict(safe_record)
        enriched["thinq_available"] = False
        enriched["thinq_error"] = str(exc)
        return enriched


def run_daily(input_path: Optional[str] = None, output_root: str = "outputs", run_date: Optional[str] = None) -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    raw_candidates = load_candidates(input_path)
    candidates = [repair_candidate_side(candidate) for candidate in raw_candidates]
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
        "runtime": "corq_daily_side_safe",
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
        "side_safety": {
            "player1_definition": "HOME_API_FIRST_SIDE",
            "player2_definition": "AWAY_API_SECOND_SIDE",
            "pick_definition": "DERIVED_FROM_PICK_SIDE",
        },
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
