"""Candidate loader for the clean CORQ runtime.

MVP behavior:
- reads local JSON if provided, so the runtime can be tested immediately
- accepts either a list of matches or {"matches": [...]}
- creates two side candidates for every singles match

RapidAPI PRO match loading will be connected here after we inspect the old
fixture loader/endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def as_float(value: Any, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def load_json_candidates(path: Optional[str] = None) -> List[Dict[str, Any]]:
    candidates = []
    search_paths = []
    if path:
        search_paths.append(Path(path))
    search_paths.extend([
        Path("data/candidates.json"),
        Path("data/matches.json"),
        Path("outputs/input/candidates.json"),
        Path("outputs/input/matches.json"),
    ])

    source = None
    for candidate_path in search_paths:
        if candidate_path.exists():
            source = candidate_path
            break

    if source is None:
        return []

    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw_matches = payload.get("matches") or payload.get("events") or payload.get("data") or []
    else:
        raw_matches = payload

    if not isinstance(raw_matches, list):
        return []

    for item in raw_matches:
        if isinstance(item, dict):
            row = dict(item)
            row.setdefault("source", str(source))
            candidates.append(row)
    return candidates


def expand_match_sides(matches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for match in matches:
        player1 = match.get("player1") or match.get("home") or match.get("home_team") or match.get("player_a")
        player2 = match.get("player2") or match.get("away") or match.get("away_team") or match.get("player_b")
        if not player1 or not player2:
            continue

        p1_odds = as_float(match.get("player1_odds") or match.get("odds_player1") or match.get("home_odds") or match.get("p1_odds") or match.get("odds1"))
        p2_odds = as_float(match.get("player2_odds") or match.get("odds_player2") or match.get("away_odds") or match.get("p2_odds") or match.get("odds2"))

        common = dict(match)
        common["player1"] = str(player1)
        common["player2"] = str(player2)

        rows.append({**common, "pick": str(player1), "opponent": str(player2), "odds": p1_odds, "pick_odds": p1_odds, "opponent_odds": p2_odds})
        rows.append({**common, "pick": str(player2), "opponent": str(player1), "odds": p2_odds, "pick_odds": p2_odds, "opponent_odds": p1_odds})
    return rows


def load_candidates(path: Optional[str] = None) -> List[Dict[str, Any]]:
    matches = load_json_candidates(path)
    return expand_match_sides(matches)
