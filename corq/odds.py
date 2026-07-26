"""CORQ odds helpers using the clean RapidAPI PRO client.

This module deliberately stays lean: the robust TennisApi PRO endpoint chain
lives in thinq.loaders.rapidapi_client.RapidApiClient.get_event_odds().
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from thinq.loaders.rapidapi_client import RapidApiClient, orient_odds_to_match


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

    p1, p2, direction, direct_score, reverse_score = orient_odds_to_match(match, odds)
    enriched.update({
        "odds_matching_direction": direction,
        "odds_label_1": odds.get("player1_label"),
        "odds_label_2": odds.get("player2_label"),
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
        },
    })

    if p1 is not None and p2 is not None:
        try:
            gap = abs(float(p1) - float(p2))
            enriched["odds_gap_abs"] = round(gap, 4)
            enriched["odds_gap_pct"] = round(gap / max(min(float(p1), float(p2)), 0.0001), 4)
        except Exception:
            pass

    return enriched
