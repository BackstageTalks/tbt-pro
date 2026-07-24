"""CORQ candidate loader.

Canonical side-safe version:
- player1 is always HOME/API first side
- player2 is always AWAY/API second side
- candidate rows are HOME and AWAY sides
- pick/opponent are derived from pick_side, never manually trusted
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from corq.sides import AWAY, HOME, derive_side_record, repair_candidate_side
from thinq.loaders.rapidapi_client import fetch_daily_matches_with_odds


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
    rows = []
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
        matches = fetch_daily_matches_with_odds()
    except Exception as exc:
        print(f"RAPIDAPI LOADER ERROR: {exc}")
        matches = []
    if matches:
        return expand_match_sides(matches)
    if os.getenv("CORQ_ALLOW_LOCAL_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "y"}:
        return expand_match_sides(load_json_candidates(path=None, include_default_paths=True))
    return []
