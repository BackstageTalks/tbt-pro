from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

HISTORY_SEARCH_DIRS = [
    Path("data/history"),
    Path("thinq/data/history"),
    Path("data/sackmann"),
    Path("thinq/data/sackmann"),
    Path("data/results_history"),
    Path("outputs/results"),
]

HISTORY_FILE_PATTERNS = (
    "*.csv",
    "*.json",
    "*.jsonl",
)

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


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_surface(value: Any) -> str:
    raw = str(value or "").strip()
    key = raw.lower()
    if key in _SURFACE_MAP:
        return _SURFACE_MAP[key]
    for marker, normalized in _SURFACE_MAP.items():
        if marker in key:
            return normalized
    return raw.title() if raw else "Unknown"


def _parse_date(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Sackmann tourney_date format is YYYYMMDD.
    if re.fullmatch(r"\d{8}", text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    # Already ISO-ish.
    if len(text) >= 10 and text[4:5] == "-":
        return text[:10]
    return text


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


@dataclass
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
        if not root.exists():
            continue
        for pattern in HISTORY_FILE_PATTERNS:
            files.extend(root.rglob(pattern))
    return sorted(set(files))


def _match_from_sackmann_row(row: Dict[str, Any], source: Path) -> Optional[HistoryMatch]:
    winner = row.get("winner_name") or row.get("winner") or row.get("winnerName")
    loser = row.get("loser_name") or row.get("loser") or row.get("loserName")
    if not winner or not loser:
        return None
    return HistoryMatch(
        date=_parse_date(row.get("tourney_date") or row.get("date") or row.get("match_date") or row.get("startDate")),
        winner=str(winner),
        loser=str(loser),
        surface=normalize_surface(row.get("surface") or row.get("surfaceType") or row.get("court")),
        level=str(row.get("tourney_level") or row.get("level") or row.get("category") or ""),
        tournament=str(row.get("tourney_name") or row.get("tournament") or row.get("event") or ""),
        winner_rank=_to_int(row.get("winner_rank") or row.get("winnerRank")),
        loser_rank=_to_int(row.get("loser_rank") or row.get("loserRank")),
        source_file=str(source),
    )


def _matches_from_json_payload(payload: Any, source: Path) -> List[HistoryMatch]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("matches", "results", "items", "data", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                records = [x for x in value if isinstance(x, dict)]
                break
        if not records and "winner" in payload and "loser" in payload:
            records = [payload]
    out: List[HistoryMatch] = []
    for row in records:
        m = _match_from_sackmann_row(row, source)
        if m:
            out.append(m)
    return out


@lru_cache(maxsize=1)
def load_history_matches() -> Tuple[HistoryMatch, ...]:
    out: List[HistoryMatch] = []
    for path in _candidate_files():
        try:
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        m = _match_from_sackmann_row(row, path)
                        if m and m.date:
                            out.append(m)
            elif path.suffix.lower() == ".jsonl":
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        m = _match_from_sackmann_row(row, path)
                        if m and m.date:
                            out.append(m)
            elif path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                out.extend(m for m in _matches_from_json_payload(payload, path) if m.date)
        except Exception:
            # History data should never break production runtime.
            continue
    # newest first
    out.sort(key=lambda m: m.date or "", reverse=True)
    return tuple(out)


def get_player_matches(player: str, limit: Optional[int] = None) -> List[HistoryMatch]:
    key = normalize_name(player)
    matches = [m for m in load_history_matches() if m.involves(key)]
    return matches[:limit] if limit else matches


def history_data_status() -> Dict[str, Any]:
    matches = load_history_matches()
    files = _candidate_files()
    return {
        "status": "OK" if matches else "NO_DATA",
        "match_count": len(matches),
        "file_count": len(files),
        "search_dirs": [str(p) for p in HISTORY_SEARCH_DIRS],
        "sample_files": [str(p) for p in files[:8]],
    }
