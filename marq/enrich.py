from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .pipeline import build_marq_from_match


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "" or value == "—" or value == "-":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[marq] failed to read {path}: {exc}")
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def json_rows_with_writer(payload: Any) -> Tuple[List[Dict[str, Any]], Any]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)], ("list", None)
    if isinstance(payload, dict):
        for key in ("rows", "items", "top7", "all", "picks", "cloq", "records", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)], ("dict", key)
    return [], ("none", None)


def replace_rows(payload: Any, descriptor: Any, rows: List[Dict[str, Any]]) -> Any:
    kind, key = descriptor
    if kind == "list":
        return rows
    if kind == "dict" and isinstance(payload, dict) and key:
        out = dict(payload)
        out[key] = rows
        return out
    return payload


def pick_name(row: Dict[str, Any]) -> str:
    return str(row.get("pick") or row.get("cloq_pick") or row.get("player") or row.get("player1") or row.get("home") or "").strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(row.get("opponent") or row.get("opp") or row.get("player2") or row.get("away") or "").strip()


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "cloq_pick_odds", "selected_odds", "odds_decimal", "decimal_odds", "odds"):
        value = as_float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("opponent_odds", "opp_odds", "cloq_opponent_odds", "opponent_price"):
        value = as_float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def row_date(row: Dict[str, Any]) -> str:
    for key in ("date", "snapshot_date", "run_date", "match_date", "start_time_utc", "match_time_utc", "start_time", "match_time"):
        value = row.get(key)
        if value:
            text = str(value)[:10]
            if re.match(r"^20\d{2}-\d{2}-\d{2}$", text):
                return text
    return date.today().isoformat()


def percent_text(value: Any) -> str:
    val = as_float(value)
    if val is None:
        return "—"
    if abs(val) <= 1.0:
        val *= 100.0
    return f"{val:.1f}%"


def number_text(value: Any, digits: int = 2) -> str:
    val = as_float(value)
    if val is None:
        return "—"
    return f"{val:.{digits}f}"


def display_aliases(marq: Dict[str, Any]) -> Dict[str, Any]:
    market_view = bool(marq.get("marq_market_view"))
    quality = str(marq.get("marq_quality_signal") or marq.get("marq_ai_signal") or "Pending")
    source = str(marq.get("marq_source") or "—")
    provider_count = marq.get("marq_provider_count")
    move = str(marq.get("marq_move_signal") or "UNKNOWN")
    move_pct = marq.get("marq_market_move_pct")
    if move_pct is not None:
        move = f"{move} ({number_text(move_pct, 1)}%)"
    sharp = str(marq.get("marq_sharp_signal") or "NO SHARP DATA")
    sharp_pct = marq.get("marq_sharp_pick_pct")
    if sharp_pct is not None:
        sharp = f"{sharp} ({percent_text(sharp_pct)})"
    pick_market = percent_text(marq.get("marq_crowd_pick_pct"))
    opp_market = percent_text(marq.get("marq_crowd_opponent_pct"))
    quality_display = f"{quality} | P{provider_count}" if provider_count not in (None, "") else quality
    status = quality_display if market_view else str(marq.get("marq_ai_signal") or "Pending")
    return {
        "marq_status": status,
        "pick_marq": pick_market,
        "opponent_marq": opp_market,
        "market_move": move,
        "odds_source": source,
        "odds_matching_direction_display": sharp,
        "marq_quality_display": quality_display,
    }


def enrich_row_with_marq(row: Dict[str, Any], force_refresh: bool = False) -> Dict[str, Any]:
    out = dict(row)
    if out.get("marq_market_view") is not None and not force_refresh:
        out.update(display_aliases(out))
        return out
    player1 = pick_name(out)
    player2 = opponent_name(out)
    if not player1 or not player2:
        out.update({"marq_market_view": False, "marq_ai_signal": "MISSING PLAYERS", "marq_ai_reason": "missing_players"})
        out.update(display_aliases(out))
        return out
    result = build_marq_from_match(
        player1=player1,
        player2=player2,
        date_only=row_date(out),
        pick=player1,
        odds_player1=pick_odds(out),
        odds_player2=opponent_odds(out),
        force_refresh=force_refresh,
    )
    out.update(result or {})
    out.update(display_aliases(out))
    return out


def enrich_rows_with_marq(rows: Iterable[Dict[str, Any]], limit: Optional[int] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if limit is not None and count >= limit:
            enriched.append(dict(row))
            continue
        enriched.append(enrich_row_with_marq(row, force_refresh=force_refresh))
        count += 1
    return enriched


def enrich_json_file(path: Path, limit: Optional[int] = None, force_refresh: bool = False) -> int:
    payload = read_json(path, None)
    rows, descriptor = json_rows_with_writer(payload)
    if not rows:
        print(f"[marq] no rows in {path}")
        return 0
    enriched = enrich_rows_with_marq(rows, limit=limit, force_refresh=force_refresh)
    write_json(path, replace_rows(payload, descriptor, enriched))
    print(f"[marq] enriched {len(enriched)} rows in {path}")
    return len(enriched)
