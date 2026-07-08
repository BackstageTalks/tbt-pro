from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.request import Request, urlopen

import pandas as pd

from torq_tennisabstract import fetch_snapshot

RAW_DIR = Path("data/torq_tennisabstract/raw")
META_DIR = Path("data/torq_tennisabstract/meta")
SNAPSHOT_DIR = Path("data/torq_tennisabstract")

USER_AGENT = "Mozilla/5.0 (compatible; tbt-pro-ta-weekly-sync/1.0; +https://github.com/BackstageTalks/tbt-pro)"

SOURCES = {
    "atp_elo.html": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "atp_yelo.html": "https://tennisabstract.com/reports/atp_season_yelo_ratings.html",
    "wta_elo.html": "https://tennisabstract.com/reports/wta_elo_ratings.html",
    "wta_yelo.html": "https://tennisabstract.com/reports/wta_season_yelo_ratings.html",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=60) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def validate_html(filename: str, html: str) -> None:
    lower = html.lower()
    if "tennis abstract" not in lower:
        raise RuntimeError(f"Invalid Tennis Abstract HTML for {filename}: missing site marker")
    if "player" not in lower or "elo" not in lower:
        raise RuntimeError(f"Invalid Tennis Abstract HTML for {filename}: missing Player/Elo table markers")
    # pandas parse check catches anti-bot/error pages early
    tables = pd.read_html(html)
    if not tables:
        raise RuntimeError(f"Invalid Tennis Abstract HTML for {filename}: no tables parsed")


def write_meta(filename: str, url: str, html: str, changed: bool) -> None:
    meta = {
        "filename": filename,
        "url": url,
        "downloaded_at_utc": now_utc(),
        "sha256": sha256_text(html),
        "changed": changed,
        "bytes": len(html.encode("utf-8", errors="replace")),
    }
    (META_DIR / f"{filename}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def update_one(filename: str, url: str) -> bool:
    destination = RAW_DIR / filename
    previous = destination.read_text(encoding="utf-8", errors="replace") if destination.exists() else None
    html = fetch_url(url)
    validate_html(filename, html)
    changed = previous != html
    destination.write_text(html, encoding="utf-8")
    write_meta(filename, url, html, changed)
    print("TA WEEKLY SYNC", filename, "changed", changed, "bytes", len(html.encode("utf-8", errors="replace")))
    return changed


def main() -> None:
    ensure_dirs()
    changed_count = 0
    for filename, url in SOURCES.items():
        if update_one(filename, url):
            changed_count += 1

    # Build parsed snapshot from the freshly downloaded HTML.
    # torq_tennisabstract.py reads data/torq_tennisabstract/raw first after this patch.
    snapshot = fetch_snapshot(force=True)
    snapshot_path = SNAPSHOT_DIR / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {key: len(value) for key, value in snapshot.items()}
    print("TA WEEKLY SNAPSHOT COUNTS", counts)
    print("TA WEEKLY SYNC DONE", "changed_files", changed_count)


if __name__ == "__main__":
    main()
