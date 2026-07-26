from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HISTORY_SEARCH_DIRS = [
    Path("data/history"),
    Path("thinq/data/history"),
    Path("data/sackmann"),
    Path("thinq/data/sackmann"),
    Path("data/results_history"),
    Path("outputs/results"),
    Path("outputs/results/all"),
    Path("outputs/results/corq"),
    Path("outputs/snapshots/all"),
    Path("outputs/snapshots"),
]

HISTORY_FILE_PATTERNS = ("*.csv", "*.json", "*.jsonl")

_SURFACE_MAP = {
    "hard": "Hard",
    "outdoor hard": "Hard",
    "indoor hard": "Hard",
    "clay": "Clay",
    "red clay": "Clay",
    "green clay": "Clay",
    "grass": "Grass",
    "carpet": "Carpet",
    "carpet indoor": "Carpet",
}

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


def _name_from_obj(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in (
            "name", "fullName", "full_name", "displayName", "display_name",
            "shortName", "short_name", "slug",
        ):
            if value.get(key):
                return str(value.get(key))
        return ""
    return str(value)


def normalize_name(value: Any) -> str:
    text = _name_from_obj(value).strip().lower().translate(_TRANSLATE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(".", " ").replace("-", " ").replace("_", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_surface(value: Any) -> str:
    raw = str(value or "").strip()
    key = raw.lower()
    if key in _SURFACE_MAP:
        return _SURFACE_MAP[key]
    for marker, normalized in _SURFACE_MAP.items():
        if marker in key:
            return normalized
    return raw.title() if raw else "Unknown"


def _clean_key(k: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(k or "").lower())


def _norm_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for k, v in row.items():
        out[_clean_key(k)] = v
    return out


def _first(row: Dict[str, Any], names: List[str]) -> Any:
    for name in names:
        if name in row and row.get(name) not in (None, ""):
            return row.get(name)
        ck = _clean_key(name)
        if ck in row and row.get(ck) not in (None, ""):
            return row.get(ck)
    return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except Exception:
        return None


def _parse_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if re.fullmatch(r"\d{10}", text):
        try:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(int(text), tz=timezone.utc).date().isoformat()
        except Exception:
            pass
    if len(text) >= 10 and text[4:5] == "-":
        return text[:10]
    return text


@dataclass(frozen=True)
class HistoryMatch:
    date: str
    winner: str
    loser: str
    surface: str = "Unknown"
    level: str = ""
    tournament: str = ""
    winner_rank: Optional[int] = None
    loser_rank: Optional[int] = None
    source_file: str = ""

    @property
    def winner_key(self) -> str:
        return normalize_name(self.winner)

    @property
    def loser_key(self) -> str:
        return normalize_name(self.loser)

    def involves(self, player_key: str) -> bool:
        return player_key in {self.winner_key, self.loser_key}

    def player_won(self, player_key: str) -> Optional[bool]:
        if self.winner_key == player_key:
            return True
        if self.loser_key == player_key:
            return False
        return None

    def opponent_rank_for(self, player_key: str) -> Optional[int]:
        if self.winner_key == player_key:
            return self.loser_rank
        if self.loser_key == player_key:
            return self.winner_rank
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _candidate_files() -> List[Path]:
    files: List[Path] = []
    for root in HISTORY_SEARCH_DIRS:
        if root.exists():
            for pattern in HISTORY_FILE_PATTERNS:
                files.extend(root.rglob(pattern))
    return sorted(set(files))


def _score_current(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        return _to_int(value.get("current") or value.get("score") or value.get("sets"))
    return _to_int(value)


def _match_from_row(raw_row: Dict[str, Any], source: Path) -> Optional[HistoryMatch]:
    row = _norm_row(raw_row)

    winner = _first(row, [
        "winner_name", "winner", "winnerName", "match_winner", "matchWinner",
        "player_won", "winner_player", "winnerplayer", "winnerTeam", "winner_team",
    ])
    loser = _first(row, [
        "loser_name", "loser", "loserName", "match_loser", "matchLoser",
        "loser_player", "loserplayer", "loserTeam", "loser_team",
    ])

    p1 = _first(row, ["player1", "player_1", "home", "home_player", "homeTeam", "home_name", "home_name_full", "p1", "Player 1"])
    p2 = _first(row, ["player2", "player_2", "away", "away_player", "awayTeam", "away_name", "away_name_full", "p2", "Player 2"])
    p1_name = _name_from_obj(p1)
    p2_name = _name_from_obj(p2)

    winner_code = _to_int(_first(row, ["winnerCode", "winner_code", "winnercode"]))
    if (not winner or not loser) and p1_name and p2_name and winner_code in {1, 2}:
        if winner_code == 1:
            winner, loser = p1_name, p2_name
        else:
            winner, loser = p2_name, p1_name

    if (not loser) and p1_name and p2_name and winner:
        wkey = normalize_name(winner)
        if wkey == normalize_name(p1_name):
            loser = p2_name
        elif wkey == normalize_name(p2_name):
            loser = p1_name

    if (not winner or not loser) and p1_name and p2_name:
        home_score = _score_current(_first(row, ["homeScore", "home_score", "p1_score", "homeCurrent", "homescorecurrent"]))
        away_score = _score_current(_first(row, ["awayScore", "away_score", "p2_score", "awayCurrent", "awayscorecurrent"]))
        if home_score is not None and away_score is not None and home_score != away_score:
            if home_score > away_score:
                winner, loser = p1_name, p2_name
            else:
                winner, loser = p2_name, p1_name

    if not winner or not loser:
        return None

    date_value = _first(row, [
        "tourney_date", "date", "match_date", "startDate", "start_date", "start_time",
        "startTimestamp", "start_timestamp", "time", "Date",
    ])

    return HistoryMatch(
        date=_parse_date(date_value),
        winner=_name_from_obj(winner),
        loser=_name_from_obj(loser),
        surface=normalize_surface(_first(row, ["surface", "surfaceType", "court", "court_surface", "Surface"])),
        level=str(_first(row, ["tourney_level", "level", "category", "tour", "competition", "Level"]) or ""),
        tournament=str(_first(row, ["tourney_name", "tournament", "event", "competition_name", "Tournament"]) or ""),
        winner_rank=_to_int(_first(row, ["winner_rank", "winnerRank", "winner_ranking", "wrank"])),
        loser_rank=_to_int(_first(row, ["loser_rank", "loserRank", "loser_ranking", "lrank"])),
        source_file=str(source),
    )


def _matches_from_json_payload(payload: Any, source: Path) -> List[HistoryMatch]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("matches", "results", "items", "data", "events", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                records = [x for x in value if isinstance(x, dict)]
                break
        if not records:
            records = [payload]

    out: List[HistoryMatch] = []
    for record in records:
        match = _match_from_row(record, source)
        if match and match.date:
            out.append(match)
    return out


@lru_cache(maxsize=1)
def load_history_matches() -> Tuple[HistoryMatch, ...]:
    out: List[HistoryMatch] = []
    for path in _candidate_files():
        if path.name == "bootstrap_manifest.json":
            continue
        try:
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        match = _match_from_row(row, path)
                        if match and match.date:
                            out.append(match)
            elif path.suffix.lower() == ".jsonl":
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        match = _match_from_row(json.loads(line), path)
                        if match and match.date:
                            out.append(match)
            elif path.suffix.lower() == ".json":
                out.extend(_matches_from_json_payload(json.loads(path.read_text(encoding="utf-8")), path))
        except Exception:
            continue

    out.sort(key=lambda m: m.date or "", reverse=True)
    return tuple(out)


def get_player_matches(player: str, limit: Optional[int] = None) -> List[HistoryMatch]:
    key = normalize_name(player)
    matches = [m for m in load_history_matches() if m.involves(key)]
    return matches[:limit] if limit else matches


def history_data_status() -> Dict[str, Any]:
    files = _candidate_files()
    matches = load_history_matches()
    return {
        "status": "OK" if matches else "NO_DATA",
        "match_count": len(matches),
        "file_count": len(files),
        "search_dirs": [str(p) for p in HISTORY_SEARCH_DIRS],
        "sample_files": [str(p) for p in files[:10]],
    }
