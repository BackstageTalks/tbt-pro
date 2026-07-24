"""Candidate loader for CORQ clean runtime.

Priority order:
1. Explicit JSON input passed by --input.
2. Real daily matches through legacy project functions, if available:
   - fetch_matches.get_today_matches()
   - odds_api.fetch_odds()
   - odds_api.find_match_odds()
3. Optional local JSON fallback only when CORQ_ALLOW_LOCAL_FALLBACK=1.

This keeps sample data out of production daily workflow while still allowing
local tests with explicit --input data/candidates.sample.json.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def as_float(value: Any, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def names_match(a: Any, b: Any) -> bool:
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    a_parts = a_norm.split()
    b_parts = b_norm.split()
    if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
        return True
    return a_norm in b_norm or b_norm in a_norm


def first_present(item: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return None


def extract_odds_pair(odds_data: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    odds_data = odds_data or {}
    raw = odds_data.get("raw") if isinstance(odds_data.get("raw"), dict) else {}

    p1 = as_float(first_present(odds_data, (
        "odds_player1", "p1_odds", "home_odds", "odds1", "price1", "home_price", "player1_odds",
        "homeDecimalOdds", "home_decimal_odds",
    )))
    p2 = as_float(first_present(odds_data, (
        "odds_player2", "p2_odds", "away_odds", "odds2", "price2", "away_price", "player2_odds",
        "awayDecimalOdds", "away_decimal_odds",
    )))

    if p1 is None and raw:
        p1 = as_float(first_present(raw, ("odds_player1", "p1_odds", "home_odds", "odds1", "price1", "home_price")))
    if p2 is None and raw:
        p2 = as_float(first_present(raw, ("odds_player2", "p2_odds", "away_odds", "odds2", "price2", "away_price")))

    return p1, p2


def orient_odds_to_match_players(
    odds_data: Optional[Dict[str, Any]],
    player1: Any,
    player2: Any,
    p1_odds: Optional[float],
    p2_odds: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    if not isinstance(odds_data, dict) or p1_odds is None or p2_odds is None:
        return p1_odds, p2_odds, None

    item_player1 = odds_data.get("player1") or odds_data.get("home") or odds_data.get("home_team") or odds_data.get("homeTeam")
    item_player2 = odds_data.get("player2") or odds_data.get("away") or odds_data.get("away_team") or odds_data.get("awayTeam")
    direction = odds_data.get("odds_matching_direction") or odds_data.get("matching_direction") or odds_data.get("odds_match_method")

    if item_player1 and item_player2:
        direct = names_match(player1, item_player1) and names_match(player2, item_player2)
        reverse = names_match(player1, item_player2) and names_match(player2, item_player1)
        if reverse and not direct:
            return p2_odds, p1_odds, "REVERSED_TO_MATCH_PLAYERS"
        if direct:
            return p1_odds, p2_odds, direction or "DIRECT_TO_MATCH_PLAYERS"

    return p1_odds, p2_odds, direction


def is_doubles_name(name: Any) -> bool:
    text = str(name or "")
    return "/" in text or " & " in text or " + " in text


def normalize_match(match: Dict[str, Any]) -> Dict[str, Any]:
    event_id = match.get("event_id") or match.get("match_id") or match.get("id") or match.get("eventId")
    player1 = match.get("player1") or match.get("home") or match.get("home_team") or match.get("homeTeam") or match.get("player_a")
    player2 = match.get("player2") or match.get("away") or match.get("away_team") or match.get("awayTeam") or match.get("player_b")

    start_value = match.get("match_start") or match.get("start_time") or match.get("commence_time") or match.get("startTimestamp")
    if isinstance(start_value, (int, float)):
        try:
            start_value = datetime.utcfromtimestamp(int(start_value)).isoformat() + "Z"
        except Exception:
            start_value = None

    return {
        **match,
        "match_id": event_id,
        "event_id": event_id,
        "id": event_id,
        "player1": str(player1) if player1 is not None else None,
        "player2": str(player2) if player2 is not None else None,
        "surface": match.get("surface") or match.get("surfaceType") or match.get("court_surface") or "Hard",
        "level": match.get("level") or match.get("category") or match.get("tour") or match.get("gender"),
        "tournament": match.get("tournament") or match.get("league") or match.get("competition") or match.get("category"),
        "category": match.get("category"),
        "gender": match.get("gender") or match.get("tour_type"),
        "best_of": match.get("best_of") or 3,
        "match_start": start_value,
        "start_time": start_value,
        "is_doubles": bool(match.get("is_doubles")) or is_doubles_name(player1) or is_doubles_name(player2),
    }


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
            row = normalize_match(item)
            row.setdefault("source", str(source))
            rows.append(row)
    return rows


def load_real_matches() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    metadata: Dict[str, Any] = {"candidate_source": "legacy_real_loader", "errors": []}
    try:
        from fetch_matches import get_today_matches  # type: ignore
    except Exception as exc:
        metadata["errors"].append(f"fetch_matches_import_failed: {exc}")
        return [], metadata

    try:
        raw_matches = get_today_matches()
    except Exception as exc:
        metadata["errors"].append(f"get_today_matches_failed: {exc}")
        return [], metadata

    if not isinstance(raw_matches, list):
        metadata["errors"].append("get_today_matches_returned_non_list")
        return [], metadata

    matches = [normalize_match(item) for item in raw_matches if isinstance(item, dict)]
    matches = [m for m in matches if m.get("player1") and m.get("player2")]
    metadata["raw_match_count"] = len(raw_matches)
    metadata["normalized_match_count"] = len(matches)
    return matches, metadata


def attach_real_odds(matches: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    metadata: Dict[str, Any] = {"odds_source": "legacy_odds_api", "odds_hits": 0, "odds_misses": 0, "errors": []}
    try:
        from odds_api import fetch_odds, find_match_odds  # type: ignore
    except Exception as exc:
        metadata["errors"].append(f"odds_api_import_failed: {exc}")
        return matches, metadata

    try:
        odds_list = fetch_odds()
    except Exception as exc:
        metadata["errors"].append(f"fetch_odds_failed: {exc}")
        odds_list = []

    if not isinstance(odds_list, list):
        metadata["errors"].append("fetch_odds_returned_non_list")
        odds_list = []

    enriched: List[Dict[str, Any]] = []
    for match in matches:
        odds_data = None
        try:
            odds_data = find_match_odds(odds_list, match)
        except TypeError:
            try:
                odds_data = find_match_odds(match)
            except Exception as exc:
                metadata["errors"].append(f"find_match_odds_failed: {exc}")
        except Exception as exc:
            metadata["errors"].append(f"find_match_odds_failed: {exc}")

        p1_odds, p2_odds = extract_odds_pair(odds_data)
        p1_odds, p2_odds, direction = orient_odds_to_match_players(odds_data, match.get("player1"), match.get("player2"), p1_odds, p2_odds)

        row = dict(match)
        row["odds_player1"] = p1_odds
        row["odds_player2"] = p2_odds
        row["p1_odds"] = p1_odds
        row["p2_odds"] = p2_odds
        row["home_odds"] = p1_odds
        row["away_odds"] = p2_odds
        row["odds1"] = p1_odds
        row["odds2"] = p2_odds
        row["price1"] = p1_odds
        row["price2"] = p2_odds
        row["odds_source"] = odds_data.get("odds_source") or odds_data.get("source") if isinstance(odds_data, dict) else None
        row["bookmaker"] = odds_data.get("bookmaker") if isinstance(odds_data, dict) else None
        row["odds_matching_direction"] = direction
        row["odds_pair_available"] = p1_odds is not None and p2_odds is not None

        if row["odds_pair_available"]:
            metadata["odds_hits"] += 1
            gap = abs(p1_odds - p2_odds)
            row["odds_gap_abs"] = round(gap, 4)
            row["odds_gap_pct"] = round(gap / max(min(p1_odds, p2_odds), 0.0001), 4)
        else:
            metadata["odds_misses"] += 1
            row["no_odds_reason"] = "NO_MATCHED_WINNING_ODDS"

        enriched.append(row)

    metadata["odds_list_count"] = len(odds_list)
    return enriched, metadata


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

    matches, match_meta = load_real_matches()
    if matches:
        matches, odds_meta = attach_real_odds(matches)
        candidates = expand_match_sides(matches)
        for row in candidates:
            row["candidate_loader_meta"] = {"matches": match_meta, "odds": odds_meta}
        return candidates

    if os.getenv("CORQ_ALLOW_LOCAL_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "y"}:
        return expand_match_sides(load_json_candidates(path=None, include_default_paths=True))

    return []
