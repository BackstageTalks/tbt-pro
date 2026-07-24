"""CORQ odds helpers using the clean RapidAPI PRO client."""

from __future__ import annotations

from typing import Any, Dict, Optional

from thinq.loaders.rapidapi_client import RapidApiClient, normalize_winner_odds_payload


def get_event_odds(event_id: Any) -> Optional[Dict[str, Any]]:
    client = RapidApiClient()
    return client.get_event_odds(event_id)


def enrich_match_with_odds(match: Dict[str, Any]) -> Dict[str, Any]:
    event_id = match.get("event_id") or match.get("match_id") or match.get("id")
    odds = get_event_odds(event_id)
    enriched = dict(match)
    if not odds:
        enriched["odds_pair_available"] = False
        enriched["no_odds_reason"] = "NO_RAPIDAPI_PRO_ODDS"
        return enriched
    p1 = odds.get("odds_player1")
    p2 = odds.get("odds_player2")
    enriched.update({
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
        "odds_pair_available": p1 is not None and p2 is not None,
    })
    return enriched
