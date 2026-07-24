"""CORQ output writers with yearly folders and latest aliases."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
    _write_json(dated, rows)
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
