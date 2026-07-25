from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_YEARS = [2024, 2025, 2026]
DEFAULT_TOURS = ["atp", "wta"]
ROOT = Path(os.environ.get("THINQ_HISTORY_ROOT", "data/history"))

TML_FILES_API = "https://stats.tennismylife.org/api/data-files"

# Public mirrors / upstreams. The archive mirror keeps ATP and WTA yearly files through 2026.
ARCHIVE_URLS = {
    "atp": [
        "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive/main/atp/atp_matches_{year}.csv",
        "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv",
    ],
    "wta": [
        "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive/main/wta/wta_matches_{year}.csv",
        "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv",
    ],
}


def _env_list(name: str, default: List[str]) -> List[str]:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return [x.strip().lower() for x in value.split(",") if x.strip()]


def _download(url: str, dest: Path, timeout: int = 45) -> Dict[str, Any]:
    item: Dict[str, Any] = {"url": url, "path": str(dest)}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 500:
            raise RuntimeError(f"Downloaded file too small: {len(data)} bytes")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        item.update({"status": "OK", "bytes": len(data)})
    except Exception as exc:
        item.update({"status": "ERROR", "error": str(exc)})
    return item


def _fetch_tml_files() -> List[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(TML_FILES_API, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        files = payload.get("files", []) if isinstance(payload, dict) else []
        return [x for x in files if isinstance(x, dict)]
    except Exception as exc:
        print(f"TML api error: {exc}")
        return []


def bootstrap_from_tml(years: List[int], tours: List[str]) -> List[Dict[str, Any]]:
    files = _fetch_tml_files()
    selected: List[Dict[str, Any]] = []
    year_tokens = {str(y) for y in years}
    for f in files:
        name = str(f.get("name") or f.get("path") or "").lower()
        url = str(f.get("url") or "")
        if not url or not any(y in name for y in year_tokens):
            continue
        if "atp" in tours and (
            name.endswith(".csv") and (
                name.split("/")[-1] in {f"{y}.csv" for y in year_tokens}
                or "challenger" in name
                or "_ch" in name
                or "atp_quali" in name
            )
        ):
            selected.append(f)
        if "wta" in tours and ("wta" in name or "women" in name):
            selected.append(f)

    results: List[Dict[str, Any]] = []
    print(f"TML files listed: {len(files)} selected: {len(selected)}")
    for f in selected:
        name = str(f.get("name") or Path(str(f.get("url"))).name)
        dest = ROOT / "tml" / name.replace("\\", "/").strip("/")
        res = _download(str(f.get("url")), dest)
        res.update({"provider": "tennismylife", "name": name})
        results.append(res)
        print(f"TML {res.get('status')}: {name}")
        time.sleep(0.15)
    return results


def bootstrap_from_archives(years: List[int], tours: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for tour in tours:
        templates = ARCHIVE_URLS.get(tour, [])
        for year in years:
            got_year = False
            for template in templates:
                url = template.format(year=year)
                provider = "sackmann_archive" if "Aneeshers" in url else "sackmann_upstream"
                dest = ROOT / provider / tour / str(year) / f"{tour}_matches_{year}.csv"
                res = _download(url, dest)
                res.update({"provider": provider, "tour": tour, "year": year})
                results.append(res)
                print(f"{provider} {res.get('status')}: {tour} {year}")
                time.sleep(0.15)
                if res.get("status") == "OK":
                    got_year = True
                    break
            if not got_year:
                print(f"No archive source succeeded for {tour} {year}")
    return results


def main() -> int:
    years = [int(x) for x in _env_list("THINQ_HISTORY_YEARS", [str(y) for y in DEFAULT_YEARS])]
    tours = _env_list("THINQ_HISTORY_TOURS", DEFAULT_TOURS)
    ROOT.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    results.extend(bootstrap_from_tml(years, tours))
    results.extend(bootstrap_from_archives(years, tours))

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "years": years,
        "tours": tours,
        "ok": ok,
        "fail": fail,
        "providers": ["tennismylife", "sackmann_archive", "sackmann_upstream"],
        "results": results,
    }
    (ROOT / "bootstrap_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"THINQ history bootstrap finished: ok={ok} fail={fail} root={ROOT}")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
