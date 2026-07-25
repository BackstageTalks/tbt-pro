from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

DEFAULT_YEARS = [2024, 2025, 2026]
DEFAULT_TOURS = ["atp", "wta"]
BASE_URLS = {
    "atp": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv",
    "wta": "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv",
}


def parse_list_env(name: str, default: List[str]) -> List[str]:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return [x.strip() for x in value.split(",") if x.strip()]


def main() -> int:
    years = [int(x) for x in parse_list_env("THINQ_HISTORY_YEARS", [str(y) for y in DEFAULT_YEARS])]
    tours = parse_list_env("THINQ_HISTORY_TOURS", DEFAULT_TOURS)
    root = Path(os.environ.get("THINQ_HISTORY_ROOT", "data/history"))
    root.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0
    downloads: List[Dict[str, object]] = []

    for tour in tours:
        if tour not in BASE_URLS:
            continue
        for year in years:
            url = BASE_URLS[tour].format(year=year)
            dest = root / tour / str(year) / f"{tour}_matches_{year}.csv"
            dest.parent.mkdir(parents=True, exist_ok=True)
            item: Dict[str, object] = {"tour": tour, "year": year, "url": url, "path": str(dest)}
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    data = resp.read()
                if len(data) < 1000:
                    raise RuntimeError(f"Downloaded file too small: {len(data)} bytes")
                dest.write_bytes(data)
                item.update({"status": "OK", "bytes": len(data)})
                ok += 1
            except Exception as exc:
                item.update({"status": "ERROR", "error": str(exc)})
                fail += 1
            downloads.append(item)
            time.sleep(0.2)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "ok": ok,
        "fail": fail,
        "downloads": downloads,
    }
    (root / "bootstrap_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"THINQ history bootstrap finished: ok={ok} fail={fail} root={root}")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
