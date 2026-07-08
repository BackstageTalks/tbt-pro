from __future__ import annotations
import json, os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from tennisapi_client import TennisApiClient, normalize_event, normalize_odds, parse_category_ids
from torq_tennisabstract import elo_probability, fetch_snapshot, lookup_rating
LOCAL_TZ = ZoneInfo("Europe/Bratislava"); PUBLIC = Path("public")
def betting_day():
    now = datetime.now(LOCAL_TZ)
    return now - timedelta(days=1) if now.hour < int(os.getenv("SNAPSHOT_HOUR", "6")) else now
def clamp(v,l,h): return max(l, min(h, v))
def build_prediction(match, ratings, odds):
    p1, p2 = match.get("player1"), match.get("player2"); surface = match.get("surface") or "Hard"; tour = match.get("gender")
    r1, r2 = lookup_rating(ratings, p1, tour, surface), lookup_rating(ratings, p2, tour, surface)
    long_p1, short_p1 = elo_probability(r1.get("long_elo"), r2.get("long_elo")), elo_probability(r1.get("short_elo"), r2.get("short_elo"))
    if long_p1 is None and short_p1 is None: long_p1 = 0.5
    if long_p1 is None: long_p1 = short_p1
    base_p1 = long_p1 if short_p1 is None else 0.65 * long_p1 + 0.35 * short_p1
    base_p1 = clamp(base_p1, 0.15, 0.85)
    if base_p1 >= 0.5:
        pick, opp, prob, po, corq, bst = p1, p2, base_p1, odds.get("odds_player1"), long_p1, short_p1
    else:
        pick, opp, prob, po, corq, bst = p2, p1, 1-base_p1, odds.get("odds_player2"), 1-long_p1 if long_p1 is not None else None, 1-short_p1 if short_p1 is not None else None
    return {"source":"TorqDailyRapidAPI", "model":"Torq Base", "match_id":match.get("match_id"), "event_id":match.get("event_id") or match.get("match_id"), "match":f"{p1} vs {p2}", "pick":pick, "opponent":opp, "player1":p1, "player2":p2, "tournament":match.get("tournament"), "category":match.get("category"), "gender":tour, "surface":surface, "best_of":match.get("best_of") or 3, "match_start":match.get("match_start"), "probability":round(prob,3), "base_probability":round(prob,3), "corq_ai_probability":round(corq,3) if corq is not None else None, "bst_ai_probability":round(bst,3) if bst is not None else None, "bst_ai_status":"OK" if bst is not None else "NO_SHORT_XML_ELO", "bst_ai_reason":"Tennis Abstract season yElo available" if bst is not None else "Short XML/yElo not found", "odds":po, "odds_player1":odds.get("odds_player1"), "odds_player2":odds.get("odds_player2"), "odds_source":odds.get("odds_source"), "bookmaker":odds.get("bookmaker"), "form_adjustment":0.0, "marq_ai_signal":"NO_DATA", "marq_ai_reason":"RapidAPI market movement layer not available in Torq Daily v1"}
def main():
    PUBLIC.mkdir(parents=True, exist_ok=True); day = betting_day(); client = TennisApiClient(); ratings = fetch_snapshot(force=os.getenv("TORQ_FORCE_TA_REFRESH", "false").lower() == "true"); raw_events = client.get_events_by_date(day, parse_category_ids()); predictions = []
    for raw in raw_events:
        match = normalize_event(raw)
        if not match.get("match_id") or not match.get("player1") or not match.get("player2"): continue
        if str(match.get("status") or "").upper() not in {"NOT_STARTED", "UNKNOWN"}: continue
        odds = {}
        try: odds = normalize_odds(client.get_winning_odds(int(match["match_id"])))
        except Exception as exc: print("ODDS ERROR", match.get("match_id"), exc)
        predictions.append(build_prediction(match, ratings, odds))
    predictions.sort(key=lambda x: x.get("probability", 0), reverse=True); dk = day.strftime("%Y-%m-%d"); data = json.dumps(predictions, ensure_ascii=False, indent=2)
    (PUBLIC / f"all_predictions_{dk}.json").write_text(data, encoding="utf-8"); (PUBLIC / "all_predictions_latest.json").write_text(data, encoding="utf-8")
    print("TORQ DAILY DONE", "date", dk, "matches", len(raw_events), "predictions", len(predictions))
if __name__ == "__main__": main()
