from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple
from urllib.request import Request, urlopen

import pandas as pd

try:
    from torq_tennisabstract import fetch_snapshot
except Exception:
    fetch_snapshot = None

RAW_DIR = Path("data/torq_tennisabstract/raw")
META_DIR = Path("data/torq_tennisabstract/meta")
SNAPSHOT_DIR = Path("data/torq_tennisabstract")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

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
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=60) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def is_cloudflare_challenge(html: str) -> bool:
    lower = html.lower()
    markers = [
        "challenge-platform",
        "/cdn-cgi/challenge-platform",
        "window._cf_chl_opt",
        "cf-browser-verification",
        "checking your browser",
    ]
    return any(marker in lower for marker in markers)


def classify_html(filename: str, html: str) -> Tuple[bool, str]:
    lower = html.lower()
    if is_cloudflare_challenge(html):
        return False, "CLOUDFLARE_CHALLENGE"
    if "tennis abstract" not in lower:
        return False, "MISSING_TENNIS_ABSTRACT_MARKER"
    if "player" not in lower or "elo" not in lower:
        return False, "MISSING_PLAYER_ELO_MARKERS"
    try:
        tables = pd.read_html(html)
    except Exception as exc:
        return False, f"PANDAS_PARSE_ERROR:{exc}"
    if not tables:
        return False, "NO_TABLES"
    return True, "OK"


def write_meta(filename: str, url: str, html: str, changed: bool, valid: bool, status: str) -> None:
    meta = {
        "filename": filename,
        "url": url,
        "downloaded_at_utc": now_utc(),
        "sha256": sha256_text(html),
        "changed": changed,
        "valid": valid,
        "status": status,
        "bytes": len(html.encode("utf-8", errors="replace")),
    }
    (META_DIR / f"{filename}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def update_one(filename: str, url: str) -> Tuple[bool, bool, str]:
    destination = RAW_DIR / filename
    previous = destination.read_text(encoding="utf-8", errors="replace") if destination.exists() else None

    html = fetch_url(url)
    valid, status = classify_html(filename, html)

    if not valid:
        # Keep previous good HTML instead of replacing it with a Cloudflare/error page.
        rejected_path = META_DIR / f"{filename}.rejected.html"
        rejected_path.write_text(html[:5000], encoding="utf-8")
        write_meta(filename, url, html, changed=False, valid=False, status=status)
        print("TA WEEKLY SKIP", filename, "status", status, "bytes", len(html.encode("utf-8", errors="replace")))
        return False, False, status

    changed = previous != html
    destination.write_text(html, encoding="utf-8")
    write_meta(filename, url, html, changed=changed, valid=True, status="OK")
    print("TA WEEKLY SYNC", filename, "changed", changed, "bytes", len(html.encode("utf-8", errors="replace")))
    return changed, True, "OK"


def main() -> None:
    ensure_dirs()

    changed_count = 0
    valid_count = 0
    statuses: Dict[str, str] = {}

    for filename, url in SOURCES.items():
        try:
            changed, valid, status = update_one(filename, url)
            statuses[filename] = status
            if changed:
                changed_count += 1
            if valid:
                valid_count += 1
        except Exception as exc:
            statuses[filename] = f"ERROR:{exc}"
            print("TA WEEKLY ERROR", filename, exc)

    # Only rebuild snapshot if we have valid raw HTML files or an existing snapshot parser.
    if valid_count > 0 and fetch_snapshot is not None:
        try:
            snapshot = fetch_snapshot(force=True)
            snapshot_path = SNAPSHOT_DIR / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            counts = {key: len(value) for key, value in snapshot.items()}
            print("TA WEEKLY SNAPSHOT COUNTS", counts)
        except Exception as exc:
            print("TA WEEKLY SNAPSHOT ERROR", exc)
    else:
        print("TA WEEKLY SNAPSHOT SKIPPED", "valid_downloads", valid_count)

    # DONT fail the workflow when Tennis Abstract serves a Cloudflare challenge.
    # The existing committed snapshot/raw HTML remains usable by Torq Daily.
    print("TA WEEKLY STATUS", statuses)
    print("TA WEEKLY SYNC DONE", "changed_files", changed_count, "valid_downloads", valid_count)


if __name__ == "__main__":
    main()
