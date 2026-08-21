"""Settle immutable LucQ snapshots from real API PRO event data."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import RapidApiClient

LOCAL_TZ = ZoneInfo("Europe/Bratislava")


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _status_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("type") or value.get("description") or value.get("name")
    return str(value or "").strip().lower().replace("_", "")


def _event_finished(event: Dict[str, Any]) -> bool:
    status = event.get("status") or event.get("statusType") or event.get("status_type")
    text = _status_text(status)
    return text in {"finished", "ended", "complete", "completed"} or event.get("winnerCode") not in (None, 0, "0", "")


def _period_values(score: Any) -> List[int]:
    if not isinstance(score, dict):
        return []
    out: List[int] = []
    for index in range(1, 6):
        value = score.get(f"period{index}")
        try:
            if value not in (None, ""):
                out.append(int(float(value)))
        except Exception:
            continue
    return out


def _actual_shape(event: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[bool]]:
    home = _period_values(event.get("homeScore"))
    away = _period_values(event.get("awayScore"))
    count = min(len(home), len(away))
    if count <= 0:
        return None, None, None
    pairs = list(zip(home[:count], away[:count]))
    actual_sets = sum(1 for h, a in pairs if h != a)
    actual_games = sum(h + a for h, a in pairs)
    actual_tb = any((h == 7 and a == 6) or (h == 6 and a == 7) for h, a in pairs)
    return actual_sets or None, actual_games or None, actual_tb


def _walk(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _stat_pair(payload: Any, wanted: str) -> Tuple[Optional[float], Optional[float]]:
    target = wanted.lower().replace("_", " ")
    aliases = {target}
    if target == "double faults":
        aliases.update({"double fault", "doublefaults", "doublefault"})
    for item in _walk(payload):
        name = str(item.get("name") or item.get("label") or item.get("type") or "").strip().lower().replace("_", " ")
        compact = name.replace(" ", "")
        if name not in aliases and compact not in {a.replace(" ", "") for a in aliases}:
            continue
        home = item.get("home")
        away = item.get("away")
        if home is None:
            home = item.get("homeValue") or item.get("valueHome") or item.get("home_value")
        if away is None:
            away = item.get("awayValue") or item.get("valueAway") or item.get("away_value")
        h, a = _float(home), _float(away)
        if h is not None or a is not None:
            return h, a
    return None, None


def _ou_status(selection: Any, actual: Any) -> str:
    text = str(selection or "").strip().upper()
    value = _float(actual)
    if not text or value is None:
        return "RESULT_UNAVAILABLE"
    side = text[:1]
    try:
        line = float(text[1:])
    except Exception:
        return "RESULT_UNAVAILABLE"
    if abs(value - line) < 1e-9:
        return "VOID"
    won = value > line if side == "O" else value < line if side == "U" else False
    return "WON" if won else "LOST"


def _tb_status(selection: Any, actual: Any) -> str:
    if actual is None or not selection:
        return "RESULT_UNAVAILABLE"
    predicted = str(selection).strip().upper() == "YES"
    return "WON" if bool(actual) == predicted else "LOST"


def _overall_status(row: Dict[str, Any]) -> str:
    statuses = [str(row.get(key) or "") for key in (
        "sets_result_status", "games_result_status", "tb_result_status",
        "aces_result_status", "df_result_status",
    )]
    decided = [value for value in statuses if value in {"WON", "LOST", "VOID"}]
    if any(value == "LOST" for value in decided):
        return "LOST"
    if any(value == "WON" for value in decided):
        return "WON"
    if any(value == "PENDING" for value in statuses):
        return "PENDING"
    return "RESULT_UNAVAILABLE"


def settle_row(row: Dict[str, Any], client: RapidApiClient) -> Dict[str, Any]:
    out = deepcopy(row)
    event_id = out.get("event_id") or out.get("match_id")
    if event_id in (None, ""):
        out["lucq_result_status"] = "RESULT_UNAVAILABLE"
        return out
    event_payload = client.get(f"/api/tennis/event/{event_id}")
    event = event_payload.get("event") if isinstance(event_payload, dict) and isinstance(event_payload.get("event"), dict) else event_payload
    if not isinstance(event, dict):
        out["lucq_result_status"] = "RESULT_UNAVAILABLE"
        return out
    if not _event_finished(event):
        out["lucq_result_status"] = "PENDING"
        return out

    actual_sets, actual_games, actual_tb = _actual_shape(event)
    out["actual_sets"] = actual_sets
    out["actual_games"] = actual_games
    out["actual_tiebreak"] = actual_tb
    out["sets_result_status"] = _ou_status(out.get("sets_selection"), actual_sets)
    out["games_result_status"] = _ou_status(out.get("games_selection"), actual_games)
    out["tb_result_status"] = _tb_status(out.get("tb_selection"), actual_tb)

    stats = client.get(f"/api/tennis/event/{event_id}/statistics")
    home_aces, away_aces = _stat_pair(stats, "aces")
    home_df, away_df = _stat_pair(stats, "double faults")
    pick_home = str(out.get("pick_side") or "HOME").upper() == "HOME"
    pick_aces, opp_aces = (home_aces, away_aces) if pick_home else (away_aces, home_aces)
    pick_df, opp_df = (home_df, away_df) if pick_home else (away_df, home_df)
    out["actual_pick_aces"], out["actual_opponent_aces"] = pick_aces, opp_aces
    out["actual_total_aces"] = (pick_aces + opp_aces) if pick_aces is not None and opp_aces is not None else None
    out["actual_pick_df"], out["actual_opponent_df"] = pick_df, opp_df
    out["actual_total_df"] = (pick_df + opp_df) if pick_df is not None and opp_df is not None else None
    out["aces_result_status"] = _ou_status(out.get("total_aces_selection"), out.get("actual_total_aces"))
    out["df_result_status"] = _ou_status(out.get("total_df_selection"), out.get("actual_total_df"))
    out["lucq_result_status"] = _overall_status(out)
    out["settled_at"] = datetime.now(LOCAL_TZ).isoformat()
    return out


def _load_rows(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    return [row for row in (rows or []) if isinstance(row, dict)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="", help="Optional snapshot day YYYY-MM-DD")
    parser.add_argument("--output", default="outputs/lucq/results/latest_lucq_results.json")
    args = parser.parse_args()
    snapshot_dir = Path("outputs/lucq/snapshots")
    if args.date:
        requested = snapshot_dir / f"lucq_{args.date}.json"
        paths = [requested] if requested.exists() else []
    else:
        paths = sorted(snapshot_dir.glob("lucq_*.json"))
    latest = Path("outputs/lucq/latest_lucq.json")
    if not paths and latest.exists():
        print(f"No matching snapshot found; using fallback: {latest}")
        paths = [latest]
    if not paths:
        raise SystemExit("No LucQ snapshot or latest_lucq.json found to settle")
    print("LucQ settlement inputs:", ", ".join(str(path) for path in paths))
    rows_by_id: Dict[str, Dict[str, Any]] = {}
    for path in paths:
        for row in _load_rows(path):
            key = str(row.get("event_id") or row.get("match_id") or f"{row.get('pick')}|{row.get('opponent')}|{row.get('match_start')}")
            rows_by_id[key] = row
    if not rows_by_id:
        raise SystemExit("LucQ settlement input contains zero rows")
    client = RapidApiClient()
    settled = [settle_row(row, client) for row in rows_by_id.values()]
    settled.sort(key=lambda row: str(row.get("match_start") or ""), reverse=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": "LucQ Results", "generated_at": datetime.now(LOCAL_TZ).isoformat(), "row_count": len(settled), "rows": settled}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"LUCQ RESULTS: {output} rows={len(settled)}")


if __name__ == "__main__":
    main()
