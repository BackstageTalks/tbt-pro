"""CORQ output writers with yearly folders, latest aliases and empty-TOP7 protection."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _today_str(run_date: Optional[str] = None) -> str:
    if run_date:
        return str(run_date)[:10]
    return date.today().isoformat()


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return path


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _non_empty_list_payload(payload: Any) -> bool:
    if isinstance(payload, list):
        return len([x for x in payload if isinstance(x, dict)]) > 0
    if isinstance(payload, dict):
        for key in ("rows", "items", "top7", "picks", "data", "records"):
            value = payload.get(key)
            if isinstance(value, list) and any(isinstance(x, dict) for x in value):
                return True
    return False


def save_all(records: Iterable[Dict[str, Any]], run_date: Optional[str] = None, output_root: str = "outputs") -> Dict[str, str]:
    rows = list(records)
    day = _today_str(run_date)
    year = day[:4]
    root = Path(output_root)
    dated = root / year / "all" / f"all_{day}.json"
    latest = root / "latest_all.json"
    _write_json(dated, rows)
    _write_json(latest, rows)
    return {"dated": str(dated), "latest": str(latest)}


def save_top7(records: Iterable[Dict[str, Any]], run_date: Optional[str] = None, output_root: str = "outputs") -> Dict[str, str]:
    rows = list(records)
    day = _today_str(run_date)
    year = day[:4]
    root = Path(output_root)
    dated = root / year / "top7" / f"top7_{day}.json"
    latest = root / "latest_top7.json"

    # Always write the dated diagnostic file so every run is auditable.
    _write_json(dated, rows)

    # Safety guard: a late/manual run can legitimately produce zero TOP7 rows
    # when all candidates are already finished. Do not overwrite the public latest
    # alias with [] unless explicitly allowed. The workflow additionally checks
    # latest_manifest.top7_count and refuses to snapshot/deploy a zero-TOP7 run.
    if not rows and latest.exists() and _env_truthy("CORQ_PRESERVE_LATEST_TOP7_ON_EMPTY", True):
        existing = _read_json(latest, [])
        if _non_empty_list_payload(existing):
            return {
                "dated": str(dated),
                "latest": str(latest),
                "latest_preserved": "true",
                "preserve_reason": "empty_top7_run_did_not_overwrite_existing_latest",
            }

    _write_json(latest, rows)
    return {"dated": str(dated), "latest": str(latest)}


def save_run_manifest(payload: Dict[str, Any], run_date: Optional[str] = None, output_root: str = "outputs") -> Dict[str, str]:
    day = _today_str(run_date)
    year = day[:4]
    root = Path(output_root)
    dated = root / year / "run" / f"manifest_{day}.json"
    latest = root / "latest_manifest.json"
    _write_json(dated, payload)
    _write_json(latest, payload)
    return {"dated": str(dated), "latest": str(latest)}
