from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tennisapi_client import TennisApiClient, normalize_event, normalize_odds, parse_category_ids
from torq_tennisabstract import elo_probability, fetch_snapshot, lookup_rating

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
PUBLIC = Path("public")


def is_doubles_name(value):
    text = str(value or "")
    return " / " in text or "/" in text


def is_doubles_match(match):
    return is_doubles_name(match.get("player1")) or is_doubles_name(match.get("player2")) or is_doubles_name(match.get("match"))


def betting_day():
    now = datetime.now(LOCAL_TZ)
    return now - timedelta(days=1) if now.hour < int(os.getenv("SNAPSHOT_HOUR", "6")) else now


def clamp(v, l, h):
    return max(l, min(h, v))


def build_prediction(match, ratings, odds):
    p1, p2 = match.get("player1"), match.get("player2")
    surface = match.get("surface") or "Hard"
    tour = match.get("gender")
    doubles = is_doubles_match(match)

    r1 = lookup_rating(ratings, p1, tour, surface) if not doubles else {}
    r2 = lookup_rating(ratings, p2, tour, surface) if not doubles else {}

    long_p1 = elo_probability(r1.get("long_elo"), r2.get("long_elo"))
    short_p1 = elo_probability(r1.get("short_elo"), r2.get("short_elo"))
    long_found = long_p1 is not None
    short_found = short_p1 is not None

    if long_p1 is None and short_p1 is None:
        long_p1 = 0.5
    if long_p1 is None:
        long_p1 = short_p1

    base_p1 = long_p1 if short_p1 is None else 0.65 * long_p1 + 0.35 * short_p1
    base_p1 = clamp(base_p1, 0.15, 0.85)

    if base_p1 >= 0.5:
        pick, opponent, probability = p1, p2, base_p1
        pick_odds = odds.get("odds_player1")
        corq = long_p1 if long_found else None
        bst = short_p1 if short_found else None
    else:
        pick, opponent, probability = p2, p1, 1.0 - base_p1
        pick_odds = odds.get("odds_player2")
        corq = 1.0 - long_p1 if long_found and long_p1 is not None else None
        bst = 1.0 - short_p1 if short_found and short_p1 is not None else None

    return {
        "source": "TorqDailyRapidAPI",
        "model": "Torq Base",
        "is_doubles": doubles,
        "torq_eligible_top5": not doubles,
        "torq_eligible_b_hand": not doubles,
        "torq_long_found": long_found,
        "torq_short_found": short_found,
        "match_id": match.get("match_id"),
        "event_id": match.get("event_id") or match.get("match_id"),
        "match": f"{p1} vs {p2}",
        "pick": pick,
        "opponent": opponent,
        "player1": p1,
        "player2": p2,
        "tournament": match.get("tournament"),
        "category": match.get("category"),
        "gender": tour,
        "surface": surface,
        "best_of": match.get("best_of") or 3,
        "match_start": match.get("match_start"),
        "probability": round(probability, 3),
        "base_probability": round(probability, 3),
        "corq_ai_probability": round(corq, 3) if corq is not None else None,
        "bst_ai_probability": round(bst, 3) if bst is not None else None,
        "bst_ai_status": "OK" if bst is not None else "NO_SHORT_XML_ELO",
        "bst_ai_reason": "Doubles excluded from ELO matching" if doubles else ("Tennis Abstract season yElo available" if bst is not None else "Short XML/yElo not found"),
        "odds": pick_odds,
        "odds_player1": odds.get("odds_player1"),
        "odds_player2": odds.get("odds_player2"),
        "odds_source": odds.get("odds_source"),
        "bookmaker": odds.get("bookmaker"),
        "form_adjustment": 0.0,
        "marq_ai_signal": "NO_DATA",
        "marq_ai_reason": "RapidAPI market movement layer not available in Torq Daily v1",
        "torq_skip_reason": "DOUBLES_INFO_ONLY" if doubles else None,
        "torq_rating_match_player1": r1.get("matched_long") or r1.get("matched_short"),
        "torq_rating_match_player2": r2.get("matched_long") or r2.get("matched_short"),
        "torq_rating_tour_player1_long": r1.get("tour_long"),
        "torq_rating_tour_player2_long": r2.get("tour_long"),
        "torq_rating_tour_player1_short": r1.get("tour_short"),
        "torq_rating_tour_player2_short": r2.get("tour_short"),
    }


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    day = betting_day()
    client = TennisApiClient()
    ratings = fetch_snapshot(force=os.getenv("TORQ_FORCE_TA_REFRESH", "true").lower() == "true")
    raw_events = client.get_events_by_date(day, parse_category_ids())
    predictions = []

    for raw in raw_events:
        match = normalize_event(raw)
        if not match.get("match_id") or not match.get("player1") or not match.get("player2"):
            continue
        if str(match.get("status") or "").upper() not in {"NOT_STARTED", "UNKNOWN"}:
            continue
        odds = {}
        try:
            odds = normalize_odds(client.get_winning_odds(int(match["match_id"])))
        except Exception as exc:
            print("ODDS ERROR", match.get("match_id"), exc)
        predictions.append(build_prediction(match, ratings, odds))

    predictions.sort(key=lambda x: (x.get("is_doubles", False), -x.get("probability", 0)))
    date_key = day.strftime("%Y-%m-%d")
    data = json.dumps(predictions, ensure_ascii=False, indent=2)
    (PUBLIC / f"all_predictions_{date_key}.json").write_text(data, encoding="utf-8")
    (PUBLIC / "all_predictions_latest.json").write_text(data, encoding="utf-8")

    singles = sum(1 for x in predictions if not x.get("is_doubles"))
    doubles = sum(1 for x in predictions if x.get("is_doubles"))
    long_found = sum(1 for x in predictions if x.get("torq_long_found"))
    short_found = sum(1 for x in predictions if x.get("torq_short_found"))
    odds_found = sum(1 for x in predictions if x.get("odds") is not None)

    print("TORQ DAILY DONE", "date", date_key, "matches", len(raw_events), "predictions", len(predictions), "singles", singles, "doubles", doubles, "long_found", long_found, "short_found", short_found, "odds_found", odds_found)


if __name__ == "__main__":
    main()
