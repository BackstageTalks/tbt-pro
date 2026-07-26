from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

ATP_RANKINGS_URL = "https://tennisabstract.com/reports/atpRankings.html"
WTA_RANKINGS_URL = "https://tennisabstract.com/reports/wtaRankings.html"
DEFAULT_OUTPUT = Path("thinq/data/rankings/ta_rankings.json")

_TRANSLATE = str.maketrans({
    "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D",
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th",
    "ß": "ss",
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "Ae",
    "œ": "oe", "Œ": "Oe",
})


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.current_cell: List[str] = []
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag in {"td", "th"} and self.in_tr:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self.in_cell:
            text = " ".join("".join(self.current_cell).split())
            self.current_row.append(unescape(text))
            self.in_cell = False
            self.current_cell = []
        elif tag == "tr" and self.in_tr:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_tr = False
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower().translate(_TRANSLATE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(".", " ").replace("-", " ").replace("_", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "TBT-PRO-TA-Rankings/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def _last_update(html: str) -> Optional[str]:
    match = re.search(r"Last update:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", html, flags=re.I)
    return match.group(1) if match else None


def _parse_rankings_html(html: str, tour: str, source_url: str) -> Dict[str, Dict[str, Any]]:
    parser = _TableParser()
    parser.feed(html)
    players: Dict[str, Dict[str, Any]] = {}
    last_update = _last_update(html)

    for row in parser.rows:
        if len(row) < 2:
            continue
        try:
            rank = int(str(row[0]).strip())
        except Exception:
            continue
        player = str(row[1]).strip()
        if not player or player.lower() == "player":
            continue
        country = str(row[2]).strip() if len(row) >= 3 else ""
        birthdate = str(row[3]).strip() if len(row) >= 4 else ""
        key = normalize_name(player)
        if not key:
            continue
        players[key] = {
            "rank": rank,
            "player": player,
            "tour": tour,
            "country": country,
            "birthdate": birthdate,
            "source": source_url,
            "source_last_update": last_update,
        }
    return players


def build_rankings() -> Dict[str, Any]:
    sources = {"atp": ATP_RANKINGS_URL, "wta": WTA_RANKINGS_URL}
    players: Dict[str, Dict[str, Any]] = {}
    source_updates: Dict[str, Optional[str]] = {}

    for tour, url in sources.items():
        html = _fetch_text(url)
        source_updates[tour] = _last_update(html)
        players.update(_parse_rankings_html(html, tour=tour, source_url=url))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "source_last_updates": source_updates,
        "players": players,
        "player_count": len(players),
    }


def save_rankings(output_path: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    payload = build_rankings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def load_rankings(path: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    if not path.exists():
        return {"players": {}, "player_count": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_player_rank(player_name: Any, rankings: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    rankings = rankings if rankings is not None else load_rankings()
    players = rankings.get("players") if isinstance(rankings, dict) else {}
    if not isinstance(players, dict):
        return None
    key = normalize_name(player_name)
    if key in players:
        return players[key]

    compact = _compact_name(player_name)
    if not compact:
        return None

    # Safe fallback: compact full-name match only. Avoid surname-only matching to prevent collisions.
    for candidate_key, record in players.items():
        if _compact_name(candidate_key) == compact:
            return record
    return None


def rank_display(rank_record: Optional[Dict[str, Any]]) -> str:
    if not rank_record or rank_record.get("rank") in (None, ""):
        return "(X)"
    return f"({int(rank_record['rank'])})"


def enrich_row_with_ta_ranks(row: Dict[str, Any], rankings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rankings = rankings if rankings is not None else load_rankings()
    pick_name = row.get("pick") or row.get("player") or row.get("player_name")
    opponent_name = row.get("opponent") or row.get("opp") or row.get("opponent_name")

    pick_rank = lookup_player_rank(pick_name, rankings) if pick_name else None
    opponent_rank = lookup_player_rank(opponent_name, rankings) if opponent_name else None

    row["pick_ta_rank"] = pick_rank.get("rank") if pick_rank else None
    row["opponent_ta_rank"] = opponent_rank.get("rank") if opponent_rank else None
    row["pick_ta_rank_display"] = rank_display(pick_rank)
    row["opponent_ta_rank_display"] = rank_display(opponent_rank)
    row["pick_ta_rank_tour"] = pick_rank.get("tour") if pick_rank else None
    row["opponent_ta_rank_tour"] = opponent_rank.get("tour") if opponent_rank else None
    row["ta_rankings_generated_at"] = rankings.get("generated_at") if isinstance(rankings, dict) else None
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Tennis Abstract ATP/WTA rankings cache.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    args = parser.parse_args()
    payload = save_rankings(Path(args.output))
    print(f"TA rankings updated: players={payload.get('player_count')} output={args.output}")


if __name__ == "__main__":
    main()
