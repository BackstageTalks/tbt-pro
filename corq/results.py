from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RAPIDAPI_HOST = "tennisapi1.p.rapidapi.com"


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("rows", "items", "top7", "all", "results"):
            if isinstance(value.get(key), list):
                return [x for x in value[key] if isinstance(x, dict)]
    return []


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def _prob(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_estimated_win_probability", "corq_probability", "win_probability", "corq_score"):
        value = _num(row.get(key), None)
        if value is not None:
            return value / 100.0 if value > 1.5 else value
    return None


def _odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "odds", "selected_odds"):
        value = _num(row.get(key), None)
        if value is not None:
            return value
    return None


def _status_from_obj(status: Any) -> str:
    if isinstance(status, dict):
        raw = status.get("type") or status.get("description") or status.get("status") or status.get("code")
    else:
        raw = status
    text = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in {"100", "finished", "ended", "complete", "completed"}:
        return "finished"
    if text in {"inprogress", "in_progress", "live"}:
        return "live"
    if text in {"notstarted", "not_started", "scheduled", "open", "prematch", "upcoming"}:
        return "notstarted"
    if text in {"cancelled", "canceled", "postponed", "retired", "walkover", "interrupted"}:
        return text
    return text or "unknown"


def _snapshot_status(row: Dict[str, Any]) -> str:
    raw = row.get("status") or row.get("status_type") or row.get("match_status_type")
    if not raw and isinstance(row.get("raw"), dict):
        raw = ((row.get("raw") or {}).get("status") or {}).get("type")
    return _status_from_obj(raw)


def _event_id(row: Dict[str, Any]) -> Optional[int]:
    for key in ("event_id", "match_id", "id"):
        value = row.get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except Exception:
                pass
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    value = raw.get("id")
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def _fetch_event_detail(event_id: int, cache: Dict[int, Dict[str, Any]], sleep_s: float = 0.05) -> Tuple[Optional[Dict[str, Any]], str]:
    if event_id in cache:
        return cache[event_id], "CACHE"
    api_key = os.getenv("RAPIDAPI_KEY", "").strip() or os.getenv("TENNISAPI_RAPIDAPI_KEY", "").strip()
    if not api_key:
        return None, "NO_API_KEY"
    path = f"/api/tennis/event/{event_id}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=30)
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8", errors="replace")
        conn.close()
        if sleep_s:
            time.sleep(sleep_s)
        if res.status == 204 or not raw:
            return None, f"HTTP_{res.status}_EMPTY"
        if res.status >= 400:
            return None, f"HTTP_{res.status}"
        data = json.loads(raw)
        event = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), dict) else data
        if isinstance(event, dict):
            cache[event_id] = event
            return event, "OK"
        return None, "NO_EVENT_OBJECT"
    except Exception as exc:
        return None, f"ERROR_{type(exc).__name__}"


def _name_from_team(team: Any) -> str:
    if isinstance(team, dict):
        return str(team.get("name") or team.get("fullName") or team.get("shortName") or "").strip()
    return ""


def _winner_from_event(event: Dict[str, Any]) -> str:
    winner_code = event.get("winnerCode")
    if winner_code == 1:
        return _name_from_team(event.get("homeTeam"))
    if winner_code == 2:
        return _name_from_team(event.get("awayTeam"))
    return str(event.get("winner") or event.get("winnerName") or "").strip()


def _period_scores(score_obj: Any) -> List[Optional[int]]:
    if not isinstance(score_obj, dict):
        return []
    out: List[Optional[int]] = []
    for i in range(1, 6):
        value = score_obj.get(f"period{i}")
        if value is None:
            continue
        try:
            out.append(int(value))
        except Exception:
            out.append(None)
    return out


def _score_from_event(event: Dict[str, Any]) -> Tuple[str, Optional[int], Optional[int], Optional[int], bool]:
    home_scores = _period_scores(event.get("homeScore"))
    away_scores = _period_scores(event.get("awayScore"))
    max_len = max(len(home_scores), len(away_scores))
    if not max_len:
        return "", None, None, None, False
    sets_home = 0
    sets_away = 0
    games_total = 0
    tiebreak = False
    parts: List[str] = []
    for i in range(max_len):
        h = home_scores[i] if i < len(home_scores) else None
        a = away_scores[i] if i < len(away_scores) else None
        if h is None or a is None:
            continue
        parts.append(f"{h}-{a}")
        games_total += h + a
        if h > a:
            sets_home += 1
        elif a > h:
            sets_away += 1
        if {h, a} in ({7, 6}, {6, 7}):
            tiebreak = True
    actual_sets = sets_home + sets_away if (sets_home or sets_away) else None
    return " ".join(parts), actual_sets, games_total if games_total else None, max(sets_home, sets_away) if actual_sets else None, tiebreak


def _snapshot_winner(row: Dict[str, Any]) -> str:
    winner = row.get("winner") or row.get("match_winner")
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if not winner and raw:
        winner = _winner_from_event(raw)
    return str(winner or "").strip()


def _snapshot_score(row: Dict[str, Any]) -> str:
    for key in ("score", "result_score", "final_score"):
        if row.get(key):
            return str(row[key])
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    if raw:
        score, *_ = _score_from_event(raw)
        return score
    return ""


def _flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("flags", "corq_risk_flags", "corq_warning_flags", "thinq_flags", "top7_quality_reject_reasons"):
        value = row.get(key)
        if isinstance(value, list):
            out.extend(str(x) for x in value if x)
        elif value:
            out.append(str(value))
    return sorted(set(out))


def _evaluate_row(row: Dict[str, Any], source_snapshot: str, run_date: str, fetch_api: bool, cache: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    pick = str(row.get("pick") or row.get("player") or "").strip()
    opponent = str(row.get("opponent") or row.get("opp") or "").strip()
    odds = _odds(row)
    status = _snapshot_status(row)
    winner = _snapshot_winner(row)
    score = _snapshot_score(row)
    event_fetch_status = "NOT_REQUESTED"
    event = None

    if fetch_api:
        eid = _event_id(row)
        if eid is not None:
            event, event_fetch_status = _fetch_event_detail(eid, cache)
            if event:
                status = _status_from_obj(event.get("status"))
                winner = _winner_from_event(event) or winner
                event_score, actual_sets, actual_games, _, actual_tiebreak = _score_from_event(event)
                score = event_score or score
            else:
                actual_sets = actual_games = None
                actual_tiebreak = False
        else:
            event_fetch_status = "NO_EVENT_ID"
            actual_sets = actual_games = None
            actual_tiebreak = False
    else:
        actual_sets = actual_games = None
        actual_tiebreak = False

    result = "PENDING"
    units: Optional[float] = None
    if status in {"cancelled", "canceled", "postponed", "walkover", "retired"}:
        result = "VOID"
        units = 0.0
    elif status in {"finished", "ended", "complete", "completed"} or winner:
        if winner and _norm(winner) == _norm(pick):
            result = "WON"
            units = round((odds or 1.0) - 1.0, 4) if odds else None
        elif winner:
            result = "LOST"
            units = -1.0

    projected_sets = _num(row.get("thinq_projected_sets"), None)
    projected_games = _num(row.get("thinq_projected_games"), None)
    games_error = round(actual_games - projected_games, 2) if actual_games is not None and projected_games is not None else None
    sets_hit = None
    if actual_sets is not None and projected_sets is not None:
        sets_hit = round(projected_sets) == actual_sets

    return {
        "date": run_date,
        "source_snapshot": source_snapshot,
        "match_id": row.get("match_id") or row.get("event_id") or row.get("id"),
        "custom_id": row.get("event_custom_id") or row.get("customId"),
        "pick": pick,
        "opponent": opponent,
        "pick_odds": odds,
        "opponent_odds": row.get("opponent_odds") or row.get("opp_odds"),
        "corq_probability": _prob(row),
        "thinq_confidence": row.get("thinq_confidence") or row.get("thinq_probability_confidence"),
        "pick_thinq_edge": row.get("top7_pick_thinq_edge") or row.get("pick_thinq_edge") or row.get("thinq_edge"),
        "stat_data_depth": row.get("stat_data_depth") or row.get("pick_data_depth"),
        "form_data_depth": row.get("form_data_depth") or row.get("thinq_form_confidence"),
        "status": status or "unknown",
        "winner": winner,
        "score": score,
        "result": result,
        "units": units,
        "tags": _flags(row),
        "event_fetch_status": event_fetch_status,
        "sets_games": {
            "projected_sets": projected_sets,
            "projected_games": projected_games,
            "actual_sets": actual_sets,
            "actual_games": actual_games,
            "sets_hit": sets_hit,
            "games_error": games_error,
            "actual_tiebreak": actual_tiebreak,
            "three_sets_probability": row.get("thinq_decider_probability"),
            "tie_break_probability": row.get("thinq_tiebreak_probability"),
        },
        "raw_snapshot_row": row,
    }


def _summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = sum(1 for r in rows if r.get("result") == "WON")
    lost = sum(1 for r in rows if r.get("result") == "LOST")
    pending = sum(1 for r in rows if r.get("result") == "PENDING")
    void = sum(1 for r in rows if r.get("result") == "VOID")
    settled = won + lost
    units = round(sum(float(r.get("units") or 0.0) for r in rows if r.get("units") is not None), 4)
    return {
        "picks": len(rows),
        "won": won,
        "lost": lost,
        "pending": pending,
        "void": void,
        "win_rate": round(won / settled, 4) if settled else None,
        "units": units,
        "roi": round(units / settled, 4) if settled else None,
    }


def _tag_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        for tag in row.get("tags") or []:
            buckets.setdefault(str(tag), []).append(row)
    return [{"tag": tag, **_summary(items)} for tag, items in sorted(buckets.items())]


def _sets_games_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluated = [r for r in rows if isinstance(r.get("sets_games"), dict)]
    actual_games = [r["sets_games"].get("actual_games") for r in evaluated if r["sets_games"].get("actual_games") is not None]
    games_errors = [r["sets_games"].get("games_error") for r in evaluated if r["sets_games"].get("games_error") is not None]
    sets_hits = [r["sets_games"].get("sets_hit") for r in evaluated if r["sets_games"].get("sets_hit") is not None]
    tiebreaks = [r["sets_games"].get("actual_tiebreak") for r in evaluated if r["sets_games"].get("actual_tiebreak") is not None]
    return {
        "rows_with_actual_games": len(actual_games),
        "avg_actual_games": round(sum(actual_games) / len(actual_games), 2) if actual_games else None,
        "avg_games_error": round(sum(games_errors) / len(games_errors), 2) if games_errors else None,
        "sets_hit_rate": round(sum(1 for x in sets_hits if x) / len(sets_hits), 4) if sets_hits else None,
        "tiebreak_rate": round(sum(1 for x in tiebreaks if x) / len(tiebreaks), 4) if tiebreaks else None,
    }


def build_results(output_root: str = "outputs", run_date: Optional[str] = None, fetch_api: bool = False) -> Dict[str, Any]:
    root = Path(output_root)
    day = (run_date or date.today().isoformat())[:10]
    year = day[:4]

    corq_snapshot = _as_list(_load_json(root / "snapshots" / "latest_corq_top7_snapshot.json", []))
    all_snapshot = _as_list(_load_json(root / "snapshots" / "latest_all_audit_snapshot.json", []))
    if not corq_snapshot:
        corq_snapshot = _as_list(_load_json(root / "latest_top7.json", []))
    if not all_snapshot:
        all_snapshot = _as_list(_load_json(root / "latest_all.json", []))

    cache: Dict[int, Dict[str, Any]] = {}
    corq_results = [_evaluate_row(r, "CORQ_TOP7", day, fetch_api, cache) for r in corq_snapshot]
    all_results = [_evaluate_row(r, "ALL_AUDIT", day, fetch_api, cache) for r in all_snapshot]

    corq_payload = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "section": "CorQ TOP7 Results",
        "fetch_api": fetch_api,
        "summary": _summary(corq_results),
        "tag_summary": _tag_summary(corq_results),
        "sets_games_summary": _sets_games_summary(corq_results),
        "rows": corq_results,
    }
    all_payload = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "section": "ALL Results Audit",
        "fetch_api": fetch_api,
        "summary": _summary(all_results),
        "tag_summary": _tag_summary(all_results),
        "sets_games_summary": _sets_games_summary(all_results),
        "rows": all_results,
    }

    corq_dir = root / "results" / "corq" / year
    all_dir = root / "results" / "all" / year
    corq_dir.mkdir(parents=True, exist_ok=True)
    all_dir.mkdir(parents=True, exist_ok=True)
    (corq_dir / f"results_corq_{day}.json").write_text(json.dumps(corq_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (all_dir / f"results_all_{day}.json").write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "results" / "latest_results_corq.json").write_text(json.dumps(corq_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "results" / "latest_results_all.json").write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"corq": corq_payload, "all": all_payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CorQ/ALL results evaluation JSON files.")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", dest="run_date", default=None)
    parser.add_argument("--fetch-api", action="store_true", help="Fetch TennisApi event details for winner/score/status.")
    args = parser.parse_args()
    payload = build_results(output_root=args.output_root, run_date=args.run_date, fetch_api=args.fetch_api)
    print("Results built:", payload["corq"]["summary"], payload["all"]["summary"])


if __name__ == "__main__":
    main()
