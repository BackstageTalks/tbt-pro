"""CORQ odds resolver.

Temporary home for odds until MARQ becomes the official market layer.
This module is intentionally conservative:
- uses existing root odds_api.py if available
- preserves both sides of the match odds
- never fabricates odds
- writes explicit status/source fields
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import re
import unicodedata


def to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def first_present(item: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def same_player(a: Any, b: Any) -> bool:
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


def extract_pair(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    p1 = to_float(first_present(item, (
        "odds_player1", "p1_odds", "home_odds", "odds1", "price1", "home_price",
        "player1_odds", "homeDecimalOdds", "home_decimal_odds",
    )))
    p2 = to_float(first_present(item, (
        "odds_player2", "p2_odds", "away_odds", "odds2", "price2", "away_price",
        "player2_odds", "awayDecimalOdds", "away_decimal_odds",
    )))
    return p1, p2


def orient_pick_odds(match: Dict[str, Any], p1: Optional[float], p2: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    pick = match.get("pick")
    player1 = match.get("player1")
    player2 = match.get("player2")
    if p1 is None and p2 is None:
        return None, None
    if same_player(pick, player1):
        return p1, p2
    if same_player(pick, player2):
        return p2, p1
    # Fallback: keep existing pick/opponent odds if present.
    return to_float(match.get("pick_odds") or match.get("odds")), to_float(match.get("opponent_odds"))


def apply_odds_fields(match: Dict[str, Any], odds_payload: Optional[Dict[str, Any]], source_hint: str = "existing") -> Dict[str, Any]:
    enriched = dict(match)
    payload = odds_payload or {}

    p1, p2 = extract_pair(payload)
    if p1 is None and p2 is None:
        p1, p2 = extract_pair(match)

    pick_odds, opponent_odds = orient_pick_odds(match, p1, p2)

    # Final fallback: existing direct fields.
    if pick_odds is None:
        pick_odds = to_float(match.get("pick_odds") or match.get("odds"))
    if opponent_odds is None:
        opponent_odds = to_float(match.get("opponent_odds"))

    enriched.update({
        "odds_player1": p1,
        "odds_player2": p2,
        "p1_odds": p1,
        "p2_odds": p2,
        "home_odds": p1,
        "away_odds": p2,
        "pick_odds": pick_odds,
        "opponent_odds": opponent_odds,
        "odds": pick_odds,
        "odds_source": payload.get("odds_source") or payload.get("source") or match.get("odds_source") or source_hint,
        "bookmaker": payload.get("bookmaker") or match.get("bookmaker") or "TennisApi",
        "odds_status": "OK" if pick_odds is not None else "NO_ODDS",
        "odds_pair_available": pick_odds is not None and opponent_odds is not None,
    })
    if pick_odds is not None and opponent_odds is not None:
        try:
            enriched["odds_gap_abs"] = round(abs(pick_odds - opponent_odds), 4)
            enriched["odds_gap_pct"] = round(abs(pick_odds - opponent_odds) / min(pick_odds, opponent_odds), 4)
        except Exception:
            pass
    return enriched


def fetch_external_odds(match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetch odds via existing odds_api.py without making it a hard dependency."""
    try:
        import odds_api
    except Exception as exc:
        return {"odds_status": "ODDS_API_IMPORT_ERROR", "odds_error": str(exc)}

    for function_name in ("get_match_odds", "get_odds", "get_odds_for_match"):
        function = getattr(odds_api, function_name, None)
        if callable(function):
            try:
                result = function(match)
                if isinstance(result, dict) and result:
                    return result
            except Exception as exc:
                return {"odds_status": "ODDS_LOOKUP_ERROR", "odds_error": str(exc)}
    return None


def enrich_odds(match: Dict[str, Any]) -> Dict[str, Any]:
    """Return match enriched with pick_odds and opponent_odds.

    ALL may keep matches without odds. CORQ production ranking will filter them later.
    """
    # If match already has both sides, normalize and return.
    existing_pair = extract_pair(match)
    if existing_pair[0] is not None or existing_pair[1] is not None or match.get("pick_odds") is not None:
        return apply_odds_fields(match, None, source_hint=match.get("odds_source") or "existing")

    payload = fetch_external_odds(match)
    if payload and payload.get("odds_status") in ("ODDS_API_IMPORT_ERROR", "ODDS_LOOKUP_ERROR"):
        enriched = dict(match)
        enriched.update(payload)
        enriched.setdefault("odds_pair_available", False)
        return enriched
    return apply_odds_fields(match, payload, source_hint="TennisApi")
