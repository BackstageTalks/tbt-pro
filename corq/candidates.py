"""CORQ candidate loader.

Production path:
    RapidAPI PRO -> daily matches with odds -> two candidate sides per match.

Test path:
    python engine.py --input data/candidates.sample.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from thinq.loaders.rapidapi_client import fetch_daily_matches_with_odds


def as_float(value: Any, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


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


def expand_match_sides(matches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for match in matches:
        player1 = match.get("player1")
        player2 = match.get("player2")
        if not player1 or not player2:
            continue
        p1_odds = as_float(match.get("odds_player1") or match.get("p1_odds") or match.get("home_odds") or match.get("odds1") or match.get("price1"))
        p2_odds = as_float(match.get("odds_player2") or match.get("p2_odds") or match.get("away_odds") or match.get("odds2") or match.get("price2"))
        common = dict(match)
        common["player1"] = str(player1)
        common["player2"] = str(player2)
        rows.append({**common, "pick": str(player1), "opponent": str(player2), "odds": p1_odds, "pick_odds": p1_odds, "opponent_odds": p2_odds})
        rows.append({**common, "pick": str(player2), "opponent": str(player1), "odds": p2_odds, "pick_odds": p2_odds, "opponent_odds": p1_odds})
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
