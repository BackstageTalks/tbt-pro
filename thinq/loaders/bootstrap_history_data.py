from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_YEARS = [2024, 2025, 2026]
DEFAULT_TOURS = ["atp", "wta"]
ROOT = Path(os.environ.get("THINQ_HISTORY_ROOT", "data/history"))

# Primary fallback for live 2026-friendly CSVs. The endpoint returns file names and download URLs.
TML_FILES_API = "https://stats.tennismylife.org/api/data-files"

# Historical Sackmann repos may not expose yearly match files through the expected raw URLs in this environment.
# Keep these as optional attempts only, never as the only data source.
SACKMANN_URLS = {
    "atp": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv",
    "wta": "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv",
}


def _env_list(name: str, default: List[str]) -> List[str]:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return [x.strip() for x in value.split(",") if x.strip()]


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


def _select_tml_files(files: List[Dict[str, Any]], years: List[int], tours: List[str]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    year_set = {str(y) for y in years}
    want_atp = "atp" in tours
    want_wta = "wta" in tours

    for f in files:
        name = str(f.get("name") or f.get("path") or "")
        url = f.get("url")
        if not url:
            continue
        low = name.lower()
        # Keep only yearly/current history-ish files, not huge all-database unless no better source.
        if not any(y in low for y in year_set):
            continue
        if want_atp and (
            re.fullmatch(r"\d{4}\.csv", Path(low).name or "")
            or "challenger" in low
            or "_ch" in low
            or "atp_quali" in low
        ):
            selected.append(f)
            continue
        if want_wta and ("wta" in low or "women" in low or "wta_" in low):
            selected.append(f)
            continue
    return selected


def bootstrap_from_tml(years: List[int], tours: List[str]) -> List[Dict[str, Any]]:
    files = _fetch_tml_files()
    selected = _select_tml_files(files, years, tours)
    results: List[Dict[str, Any]] = []
    print(f"TML files listed: {len(files)} selected: {len(selected)}")
    for f in selected:
        name = str(f.get("name") or Path(str(f.get("url"))).name)
        safe = name.replace("\\", "/").strip("/")
        # Put everything into data/history/tml while preserving subfolders like atp_quali/...
        dest = ROOT / "tml" / safe
        res = _download(str(f.get("url")), dest)
        res.update({"provider": "tennismylife", "name": name})
        results.append(res)
        print(f"TML {res.get('status')}: {name} -> {dest}")
        time.sleep(0.15)
    return results


def bootstrap_from_sackmann(years: List[int], tours: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for tour in tours:
        template = SACKMANN_URLS.get(tour)
        if not template:
            continue
        for year in years:
            url = template.format(year=year)
            dest = ROOT / "sackmann" / tour / str(year) / f"{tour}_matches_{year}.csv"
            res = _download(url, dest)
            res.update({"provider": "sackmann", "tour": tour, "year": year})
            results.append(res)
            print(f"Sackmann {res.get('status')}: {tour} {year}")
            time.sleep(0.15)
    return results


def main() -> int:
    years = [int(x) for x in _env_list("THINQ_HISTORY_YEARS", [str(y) for y in DEFAULT_YEARS])]
    tours = _env_list("THINQ_HISTORY_TOURS", DEFAULT_TOURS)
    ROOT.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    # Try the live 2026-friendly source first.
    results.extend(bootstrap_from_tml(years, tours))
    # Then optional Sackmann raw fallback.
    results.extend(bootstrap_from_sackmann(years, tours))

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "years": years,
        "tours": tours,
        "ok": ok,
        "fail": fail,
        "results": results,
    }
    (ROOT / "bootstrap_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"THINQ history bootstrap finished: ok={ok} fail={fail} root={ROOT}")

    # Important: do not fail the workflow if a provider is temporarily unavailable.
    # Daily runtime must continue. A no-data manifest is enough for diagnostics.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
