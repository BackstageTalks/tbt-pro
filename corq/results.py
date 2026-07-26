#!/usr/bin/env python3
"""TBT PRO Results foundation and evaluation.

This module builds separate Results outputs for:
- CorQ TOP7 Results: published / selected CorQ picks.
- ALL Results Audit: all current audit rows from ALL.

Design rules:
- Results evaluate saved/output JSON rows, not a changing web page.
- CorQ results and ALL audit stay separate.
- Missing or not-finished matches remain PENDING.
- Cancelled, postponed, walkover/no-contest style states are VOID.
- Unit staking is flat 1u: win = odds - 1, loss = -1, void/pending = 0.

Usage:
    python -m corq.results --output-root outputs --fetch-api true
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import http.client
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TENNISAPI_HOST = "tennisapi1.p.rapidapi.com"
DEFAULT_TIMEOUT = 25
REQUEST_SLEEP_SECONDS = 0.15

FINISHED_STATES = {"finished", "ended", "complete", "completed", "final"}
LIVE_STATES = {"inprogress", "in_progress", "live", "started", "running"}
VOID_STATES = {"cancelled", "canceled", "postponed", "walkover", "retired", "interrupted", "abandoned"}
PENDING_STATES = {"notstarted", "not_started", "scheduled", "open", "prematch", "upcoming", "pending", "unknown", ""}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_iso() -> str:
    # UTC date is enough for file labels; snapshots carry event timestamps separately.
    return datetime.now(timezone.utc).date().isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), encoding="utf-8")


def as_rows(payload: Any) -> List[Dict[str, Any]]:
    """Accept list or common dict wrappers and return a list of row dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in (
            "rows", "items", "matches", "predictions", "top7", "all", "data", "records", "results"
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        # If dict is one record, keep it.
        if any(k in payload for k in ("pick", "player1", "match_id", "event_id")):
            return [payload]
    return []


def norm_text(value: Any) -> str:
    return str(value or "").strip()


def norm_name(value: Any) -> str:
    text = norm_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def pct_value(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = to_float(row.get(key))
        if value is None:
            continue
        if value > 1.0:
            return value / 100.0
        return value
    return None


def get_first(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return default


def extract_event_id(row: Dict[str, Any]) -> Optional[int]:
    for key in (
        "event_id", "match_id", "id", "tennisapi_event_id", "rapidapi_event_id"
    ):
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except Exception:
            continue
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for key in ("id", "event_id", "match_id"):
        value = raw.get(key)
        try:
            if value is not None:
                return int(value)
        except Exception:
            pass
    return None


def pick_name(row: Dict[str, Any]) -> str:
    return norm_text(get_first(row, "pick", "selection", "player", "player_name", default=""))


def opponent_name(row: Dict[str, Any]) -> str:
    return norm_text(get_first(row, "opponent", "opp", "opponent_name", default=""))


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    return to_float(get_first(row, "pick_odds", "selected_odds", "odds", "price", "decimal_odds"))


def status_from_payload(payload: Dict[str, Any]) -> str:
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    status = event.get("status") if isinstance(event, dict) else None
    if not isinstance(status, dict):
        return norm_text(event.get("status") if isinstance(event, dict) else "unknown").lower()
    status_type = norm_text(status.get("type")).lower()
    description = norm_text(status.get("description")).lower()
    code = status.get("code")
    if code == 100 or status_type in FINISHED_STATES or description in FINISHED_STATES:
        return "finished"
    if status_type in LIVE_STATES or description in LIVE_STATES:
        return "live"
    if status_type in VOID_STATES or description in VOID_STATES:
        return status_type or description
    if status_type in PENDING_STATES or description in PENDING_STATES:
        return status_type or description or "notstarted"
    return status_type or description or "unknown"


def event_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("event"), dict):
        return payload["event"]
    return payload if isinstance(payload, dict) else {}


def team_name(obj: Any) -> str:
    if isinstance(obj, dict):
        for key in ("name", "fullName", "full_name", "displayName", "shortName", "slug"):
            if obj.get(key):
                return str(obj.get(key))
    return str(obj or "")


def score_periods(event: Dict[str, Any]) -> Tuple[List[int], List[int]]:
    home_score = event.get("homeScore") or {}
    away_score = event.get("awayScore") or {}
    home_periods: List[int] = []
    away_periods: List[int] = []
    for i in range(1, 6):
        hp = home_score.get(f"period{i}")
        ap = away_score.get(f"period{i}")
        if hp is None or ap is None:
            continue
        try:
            home_periods.append(int(hp))
            away_periods.append(int(ap))
        except Exception:
            continue
    return home_periods, away_periods


def build_score_string(home_periods: List[int], away_periods: List[int]) -> str:
    sets = []
    for h, a in zip(home_periods, away_periods):
        sets.append(f"{h}-{a}")
    return " ".join(sets)


def derive_match_result_from_event(row: Dict[str, Any], event_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return normalized result fields for a row based on TennisApi event payload."""
    pick = pick_name(row)
    opponent = opponent_name(row)
    odds = pick_odds(row)
    base = {
        "api_status": None,
        "winner": None,
        "score": None,
        "actual_sets": None,
        "actual_games": None,
        "actual_tiebreak": None,
        "result": "PENDING",
        "units": 0.0,
        "result_reason": "NO_API_PAYLOAD" if not event_payload else "PENDING_OR_UNKNOWN",
    }
    if not event_payload:
        return base

    event = event_from_payload(event_payload)
    api_status = status_from_payload(event_payload)
    base["api_status"] = api_status

    if api_status in VOID_STATES:
        base.update({"result": "VOID", "units": 0.0, "result_reason": f"VOID_STATUS:{api_status}"})
        return base
    if api_status not in FINISHED_STATES and api_status != "finished":
        base.update({"result": "PENDING", "units": 0.0, "result_reason": f"NOT_FINISHED:{api_status}"})
        return base

    home_team = team_name(event.get("homeTeam") or event.get("home") or event.get("player1"))
    away_team = team_name(event.get("awayTeam") or event.get("away") or event.get("player2"))
    winner_code = event.get("winnerCode")
    winner = None
    if winner_code == 1:
        winner = home_team
    elif winner_code == 2:
        winner = away_team
    else:
        winner = team_name(event.get("winner")) or None

    home_periods, away_periods = score_periods(event)
    score = build_score_string(home_periods, away_periods)
    games = sum(home_periods) + sum(away_periods) if home_periods and away_periods else None
    sets = len(home_periods) if home_periods else None
    tiebreak = None
    if home_periods and away_periods:
        tiebreak = any(max(h, a) >= 7 and abs(h - a) <= 2 for h, a in zip(home_periods, away_periods))

    base.update({
        "winner": winner,
        "score": score or None,
        "actual_sets": sets,
        "actual_games": games,
        "actual_tiebreak": tiebreak,
    })

    if not winner:
        base.update({"result": "PENDING", "result_reason": "FINISHED_BUT_WINNER_UNKNOWN"})
        return base

    pick_norm = norm_name(pick)
    winner_norm = norm_name(winner)
    if pick_norm and winner_norm and (pick_norm == winner_norm or pick_norm in winner_norm or winner_norm in pick_norm):
        units = round((odds or 1.0) - 1.0, 4) if odds else 0.0
        base.update({"result": "WON", "units": units, "result_reason": "PICK_MATCHES_WINNER"})
    else:
        base.update({"result": "LOST", "units": -1.0, "result_reason": "PICK_NOT_WINNER"})
    return base


def api_get_event(event_id: int, api_key: str, host: str = TENNISAPI_HOST) -> Optional[Dict[str, Any]]:
    path = f"/api/tennis/event/{int(event_id)}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": host,
        "Content-Type": "application/json",
    }
    conn = None
    try:
        conn = http.client.HTTPSConnection(host, timeout=DEFAULT_TIMEOUT)
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8", errors="replace")
        if res.status == 204:
            return None
        if res.status >= 400:
            return {"_error": f"HTTP_{res.status}", "_body": raw[:500]}
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception as exc:
        return {"_error": f"EXCEPTION:{exc}"}
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def collect_flags(row: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    for key in (
        "corq_warning_flags", "corq_risk_flags", "top7_risk_tags", "reject_reasons", "top7_quality_reject_reasons", "public_notes", "flags"
    ):
        value = row.get(key)
        if isinstance(value, list):
            flags.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            flags.append(value.strip())
    # Deduplicate while keeping order.
    out: List[str] = []
    seen = set()
    for flag in flags:
        if flag not in seen:
            seen.add(flag)
            out.append(flag)
    return out


def projected_sets(row: Dict[str, Any]) -> Optional[float]:
    return to_float(get_first(row, "projected_sets", "expected_sets", "sets_projected"))


def projected_games(row: Dict[str, Any]) -> Optional[float]:
    return to_float(get_first(row, "projected_games", "expected_games", "games_projected"))


def enrich_result_row(row: Dict[str, Any], event_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = dict(row)
    result = derive_match_result_from_event(row, event_payload)
    out.update(result)
    out["event_id"] = extract_event_id(row)
    out["pick"] = pick_name(row)
    out["opponent"] = opponent_name(row)
    out["pick_odds"] = pick_odds(row)
    out["corq_probability"] = pct_value(row, "corq_probability", "corq_prob", "estimated_win_probability", "win_probability", "estimated_win_pct")
    out["thinq_confidence"] = pct_value(row, "thinq_confidence", "thinq_overall_confidence", "thinq_probability_confidence")
    out["stat_data_depth"] = pct_value(row, "stat_data_depth", "pick_data_depth", "data_depth")
    out["form_data_depth"] = pct_value(row, "form_data_depth", "form_confidence")
    out["pick_thinq_edge"] = pct_value(row, "pick_thinq_edge", "thinq_edge", "thinq_total_edge")
    out["result_flags"] = collect_flags(row)

    ps = projected_sets(row)
    pg = projected_games(row)
    out["projected_sets"] = ps
    out["projected_games"] = pg
    if ps is not None and result.get("actual_sets") is not None:
        out["sets_error"] = round(float(result["actual_sets"]) - float(ps), 3)
        out["sets_hit_rounded"] = int(round(ps)) == int(result["actual_sets"])
    else:
        out["sets_error"] = None
        out["sets_hit_rounded"] = None
    if pg is not None and result.get("actual_games") is not None:
        out["games_error"] = round(float(result["actual_games"]) - float(pg), 3)
    else:
        out["games_error"] = None
    return out


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    won = sum(1 for r in rows if r.get("result") == "WON")
    lost = sum(1 for r in rows if r.get("result") == "LOST")
    pending = sum(1 for r in rows if r.get("result") == "PENDING")
    void = sum(1 for r in rows if r.get("result") == "VOID")
    finished = won + lost
    units = round(sum(float(r.get("units") or 0.0) for r in rows), 4)
    risked = max(won + lost, 0)
    avg_odds_values = [float(r.get("pick_odds")) for r in rows if to_float(r.get("pick_odds"))]
    avg_odds = round(sum(avg_odds_values) / len(avg_odds_values), 4) if avg_odds_values else None
    return {
        "rows": total,
        "won": won,
        "lost": lost,
        "pending": pending,
        "void": void,
        "finished": finished,
        "win_rate": round(won / finished, 4) if finished else None,
        "units": units,
        "roi": round(units / risked, 4) if risked else None,
        "avg_odds": avg_odds,
    }


def tag_analysis(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        for tag in row.get("result_flags") or []:
            bucket = agg.setdefault(tag, {"tag": tag, "count": 0, "won": 0, "lost": 0, "pending": 0, "void": 0, "units": 0.0})
            bucket["count"] += 1
            result = row.get("result") or "PENDING"
            if result in ("WON", "LOST", "PENDING", "VOID"):
                bucket[result.lower()] += 1
            bucket["units"] += float(row.get("units") or 0.0)
    output = []
    for bucket in agg.values():
        finished = bucket["won"] + bucket["lost"]
        bucket["units"] = round(bucket["units"], 4)
        bucket["win_rate"] = round(bucket["won"] / finished, 4) if finished else None
        output.append(bucket)
    output.sort(key=lambda x: (x["count"], x["units"]), reverse=True)
    return output


def sets_games_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    games_errors = [r.get("games_error") for r in rows if isinstance(r.get("games_error"), (int, float))]
    sets_hits = [r.get("sets_hit_rounded") for r in rows if r.get("sets_hit_rounded") is not None]
    return {
        "rows_with_games_error": len(games_errors),
        "avg_games_error": round(sum(games_errors) / len(games_errors), 4) if games_errors else None,
        "avg_abs_games_error": round(sum(abs(x) for x in games_errors) / len(games_errors), 4) if games_errors else None,
        "sets_hit_rows": len(sets_hits),
        "sets_hit_rate": round(sum(1 for x in sets_hits if x) / len(sets_hits), 4) if sets_hits else None,
    }


def build_results_for_rows(rows: List[Dict[str, Any]], fetch_api: bool, api_key: Optional[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    cache: Dict[int, Optional[Dict[str, Any]]] = {}
    out_rows: List[Dict[str, Any]] = []
    for row in rows:
        event_id = extract_event_id(row)
        payload = None
        if fetch_api and api_key and event_id:
            if event_id not in cache:
                cache[event_id] = api_get_event(event_id, api_key)
                time.sleep(REQUEST_SLEEP_SECONDS)
            payload = cache.get(event_id)
        out_rows.append(enrich_result_row(row, payload))
    meta = {
        "summary": summarize(out_rows),
        "tag_analysis": tag_analysis(out_rows),
        "sets_games_summary": sets_games_summary(out_rows),
    }
    return out_rows, meta


def load_source_rows(output_root: Path, source: str) -> List[Dict[str, Any]]:
    if source == "corq":
        return as_rows(read_json(output_root / "latest_top7.json", []))
    if source == "all":
        return as_rows(read_json(output_root / "latest_all.json", []))
    if source == "cloq":
        return as_rows(read_json(output_root / "latest_cloq.json", []))
    raise ValueError(f"Unsupported source: {source}")


def write_results(output_root: Path, source: str, rows: List[Dict[str, Any]], meta: Dict[str, Any], date_str: str) -> Dict[str, Any]:
    year = date_str[:4]
    payload = {
        "schema": "tbtpro.results.v1",
        "source": source,
        "date": date_str,
        "generated_at": utc_now_iso(),
        "summary": meta.get("summary", {}),
        "tag_analysis": meta.get("tag_analysis", []),
        "sets_games_summary": meta.get("sets_games_summary", {}),
        "rows": rows,
    }
    dated_path = output_root / "results" / source / year / f"results_{source}_{date_str}.json"
    latest_path = output_root / "results" / f"latest_results_{source}.json"
    write_json(dated_path, payload)
    write_json(latest_path, payload)
    return {"dated_path": str(dated_path), "latest_path": str(latest_path), "rows": len(rows)}


def run(output_root: Path, fetch_api: bool, sources: Iterable[str]) -> Dict[str, Any]:
    api_key = os.getenv("RAPIDAPI_KEY", "").strip() or os.getenv("TENNISAPI_RAPIDAPI_KEY", "").strip()
    if fetch_api and not api_key:
        print("[WARN] fetch_api=true but RAPIDAPI_KEY/TENNISAPI_RAPIDAPI_KEY is missing; results will stay pending.", file=sys.stderr)
    date_str = today_iso()
    manifest = {
        "generated_at": utc_now_iso(),
        "date": date_str,
        "fetch_api": bool(fetch_api and api_key),
        "sources": {},
    }
    for source in sources:
        rows = load_source_rows(output_root, source)
        result_rows, meta = build_results_for_rows(rows, bool(fetch_api and api_key), api_key)
        manifest["sources"][source] = write_results(output_root, source, result_rows, meta, date_str)
    write_json(output_root / "results" / "results_manifest.json", manifest)
    return manifest


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TBT PRO Results outputs.")
    parser.add_argument("--output-root", default="outputs", help="Output root directory, default: outputs")
    parser.add_argument("--fetch-api", default="false", help="true/false, fetch TennisApi event details")
    parser.add_argument("--sources", default="corq,all,cloq", help="Comma-separated sources: corq,all,cloq")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    fetch_api = str(args.fetch_api).strip().lower() in {"1", "true", "yes", "y", "on"}
    sources = [s.strip() for s in str(args.sources).split(",") if s.strip()]
    manifest = run(Path(args.output_root), fetch_api=fetch_api, sources=sources)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
