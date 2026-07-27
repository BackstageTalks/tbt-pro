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
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from corq.candidates import load_candidates
from corq.model import build_corq_prediction
from corq.outputs import save_all, save_run_manifest, save_top7
from corq.ranking import make_all_match_view, rank_corq, top7_from_ranking
from corq.sides import build_side_audit, repair_candidate_side


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


def _load_ta_rankings() -> Dict[str, Any]:
    try:
        from thinq.loaders.ranking_loader import load_rankings  # type: ignore
        data = load_rankings()
        return data if isinstance(data, dict) else {"players": {}}
    except Exception:
        return {"players": {}}


def _enrich_with_ta_rankings(record: Dict[str, Any], rankings: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from thinq.loaders.ranking_loader import enrich_row_with_ta_ranks  # type: ignore
        return enrich_row_with_ta_ranks(record, rankings=rankings)
    except Exception:
        record.setdefault("pick_ta_rank_display", "(X)")
        record.setdefault("opponent_ta_rank_display", "(X)")
        return record



def _enrich_with_ta_profile_context(record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from thinq.loaders.ta_profile_loader import build_match_ta_context  # type: ignore
        ctx = build_match_ta_context(
            str(record.get("pick") or record.get("player") or record.get("player1") or ""),
            str(record.get("opponent") or record.get("opp") or record.get("player2") or ""),
            str(record.get("surface") or record.get("surface_raw") or ""),
        )
        if isinstance(ctx, dict):
            record.update(ctx)
            record["ta_context"] = ctx
            return record
    except Exception:
        pass
    defaults = {
        "ta_status": "N/A",
        "ta_pick_status": "N/A",
        "ta_opp_status": "N/A",
        "ta_pick_set_pct": None,
        "ta_opp_set_pct": None,
        "ta_pick_game_pct": None,
        "ta_opp_game_pct": None,
        "ta_pick_tb_split": None,
        "ta_opp_tb_split": None,
        "ta_pick_ace_pct": None,
        "ta_opp_ace_pct": None,
        "ta_pick_surface_dr": None,
        "ta_opp_surface_dr": None,
        "ta_pick_rpw_pct": None,
        "ta_opp_rpw_pct": None,
        "ta_pick_depth": None,
        "ta_opp_depth": None,
        "pick_aces_line": None,
        "opponent_aces_line": None,
        "total_aces_line": None,
        "aces_status": "N/A",
        "ta_winner_decision": "N/A",
        "ta_winner_read": "N/A",
        "ta_sets_decision": "N/A",
        "ta_games_decision": "N/A",
        "ta_tb_decision": "N/A",
        "ta_serve_return_pattern": "N/A",
        "ta_match_shape": "N/A",
        "ta_depth_label": "N/A",
        "ta_decision_confidence": 0.0,
        "ta_decision_notes": [],
    }
    for key, value in defaults.items():
        record.setdefault(key, value)
    return record


def _call_build_match_features(thinq_service: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    method = thinq_service.build_match_features
    try:
        signature = inspect.signature(method)
        accepted = set(signature.parameters.keys())
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        filtered = dict(payload) if accepts_kwargs else {key: value for key, value in payload.items() if key in accepted}
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


def _nested_get(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _raw_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = record.get("raw")
    return raw if isinstance(raw, dict) else {}


def _event_custom_id(record: Dict[str, Any]) -> Optional[str]:
    raw = _raw_dict(record)
    candidates = [
        record.get("event_custom_id"),
        record.get("custom_id"),
        record.get("customId"),
        raw.get("customId"),
        raw.get("custom_id"),
        _nested_get(record, "event", "customId"),
        _nested_get(record, "match", "customId"),
    ]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def _raw_team_id(record: Dict[str, Any], side: str) -> Any:
    raw = _raw_dict(record)
    key = "homeTeam" if side == "HOME" else "awayTeam"
    team = raw.get(key) if isinstance(raw.get(key), dict) else {}
    if team.get("id") not in (None, ""):
        return team.get("id")
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return info.get("id")


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _enrich_with_thinq(record: Dict[str, Any], thinq_service: Any) -> Dict[str, Any]:
    safe_record = repair_candidate_side(record)
    safe_record["side_audit"] = build_side_audit(safe_record)

    if thinq_service is None:
        safe_record["thinq"] = {"available": False, "error": "THINQ_SERVICE_UNAVAILABLE"}
        safe_record["thinq_available"] = False
        safe_record["thinq_error"] = "THINQ_SERVICE_UNAVAILABLE"
        safe_record["thinq_flags"] = ["THINQ_SERVICE_UNAVAILABLE"]
        return safe_record

    raw = _raw_dict(safe_record)
    event_custom_id = _event_custom_id(safe_record)
    event_id = _first_present(
        safe_record.get("event_id"),
        safe_record.get("match_id"),
        safe_record.get("id"),
        raw.get("id"),
    )

    payload = {
        "player1": safe_record.get("player1"),
        "player2": safe_record.get("player2"),
        "surface": safe_record.get("surface") or safe_record.get("surface_raw") or raw.get("groundType"),
        "level": safe_record.get("level") or safe_record.get("category") or _nested_get(raw, "tournament", "category", "name"),
        "tournament_url": safe_record.get("tournament_url"),
        "tour_type": safe_record.get("tour_type") or safe_record.get("gender") or _nested_get(raw, "homeTeam", "gender") or _nested_get(raw, "awayTeam", "gender"),
        "as_of_date": safe_record.get("date") or safe_record.get("match_date") or safe_record.get("match_start") or safe_record.get("start_time"),
        "event_id": event_id,
        "event_custom_id": event_custom_id,
        "custom_id": event_custom_id,
        "customId": event_custom_id,
        "player1_id": _first_present(safe_record.get("player1_id"), safe_record.get("player1Id"), _raw_team_id(safe_record, "HOME")),
        "player2_id": _first_present(safe_record.get("player2_id"), safe_record.get("player2Id"), _raw_team_id(safe_record, "AWAY")),
        "tournament_id": _first_present(safe_record.get("tournament_id"), safe_record.get("tournamentId"), _nested_get(raw, "tournament", "id")),
        "best_of": safe_record.get("best_of") or 3,
        "pick": safe_record.get("pick"),
        "opponent": safe_record.get("opponent"),
        "pick_side": safe_record.get("pick_side"),
        "opponent_side": safe_record.get("opponent_side"),
        "side_audit": safe_record.get("side_audit"),
        "raw": raw,
        "match_raw": raw,
        "raw_event": raw,
    }

    try:
        thinq = _call_build_match_features(thinq_service, payload)
        if not isinstance(thinq, dict):
            thinq = {"available": False, "error": "THINQ_RETURNED_NON_DICT"}
    except Exception as exc:
        thinq = {"available": False, "error": str(exc), "flags": ["THINQ_ATTACH_FAILED"]}

    safe_record["thinq"] = thinq
    safe_record["thinq_available"] = bool(thinq.get("available", thinq.get("thinq_available", False)))
    safe_record["thinq_error"] = thinq.get("error")
    safe_record["thinq_confidence"] = thinq.get("confidence") or thinq.get("thinq_confidence")
    safe_record["thinq_edges"] = thinq.get("edges") if isinstance(thinq.get("edges"), dict) else {}
    safe_record["thinq_flags"] = thinq.get("flags") or thinq.get("thinq_flags") or []

    for key, value in thinq.items():
        if key.startswith("thinq_"):
            safe_record[key] = value

    safe_record["thinq_h2h_requested_event_custom_id"] = (
        _nested_get(thinq, "h2h", "requested_event_custom_id")
        or thinq.get("thinq_h2h_requested_event_custom_id")
    )
    return safe_record




def _write_results_foundation_snapshots(
    all_rows: List[Dict[str, Any]],
    top7_rows: List[Dict[str, Any]],
    run_date: Optional[str],
    output_root: str,
) -> Dict[str, str]:
    """Store immutable daily snapshots for future Results evaluation."""
    day = (run_date or date.today().isoformat())[:10]
    year = day[:4]
    root = Path(output_root) / "snapshots" / year
    root.mkdir(parents=True, exist_ok=True)
    top7_path = root / f"{day}_corq_top7_snapshot.json"
    all_path = root / f"{day}_all_audit_snapshot.json"
    top7_path.write_text(json.dumps(top7_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    all_path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_root = Path(output_root) / "snapshots"
    latest_root.mkdir(parents=True, exist_ok=True)
    (latest_root / "latest_corq_top7_snapshot.json").write_text(json.dumps(top7_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (latest_root / "latest_all_audit_snapshot.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "corq_top7_snapshot": str(top7_path),
        "all_audit_snapshot": str(all_path),
        "latest_corq_top7_snapshot": str(latest_root / "latest_corq_top7_snapshot.json"),
        "latest_all_audit_snapshot": str(latest_root / "latest_all_audit_snapshot.json"),
    }


def run_daily(input_path: Optional[str] = None, output_root: str = "outputs", run_date: Optional[str] = None) -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    raw_candidates = load_candidates(input_path)
    candidates = [repair_candidate_side(candidate) for candidate in raw_candidates]
    thinq_service = _load_thinq_service()
    ta_rankings = _load_ta_rankings()

    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        enriched = _enrich_with_thinq(candidate, thinq_service)
        prediction = build_corq_prediction(enriched)
        prediction = _enrich_with_ta_rankings(prediction, ta_rankings)
        prediction = _enrich_with_ta_profile_context(prediction)
        scored.append(prediction)

    all_view = make_all_match_view(scored)
    ranking = rank_corq(scored)
    top7 = top7_from_ranking(ranking, top_n=7)

    all_paths = save_all(all_view, run_date=run_date, output_root=output_root)
    top7_paths = save_top7(top7, run_date=run_date, output_root=output_root)
    snapshot_paths = _write_results_foundation_snapshots(all_view, top7, run_date=run_date, output_root=output_root)
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
        "outputs": {"all": all_paths, "top7": top7_paths, "snapshots": snapshot_paths},
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
