"""
Build THINQ Snapshot

Creates thinq/outputs/thinq_snapshot.json for a list of matches.
CORQ can read this snapshot instead of calling individual loaders directly.

Input match format:
[
  {
    "player1": "Player A",
    "player2": "Player B",
    "surface": "Clay",
    "level": "ATP250",
    "tour_type": "atp",
    "best_of": 3,
    "event_id": 123
  }
]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .thinq_service import ThinqService
except ImportError:
    from thinq_service import ThinqService


def load_matches(path: str) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ["matches", "events", "data"]:
            if isinstance(data.get(key), list):
                return data[key]
    if isinstance(data, list):
        return data
    raise ValueError("Input file must contain a list or a dict with matches/events/data list")


def build_snapshot(
    matches: List[Dict[str, Any]],
    output_path: str = "thinq/outputs/thinq_snapshot.json",
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    service = ThinqService()
    results = []
    errors = []

    for match in matches:
        try:
            player1 = match.get("player1") or match.get("home") or match.get("home_player")
            player2 = match.get("player2") or match.get("away") or match.get("away_player")
            if not player1 or not player2:
                raise ValueError("match is missing player1/player2")

            result = service.build_match_features(
                player1=player1,
                player2=player2,
                surface=match.get("surface"),
                level=match.get("level"),
                tournament_url=match.get("tournament_url"),
                tour_type=match.get("tour_type") or match.get("type"),
                as_of_date=as_of_date or match.get("date"),
                event_id=match.get("event_id") or match.get("eventId"),
                player1_id=match.get("player1_id") or match.get("player1Id"),
                player2_id=match.get("player2_id") or match.get("player2Id"),
                tournament_id=match.get("tournament_id") or match.get("tournamentId"),
                best_of=int(match.get("best_of") or match.get("bestOf") or 3),
            )
            result["match_input"] = match
            results.append(result)
        except Exception as exc:
            errors.append({"match": match, "error": str(exc)})

    snapshot = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "thinq_role": "intelligence_layer",
        "snapshot_version": "full_integration_v1",
        "count": len(results),
        "error_count": len(errors),
        "matches": results,
        "errors": errors,
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON file with matches")
    parser.add_argument("--output", default="thinq/outputs/thinq_snapshot.json")
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()
    matches = load_matches(args.input)
    snapshot = build_snapshot(matches, output_path=args.output, as_of_date=args.as_of_date)
    print(json.dumps({"count": snapshot["count"], "error_count": snapshot["error_count"], "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
