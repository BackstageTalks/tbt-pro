"""CORQ odds helpers using the clean RapidAPI PRO client.

Lean wrapper: the robust TennisApi PRO endpoint chain lives in
thinq.loaders.rapidapi_client.RapidApiClient.get_event_odds().

This module adds a second local orientation pass using corq.name_match so CORQ
can tolerate common odds-label differences such as first/last reversal, initials
and Liudmila/Ludmila-style spelling variants.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from corq.name_match import name_match_score
from thinq.loaders.rapidapi_client import RapidApiClient, orient_odds_to_match as _client_orient_odds_to_match


def _as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return None
        val = float(str(value).replace(",", "."))
        return val if val > 1.0 else None
    except Exception:
        return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _match_player1_name(match: Dict[str, Any]) -> str:
    return str(_first_present(match.get("player1"), match.get("home"), match.get("home_name"), match.get("homeTeamName")) or "")


def _match_player2_name(match: Dict[str, Any]) -> str:
    return str(_first_present(match.get("player2"), match.get("away"), match.get("away_name"), match.get("awayTeamName")) or "")


def _odds_label1(odds: Dict[str, Any]) -> str:
    return str(_first_present(
        odds.get("player1_label"), odds.get("home_label"), odds.get("outcome1_label"),
        odds.get("label1"), odds.get("name1"), odds.get("player1"), odds.get("home"),
    ) or "")


def _odds_label2(odds: Dict[str, Any]) -> str:
    return str(_first_present(
        odds.get("player2_label"), odds.get("away_label"), odds.get("outcome2_label"),
        odds.get("label2"), odds.get("name2"), odds.get("player2"), odds.get("away"),
    ) or "")


def _odds_price1(odds: Dict[str, Any]) -> Optional[float]:
    return _as_float(_first_present(
        odds.get("player1_odds"), odds.get("home_odds"), odds.get("odds1"), odds.get("price1"),
        odds.get("player1_price"), odds.get("home_price"), odds.get("outcome1_price"),
    ))


def _odds_price2(odds: Dict[str, Any]) -> Optional[float]:
    return _as_float(_first_present(
        odds.get("player2_odds"), odds.get("away_odds"), odds.get("odds2"), odds.get("price2"),
        odds.get("player2_price"), odds.get("away_price"), odds.get("outcome2_price"),
    ))


def robust_orient_odds_to_match(match: Dict[str, Any], odds: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], str, float, float]:
    """Orient odds to API player1/player2 with a CORQ-local robust matcher.

    Returns player1 odds, player2 odds, direction, direct score and reverse score.
    It first tries the original RapidAPI client helper. If scores/direction are
    uncertain, it re-evaluates labels using corq.name_match.
    """
    try:
        p1, p2, direction, direct_score, reverse_score = _client_orient_odds_to_match(match, odds)
        if p1 is not None and p2 is not None and direction in {
            "DIRECT_TO_MATCH_PLAYERS",
            "REVERSED_TO_MATCH_PLAYERS",
            "DIRECT_BY_NUMERIC_OUTCOME",
            "REVERSED_BY_NUMERIC_OUTCOME",
        }:
            return p1, p2, direction, float(direct_score or 0.0), float(reverse_score or 0.0)
    except Exception:
        p1 = p2 = None
        direction = "CLIENT_ORIENT_FAILED"
        direct_score = reverse_score = 0.0

    m1 = _match_player1_name(match)
    m2 = _match_player2_name(match)
    l1 = _odds_label1(odds)
    l2 = _odds_label2(odds)
    price1 = _odds_price1(odds)
    price2 = _odds_price2(odds)

    if price1 is None or price2 is None:
        return None, None, "NO_NUMERIC_PAIR", 0.0, 0.0

    if not (m1 and m2 and l1 and l2):
        # No labels to verify, but pair exists. Keep client direction if present.
        return price1, price2, "DIRECT_BY_NUMERIC_OUTCOME", 0.0, 0.0

    direct = (name_match_score(m1, l1) + name_match_score(m2, l2)) / 2.0
    reverse = (name_match_score(m1, l2) + name_match_score(m2, l1)) / 2.0

    if direct >= 0.78 and direct >= reverse:
        return price1, price2, "DIRECT_TO_MATCH_PLAYERS_ROBUST", round(direct, 4), round(reverse, 4)
    if reverse >= 0.78:
        return price2, price1, "REVERSED_TO_MATCH_PLAYERS_ROBUST", round(direct, 4), round(reverse, 4)

    return None, None, "LABEL_MISMATCH", round(direct, 4), round(reverse, 4)


def get_event_odds(event_id: Any, match: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    client = RapidApiClient()
    return client.get_event_odds(event_id, match=match)


def enrich_match_with_odds(match: Dict[str, Any]) -> Dict[str, Any]:
    client = RapidApiClient()
    event_id = match.get("event_id") or match.get("match_id") or match.get("id")
    odds = client.get_event_odds(event_id, match=match)
    enriched = dict(match)

    if not odds:
        enriched.update({
            "odds_status": "MISSING",
            "odds_attempts": list(getattr(client, "last_odds_attempts", [])),
            "odds_pair_available": False,
            "odds_labels_confirmed": False,
            "odds_matching_direction": "NO_ODDS",
            "no_odds_reason": "NO_RAPIDAPI_PRO_ODDS",
        })
        return enriched

    p1, p2, direction, direct_score, reverse_score = robust_orient_odds_to_match(match, odds)
    enriched.update({
        "odds_matching_direction": direction,
        "odds_label_1": odds.get("player1_label") or _odds_label1(odds),
        "odds_label_2": odds.get("player2_label") or _odds_label2(odds),
        "odds_direct_match_score": direct_score,
        "odds_reverse_match_score": reverse_score,
        "odds_player1": p1,
        "odds_player2": p2,
        "p1_odds": p1,
        "p2_odds": p2,
        "home_odds": p1,
        "away_odds": p2,
        "odds1": p1,
        "odds2": p2,
        "price1": p1,
        "price2": p2,
        "odds_source": odds.get("odds_source"),
        "odds_endpoint": odds.get("odds_endpoint"),
        "odds_status": odds.get("odds_status", "OK"),
        "odds_attempts": odds.get("odds_attempts", []),
        "odds_pair_available": p1 is not None and p2 is not None,
        "odds_labels_confirmed": direction in {
            "DIRECT_TO_MATCH_PLAYERS",
            "REVERSED_TO_MATCH_PLAYERS",
            "DIRECT_BY_NUMERIC_OUTCOME",
            "REVERSED_BY_NUMERIC_OUTCOME",
            "DIRECT_TO_MATCH_PLAYERS_ROBUST",
            "REVERSED_TO_MATCH_PLAYERS_ROBUST",
        },
    })

    if p1 is not None and p2 is not None:
        try:
            gap = abs(float(p1) - float(p2))
            enriched["odds_gap_abs"] = round(gap, 4)
            enriched["odds_gap_pct"] = round(gap / max(min(float(p1), float(p2)), 0.0001), 4)
        except Exception:
            pass
    else:
        enriched.setdefault("no_odds_reason", direction)
    return enriched
