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
]
HISTORY_FILE_PATTERNS = ("*.csv", "*.json", "*.jsonl")
_SURFACE_MAP = {"hard":"Hard","outdoor hard":"Hard","indoor hard":"Hard","clay":"Clay","red clay":"Clay","green clay":"Clay","grass":"Grass","carpet":"Carpet","carpet indoor":"Carpet"}


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
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
    for n in names:
        if n in row and row.get(n) not in (None, ""):
            return row.get(n)
        ck = _clean_key(n)
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
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4:5] == "-":
        return text[:10]
    return text


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
        if root.exists():
            for pattern in HISTORY_FILE_PATTERNS:
                files.extend(root.rglob(pattern))
    return sorted(set(files))


def _match_from_row(raw_row: Dict[str, Any], source: Path) -> Optional[HistoryMatch]:
    row = _norm_row(raw_row)
    winner = _first(row, ["winner_name","winner","winnerName","match_winner","matchWinner","player_won","winner_player","winnerplayer"])
    loser = _first(row, ["loser_name","loser","loserName","match_loser","matchLoser","loser_player","loserplayer"])

    # Generic player1/player2 + winner variant.
    p1 = _first(row, ["player1","player_1","home","home_player","homeTeam","home_name","p1","Player 1"])
    p2 = _first(row, ["player2","player_2","away","away_player","awayTeam","away_name","p2","Player 2"])
    if (not winner or not loser) and p1 and p2 and winner:
        wkey = normalize_name(winner)
        p1key = normalize_name(p1)
        p2key = normalize_name(p2)
        if wkey == p1key:
            loser = p2
        elif wkey == p2key:
            loser = p1
    if not winner or not loser:
        return None

    return HistoryMatch(
        date=_parse_date(_first(row, ["tourney_date","date","match_date","startDate","start_time","time","Date"])),
        winner=str(winner),
        loser=str(loser),
        surface=normalize_surface(_first(row, ["surface","surfaceType","court","court_surface","Surface"])),
        level=str(_first(row, ["tourney_level","level","category","tour","competition","Level"]) or ""),
        tournament=str(_first(row, ["tourney_name","tournament","event","competition_name","Tournament"]) or ""),
        winner_rank=_to_int(_first(row, ["winner_rank","winnerRank","winner_ranking","wrank"])),
        loser_rank=_to_int(_first(row, ["loser_rank","loserRank","loser_ranking","lrank"])),
        source_file=str(source),
    )


def _matches_from_json_payload(payload: Any, source: Path) -> List[HistoryMatch]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("matches","results","items","data","events","rows"):
            value = payload.get(key)
            if isinstance(value, list):
                records = [x for x in value if isinstance(x, dict)]
                break
        if not records:
            records = [payload]
    out: List[HistoryMatch] = []
    for r in records:
        m = _match_from_row(r, source)
        if m and m.date:
            out.append(m)
    return out


@lru_cache(maxsize=1)
def load_history_matches() -> Tuple[HistoryMatch, ...]:
    out: List[HistoryMatch] = []
    for path in _candidate_files():
        if path.name == "bootstrap_manifest.json":
            continue
        try:
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        m = _match_from_row(row, path)
                        if m and m.date:
                            out.append(m)
            elif path.suffix.lower() == ".jsonl":
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line=line.strip()
                        if line:
                            m = _match_from_row(json.loads(line), path)
                            if m and m.date:
                                out.append(m)
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
    return {"status":"OK" if matches else "NO_DATA", "match_count":len(matches), "file_count":len(files), "search_dirs":[str(p) for p in HISTORY_SEARCH_DIRS], "sample_files":[str(p) for p in files[:10]]}
