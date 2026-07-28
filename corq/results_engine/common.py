from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[results_engine] failed to read {path}: {exc}")
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "picks", "cloq", "records", "results", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "" or value == "—" or value == "-":
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def pick_name(row: Dict[str, Any]) -> str:
    return str(row.get("pick") or row.get("cloq_pick") or row.get("player") or row.get("player1") or row.get("home") or "").strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(row.get("opponent") or row.get("opp") or row.get("player2") or row.get("away") or "").strip()


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "cloq_pick_odds", "selected_odds", "odds_decimal", "decimal_odds", "odds"):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return val
    return None


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("opponent_odds", "opp_odds", "cloq_opponent_odds", "opponent_price"):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return val
    return None


def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability", "cloq_probability"):
        val = as_float(row.get(key))
        if val is not None:
            return val / 100.0 if val > 1.5 else val
    return None


def run_date_from_payload(*payloads: Any) -> str:
    for payload in payloads:
        if isinstance(payload, dict):
            for key in ("run_date", "snapshot_date", "date", "generated_for", "updated_at", "generated_at"):
                value = payload.get(key)
                if value:
                    txt = str(value)[:10]
                    if re.match(r"^20\d{2}-\d{2}-\d{2}$", txt):
                        return txt
    return date.today().isoformat()


def row_date(row: Dict[str, Any], default: str) -> str:
    for key in ("date", "snapshot_date", "run_date", "match_date", "start_time_utc", "match_time_utc", "start_time", "match_time"):
        value = row.get(key)
        if value:
            txt = str(value)[:10]
            if re.match(r"^20\d{2}-\d{2}-\d{2}$", txt):
                return txt
    return default


def match_identity(row: Dict[str, Any]) -> str:
    for key in ("event_id", "match_id", "custom_id", "customId", "id", "match_key"):
        value = row.get(key)
        if value:
            return f"id:{value}"
    names = sorted([normalize_name(pick_name(row)), normalize_name(opponent_name(row))])
    t = str(row.get("start_time_utc") or row.get("match_time_utc") or row.get("start_time") or row.get("match_time") or "")[:16]
    return "pair:" + "|".join(names) + "|" + t


def side_identity(row: Dict[str, Any]) -> str:
    return match_identity(row) + "|pick:" + normalize_name(pick_name(row))


def result_status_text(row: Dict[str, Any]) -> str:
    return str(row.get("result") or row.get("result_status") or row.get("status") or row.get("match_status") or "").upper()


def flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("tags", "technical_flags", "corq_warning_flags", "risk_flags", "reject_reasons", "top7_risk_tags", "public_notes", "flags"):
        value = row.get(key)
        if isinstance(value, list):
            out.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value:
            out.append(value)
    return sorted(set(out))


def dedupe_match_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    def row_score(row: Dict[str, Any]) -> Tuple[float, float, float, float]:
        return (
            1.0 if row.get("top7_publishable") or row.get("eligible_for_top7") else 0.0,
            as_float(probability(row), 0.0) or 0.0,
            as_float(row.get("stat_data_depth") or row.get("pick_data_depth"), 0.0) or 0.0,
            as_float(pick_odds(row), 0.0) or 0.0,
        )

    for row in rows:
        key = match_identity(row)
        if key not in by_key:
            by_key[key] = row
            order.append(key)
        else:
            if row_score(row) > row_score(by_key[key]):
                by_key[key] = row
    return [by_key[k] for k in order]
