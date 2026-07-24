
"""
CORQ output writer.

Purpose
-------
Keep the production web output simple while storing every daily snapshot in
clean year-based archives.

Rules
-----
- public/ is only the GitHub Pages publish target.
- data/snapshots/ is the internal audit source of truth.
- Daily files are grouped by year to avoid thousands of files in one folder.
- latest JSON files stay in public/ for the website.

Expected public outputs
-----------------------
public/all_predictions_latest.json
public/corq_predictions_latest.json
public/top7_predictions_latest.json
public/thinq_predictions_latest.json
public/cloq_predictions_latest.json
public/results_latest.json

Expected archive outputs
------------------------
data/snapshots/<kind>/<YYYY>/<YYYY-MM-DD>.json
public/archive/<kind>/<YYYY>/<kind>_predictions_<YYYY-MM-DD>.json

Kinds
-----
all, corq, top7, thinq, cloq, results
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

JsonDict = Dict[str, Any]
JsonLike = Union[JsonDict, List[JsonDict]]

PROJECT_ROOT = Path(os.getenv("CORQ_PROJECT_ROOT", ".")).resolve()
PUBLIC_DIR = Path(os.getenv("CORQ_PUBLIC_DIR", str(PROJECT_ROOT / "public"))).resolve()
DATA_DIR = Path(os.getenv("CORQ_DATA_DIR", str(PROJECT_ROOT / "data"))).resolve()
SNAPSHOT_DIR = Path(os.getenv("CORQ_SNAPSHOT_DIR", str(DATA_DIR / "snapshots"))).resolve()
PUBLIC_ARCHIVE_DIR = Path(os.getenv("CORQ_PUBLIC_ARCHIVE_DIR", str(PUBLIC_DIR / "archive"))).resolve()

KIND_TO_PUBLIC_LATEST = {
    "all": "all_predictions_latest.json",
    "corq": "corq_predictions_latest.json",
    "top7": "top7_predictions_latest.json",
    "thinq": "thinq_predictions_latest.json",
    "cloq": "cloq_predictions_latest.json",
    "results": "results_latest.json",
}

KIND_TO_PUBLIC_ARCHIVE_PREFIX = {
    "all": "all_predictions",
    "corq": "corq_predictions",
    "top7": "top7_predictions",
    "thinq": "thinq_predictions",
    "cloq": "cloq_predictions",
    "results": "results",
}

KIND_ALIASES = {
    "top": "top7",
    "top_7": "top7",
    "top7_predictions": "top7",
    "corq_predictions": "corq",
    "all_predictions": "all",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_date(snapshot_date: Optional[str] = None) -> str:
    if snapshot_date:
        return str(snapshot_date)[:10]
    return today_utc_date()


def year_from_date(snapshot_date: str) -> str:
    return normalize_date(snapshot_date)[:4]


def normalize_kind(kind: str) -> str:
    raw = str(kind or "").strip().lower()
    raw = KIND_ALIASES.get(raw, raw)
    if raw not in KIND_TO_PUBLIC_LATEST:
        raise ValueError(f"Unsupported output kind: {kind!r}")
    return raw


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Union[str, Path], payload: Any) -> Path:
    path = Path(path)
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    return path


def read_json(path: Union[str, Path], default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_records(records_or_payload: Any) -> List[JsonDict]:
    """Accept either a list of predictions or a payload with common keys."""
    if records_or_payload is None:
        return []
    if isinstance(records_or_payload, list):
        return [dict(item) for item in records_or_payload if isinstance(item, Mapping)]
    if isinstance(records_or_payload, Mapping):
        for key in ("predictions", "picks", "records", "items", "matches", "data"):
            value = records_or_payload.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
        # A single prediction dict is accepted as one record only if it has a pick/player field.
        if any(k in records_or_payload for k in ("pick", "player1", "match", "event_id", "eventId")):
            return [dict(records_or_payload)]
    return []


def build_payload(kind: str, records: Any, snapshot_date: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> JsonDict:
    kind = normalize_kind(kind)
    date_value = normalize_date(snapshot_date)
    record_list = extract_records(records)
    meta_dict = dict(meta or {})
    created_at = meta_dict.pop("created_at", None) or utc_now_iso()
    return {
        "kind": kind,
        "snapshot_date": date_value,
        "created_at": created_at,
        "count": len(record_list),
        "meta": meta_dict,
        "predictions": record_list,
    }


def snapshot_path(kind: str, snapshot_date: Optional[str] = None) -> Path:
    kind = normalize_kind(kind)
    date_value = normalize_date(snapshot_date)
    year = year_from_date(date_value)
    return SNAPSHOT_DIR / kind / year / f"{date_value}.json"


def public_latest_path(kind: str) -> Path:
    kind = normalize_kind(kind)
    return PUBLIC_DIR / KIND_TO_PUBLIC_LATEST[kind]


def public_archive_path(kind: str, snapshot_date: Optional[str] = None) -> Path:
    kind = normalize_kind(kind)
    date_value = normalize_date(snapshot_date)
    year = year_from_date(date_value)
    prefix = KIND_TO_PUBLIC_ARCHIVE_PREFIX[kind]
    return PUBLIC_ARCHIVE_DIR / kind / year / f"{prefix}_{date_value}.json"


def save_snapshot(kind: str, records: Any, snapshot_date: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> JsonDict:
    payload = build_payload(kind=kind, records=records, snapshot_date=snapshot_date, meta=meta)
    write_json(snapshot_path(kind, payload["snapshot_date"]), payload)
    return payload


def save_public(kind: str, records: Any, snapshot_date: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> JsonDict:
    payload = build_payload(kind=kind, records=records, snapshot_date=snapshot_date, meta=meta)
    write_json(public_latest_path(kind), payload)
    write_json(public_archive_path(kind, payload["snapshot_date"]), payload)
    return payload


def save_kind(kind: str, records: Any, snapshot_date: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> JsonDict:
    """Save one output kind to data/snapshots and public latest/archive."""
    payload = save_snapshot(kind=kind, records=records, snapshot_date=snapshot_date, meta=meta)
    save_public(kind=kind, records=payload["predictions"], snapshot_date=payload["snapshot_date"], meta=payload.get("meta"))
    return payload


def save_outputs(
    all_predictions: Any = None,
    corq_predictions: Any = None,
    top7_predictions: Any = None,
    thinq_predictions: Any = None,
    cloq_predictions: Any = None,
    results: Any = None,
    snapshot_date: Optional[str] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, JsonDict]:
    """Canonical multi-output writer used by the clean CORQ runtime."""
    date_value = normalize_date(snapshot_date)
    base_meta = dict(meta or {})
    written: Dict[str, JsonDict] = {}

    payloads = {
        "all": all_predictions,
        "corq": corq_predictions,
        "top7": top7_predictions,
        "thinq": thinq_predictions,
        "cloq": cloq_predictions,
        "results": results,
    }
    for kind, records in payloads.items():
        if records is None:
            continue
        kind_meta = dict(base_meta)
        kind_meta.setdefault("runtime", "clean_corq")
        kind_meta.setdefault("output_kind", kind)
        written[kind] = save_kind(kind=kind, records=records, snapshot_date=date_value, meta=kind_meta)
    return written


def save_runtime_outputs(
    all_records: Any,
    corq_records: Any,
    top7_records: Any,
    snapshot_date: Optional[str] = None,
    thinq_records: Any = None,
    cloq_records: Any = None,
    results_records: Any = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, JsonDict]:
    """Friendly alias for engine.py / corq.engine usage."""
    return save_outputs(
        all_predictions=all_records,
        corq_predictions=corq_records,
        top7_predictions=top7_records,
        thinq_predictions=thinq_records,
        cloq_predictions=cloq_records,
        results=results_records,
        snapshot_date=snapshot_date,
        meta=meta,
    )


def load_latest(kind: str, default: Any = None) -> Any:
    return read_json(public_latest_path(kind), default=default)


def list_snapshot_files(kind: str, year: Optional[str] = None) -> List[Path]:
    kind = normalize_kind(kind)
    root = SNAPSHOT_DIR / kind
    if year:
        root = root / str(year)
    if not root.exists():
        return []
    return sorted(root.glob("*.json"))


def cleanup_public_root_daily_files(dry_run: bool = True) -> List[str]:
    """Move legacy daily JSONs from public/ root into public/archive/legacy_root/.

    This is intentionally conservative and only touches obvious dated JSON files.
    Use dry_run=False only after a successful clean runtime deploy.
    """
    moved: List[str] = []
    if not PUBLIC_DIR.exists():
        return moved
    legacy_dir = PUBLIC_ARCHIVE_DIR / "legacy_root"
    patterns = [
        "all_predictions_20*.json",
        "predictions_20*.json",
        "top_predictions_20*.json",
        "results_20*.json",
    ]
    for pattern in patterns:
        for src in sorted(PUBLIC_DIR.glob(pattern)):
            year = src.stem.split("_")[-1][:4]
            dst = legacy_dir / year / src.name
            moved.append(f"{src} -> {dst}")
            if not dry_run:
                ensure_parent(dst)
                shutil.move(str(src), str(dst))
    return moved


# Backwards-compatible aliases for possible older clean runtime calls.
publish_outputs = save_outputs
write_outputs = save_outputs
save_prediction_outputs = save_outputs
