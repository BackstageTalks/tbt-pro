"""THINQ Surface Resolver.

Primary source: TennisApi PRO tournament info metadata.
Endpoint: /api/tennis/tournament/{tournament_id}/info
Important rules:
- Never default missing surface to Hard.
- If raw surface contains "hard", model surface is Hard.
- Carpet is preserved as raw surface but uses Hard ELO bucket until carpet ELO exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import json
import os
import re

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

HOST = os.getenv("TENNISAPI_PRO_HOST", "tennisapi1.p.rapidapi.com")
BASE_URL = os.getenv("TENNISAPI_PRO_BASE_URL", "https://tennisapi1.p.rapidapi.com")
DATA_DIR = Path(os.getenv("THINQ_SURFACE_DATA_DIR", "thinq/data/surfaces"))
CACHE_FILE = DATA_DIR / "tournament_surface_cache.json"
RAW_DIR = DATA_DIR / "raw" / "tennisapi_tournament_metadata"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"


def normalize_surface_type(surface_type: Any) -> Dict[str, Any]:
    raw = str(surface_type or "").strip()
    text = raw.lower()
    environment = None
    if "indoor" in text:
        environment = "Indoor"
    elif "outdoor" in text:
        environment = "Outdoor"

    flags = []
    if "clay" in text:
        surface = "Clay"
        bucket = "Clay"
        elo_type = "clay_elo"
        confidence = "HIGH"
    elif "grass" in text:
        surface = "Grass"
        bucket = "Grass"
        elo_type = "grass_elo"
        confidence = "HIGH"
    elif "carpet" in text:
        surface = "Carpet"
        bucket = "Hard"
        elo_type = "hard_elo"
        confidence = "MEDIUM"
        flags.append("CARPET_AS_HARD_FALLBACK")
    elif "hard" in text:
        surface = "Hard"
        bucket = "Hard"
        elo_type = "hard_elo"
        confidence = "HIGH"
    else:
        surface = "Unknown"
        bucket = "Overall"
        elo_type = "overall_elo"
        confidence = "LOW"
        if raw:
            flags.append("UNKNOWN_SURFACE_RAW_PRESENT")
        else:
            flags.append("MISSING_SURFACE")

    return {
        "surface": surface,
        "surface_raw": raw or None,
        "surface_environment": environment,
        "surface_model_bucket": bucket,
        "surface_confidence": confidence,
        "surface_flags": flags,
        "thinq_selected_elo_type": elo_type,
    }


def load_cache() -> Dict[str, Any]:
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"generated_at": None, "source": "tennisapi_tournament_info", "items": {}}


def save_cache(cache: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache["generated_at"] = utc_now()
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(CACHE_FILE)


def extract_surface_type(payload: Dict[str, Any]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else payload
    months = meta.get("playingMonths") if isinstance(meta, dict) else None
    if isinstance(months, list):
        for item in months:
            if isinstance(item, dict) and item.get("surfaceType"):
                return item.get("surfaceType")
    # Defensive recursive scan for surfaceType in case API shape changes.
    stack = [payload]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            if obj.get("surfaceType"):
                return obj.get("surfaceType")
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)
    return None


def fetch_tournament_metadata(tournament_id: Any, timeout: int = 20) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests is not installed")
    api_key = os.getenv("RAPIDAPI_KEY") or os.getenv("X_RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError("Missing RAPIDAPI_KEY")
    url = f"{BASE_URL.rstrip('/')}/api/tennis/tournament/{tournament_id}/info"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": HOST,
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{safe_key(tournament_id)}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def resolve_tournament_surface(tournament_id: Any = None, tournament_name: Any = None, match: Optional[Dict[str, Any]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    match = match or {}
    tournament_id = tournament_id or match.get("tournament_id") or match.get("tournamentId") or match.get("competition_id") or match.get("competitionId")
    tournament_name = tournament_name or match.get("tournament") or match.get("competitionName")
    cache_key = str(tournament_id or safe_key(tournament_name))
    cache = load_cache()
    items = cache.setdefault("items", {})

    if tournament_id and not force_refresh and cache_key in items:
        item = dict(items[cache_key])
        item.setdefault("surface_source", "tennisapi_tournament_info_cache")
        return item

    if tournament_id:
        try:
            payload = fetch_tournament_metadata(tournament_id)
            raw_surface = extract_surface_type(payload)
            info = normalize_surface_type(raw_surface)
            info.update({
                "surface_source": "tennisapi_tournament_info",
                "tournament_id": tournament_id,
                "tournament": tournament_name,
                "resolved_at": utc_now(),
            })
            items[cache_key] = info
            save_cache(cache)
            return info
        except Exception as exc:
            # Continue with weak raw match surface, but do not default to Hard.
            weak = normalize_surface_type(match.get("surface_raw") or match.get("surface"))
            weak.update({
                "surface_source": "raw_match_fallback_after_api_error",
                "surface_error": str(exc),
                "tournament_id": tournament_id,
                "tournament": tournament_name,
            })
            return weak

    weak = normalize_surface_type(match.get("surface_raw") or match.get("surface"))
    weak.update({
        "surface_source": "raw_match_no_tournament_id" if weak.get("surface") != "Unknown" else "unknown_no_tournament_id",
        "tournament_id": None,
        "tournament": tournament_name,
    })
    return weak


class SurfaceResolver:
    def resolve(self, match: Dict[str, Any], force_refresh: bool = False) -> Dict[str, Any]:
        return resolve_tournament_surface(match=match, force_refresh=force_refresh)
