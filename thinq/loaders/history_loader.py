"""THINQ History loader.

Broad recent-form data layer.

This loader intentionally supports multiple simple local formats so the runtime
can work with existing data caches without forcing one final data schema yet.
It never blocks CORQ. If no history source exists, it returns explicit NO_DATA.

Supported folders:
- thinq/data
- data/thinq
- data/history
- data/sackmann
- data

Supported files:
- CSV and JSON files whose names contain history, matches, tennisabstract, sackmann, results

Supported row styles:
- winner / loser
- winner_name / loser_name
- player1 / player2 + winner
- homeTeam / awayTeam + winnerCode-like fields, if flattened
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SEARCH_DIRS = [
    Path("thinq/data"),
    Path("data/thinq"),
    Path("data/history"),
    Path("data/sackmann"),
    Path("data"),
]

FILE_HINTS = ("history", "matches", "tennisabstract", "sackmann", "results")

_TRANSLATE = str.maketrans(
    {
        "ł": "l", "Ł": "L",
        "đ": "d", "Đ": "D",
        "ð": "d", "Ð": "D",
        "þ": "th", "Þ": "Th",
        "ß": "ss",
        "ø": "o", "Ø": "O",
        "æ": "ae", "Æ": "Ae",
        "œ": "oe", "Œ": "Oe",
    }
)


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().translate(_TRANSLATE).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(".", " ").replace("-", " ").replace("_", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except Exception:
        return None


def first_present(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        low = key.lower()
        if low in lowered and lowered[low] not in (None, ""):
            return lowered[low]
    return None


def parse_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return text[:10] if len(text) >= 10 else None


def discover_history_files() -> List[Path]:
    files: List[Path] = []
    for folder in SEARCH_DIRS:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".csv", ".json"}:
                continue
            name = path.name.lower()
            if any(hint in name for hint in FILE_HINTS):
                files.append(path)
    return sorted(files)


def load_csv(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except Exception:
        return []


def load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("matches", "events", "results", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def normalize_surface_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return str(value or "Unknown").strip() or "Unknown"


def normalize_match_row(row: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    winner = first_present(row, ("winner", "winner_name", "Winner", "w_name", "wplayer", "winner_player"))
    loser = first_present(row, ("loser", "loser_name", "Loser", "l_name", "lplayer", "loser_player"))

    if not winner or not loser:
        player1 = first_present(row, ("player1", "home", "homeTeam", "home_team", "p1", "Player1"))
        player2 = first_present(row, ("player2", "away", "awayTeam", "away_team", "p2", "Player2"))
        winner_name = first_present(row, ("winner", "winner_name", "winning_player"))
        winner_code = first_present(row, ("winnerCode", "winner_code"))
        if player1 and player2 and winner_name:
            if normalize_name(winner_name) == normalize_name(player1):
                winner, loser = player1, player2
            elif normalize_name(winner_name) == normalize_name(player2):
                winner, loser = player2, player1
        elif player1 and player2 and str(winner_code) in {"1", "2"}:
            winner, loser = (player1, player2) if str(winner_code) == "1" else (player2, player1)

    if not winner or not loser:
        return None

    match_date = parse_date(first_present(row, ("date", "Date", "match_date", "start_date", "tourney_date")))
    surface = normalize_surface_label(first_present(row, ("surface", "Surface", "surfaceType", "groundType", "court_surface")))
    tournament = first_present(row, ("tournament", "Tournament", "tourney_name", "event", "competition"))
    level = first_present(row, ("level", "Level", "tour", "category", "tourney_level"))
    winner_rank = as_int(first_present(row, ("winner_rank", "wrank", "w_rank", "WinnerRank")))
    loser_rank = as_int(first_present(row, ("loser_rank", "lrank", "l_rank", "LoserRank")))

    return {
        "date": match_date,
        "winner": str(winner).strip(),
        "loser": str(loser).strip(),
        "winner_key": normalize_name(winner),
        "loser_key": normalize_name(loser),
        "surface": surface,
        "tournament": str(tournament) if tournament is not None else None,
        "level": str(level) if level is not None else None,
        "winner_rank": winner_rank,
        "loser_rank": loser_rank,
        "source": source,
    }


@lru_cache(maxsize=1)
def load_history_matches() -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for path in discover_history_files():
        rows = load_csv(path) if path.suffix.lower() == ".csv" else load_json(path)
        for row in rows:
            parsed = normalize_match_row(row, str(path))
            if parsed:
                matches.append(parsed)
    matches.sort(key=lambda item: item.get("date") or "", reverse=True)
    return matches


def player_matches(player: str, limit: int = 50, surface: Optional[str] = None) -> List[Dict[str, Any]]:
    key = normalize_name(player)
    wanted_surface = normalize_surface_label(surface) if surface else None
    output: List[Dict[str, Any]] = []
    for match in load_history_matches():
        if match.get("winner_key") != key and match.get("loser_key") != key:
            continue
        if wanted_surface and match.get("surface") != wanted_surface:
            continue
        output.append(match)
        if len(output) >= limit:
            break
    return output


def available_history_sources() -> List[str]:
    return [str(path) for path in discover_history_files()]
