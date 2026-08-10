"""CORQ candidate loader.

Canonical side-safe version:
- player1 is always HOME/API first side
- player2 is always AWAY/API second side
- candidate rows are HOME and AWAY sides
- pick/opponent are derived from pick_side, never manually trusted

Important runtime policy:
- CORQ must use the CORQ-owned RapidAPI/TennisAPI loader first.
- The CORQ loader applies the project betting-day window:
  Europe/Bratislava 06:00 -> 06:00 next day.
- Older ThinQ loaders may still exist, but they are fallback only. They must not
  be the primary source for CORQ daily ALL/Audit/TOP7 rows because they can drift
  from the 06:00 betting-day policy.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from corq.sides import AWAY, HOME, derive_side_record, repair_candidate_side

# Prefer the CORQ-owned loader. This is the loader that carries the 06:00 -> 06:00
# Europe/Bratislava betting-day policy and TennisAPI pageSize=200 pagination.
# Keep fallbacks for older repo snapshots, but do not make ThinQ the primary
# CORQ match source anymore.
try:  # preferred current repo path
    from corq.corq_rapidapi_client import fetch_daily_matches_with_odds  # type: ignore
    CORQ_CANDIDATE_LOADER_SOURCE = "corq.corq_rapidapi_client"
except Exception:  # pragma: no cover - legacy fallback
    try:
        from corq.rapidapi_client import fetch_daily_matches_with_odds  # type: ignore
        CORQ_CANDIDATE_LOADER_SOURCE = "corq.rapidapi_client"
    except Exception:  # pragma: no cover - last-resort legacy fallback
        from thinq.loaders.rapidapi_client import fetch_daily_matches_with_odds  # type: ignore
        CORQ_CANDIDATE_LOADER_SOURCE = "thinq.loaders.rapidapi_client"


def load_json_candidates(path: Optional[str] = None, include_default_paths: bool = False) -> List[Dict[str, Any]]:
    search_paths: List[Path] = []
    if path:
        search_paths.append(Path(path))
    if include_default_paths:
        search_paths.extend([
            Path("data/candidates.json"),
            Path("data/matches.json"),
            Path("outputs/input/candidates.json"),
            Path("outputs/input/matches.json"),
        ])
    source = next((candidate for candidate in search_paths if candidate.exists()), None)
    if source is None:
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_matches = payload.get("matches") or payload.get("events") or payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(raw_matches, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in raw_matches:
        if isinstance(item, dict):
            row = dict(item)
            row.setdefault("source", str(source))
            rows.append(row)
    return rows


def normalize_match_home_away(match: Dict[str, Any]) -> Dict[str, Any]:
    player1 = match.get("player1") or match.get("home_player") or match.get("home") or match.get("homeTeam")
    player2 = match.get("player2") or match.get("away_player") or match.get("away") or match.get("awayTeam")
    out = dict(match)
    if player1 is not None:
        out["player1"] = str(player1)
        out["home_player"] = str(player1)
    if player2 is not None:
        out["player2"] = str(player2)
        out["away_player"] = str(player2)
    return out


def expand_match_sides(matches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw_match in matches:
        match = normalize_match_home_away(raw_match)
        if not match.get("player1") or not match.get("player2"):
            continue
        try:
            rows.append(derive_side_record(match, HOME))
            rows.append(derive_side_record(match, AWAY))
        except Exception as exc:
            broken = dict(match)
            broken["candidate_expand_error"] = str(exc)
            rows.append(repair_candidate_side(broken))
    return rows


def load_candidates(path: Optional[str] = None) -> List[Dict[str, Any]]:
    if path:
        return expand_match_sides(load_json_candidates(path=path, include_default_paths=False))

    try:
        print(f"CORQ CANDIDATE LOADER SOURCE: {CORQ_CANDIDATE_LOADER_SOURCE}")
        matches = fetch_daily_matches_with_odds()
    except Exception as exc:
        print(f"RAPIDAPI LOADER ERROR: {exc}")
        matches = []

    if matches:
        return expand_match_sides(matches)

    if os.getenv("CORQ_ALLOW_LOCAL_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "y"}:
        return expand_match_sides(load_json_candidates(path=None, include_default_paths=True))

    return []
