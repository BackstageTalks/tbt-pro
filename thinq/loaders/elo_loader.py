"""THINQ ELO loader.

Broad, audit-friendly ELO layer for the clean runtime.

Design goals:
- no hard dependency on one exact CSV filename
- scan common project data folders
- support JSON and CSV records with common Tennis Abstract style columns
- never crash the runtime if ELO is unavailable
- return explicit status/flags for ALL audit
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SEARCH_DIRS = [
    Path("thinq/data"),
    Path("data/thinq"),
    Path("data/elo"),
    Path("data"),
]

ELO_FILE_HINTS = ("elo", "tennisabstract", "ta")

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


def compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
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


def surface_elo_key(surface: Optional[str]) -> str:
    text = str(surface or "").strip().lower()
    if "clay" in text:
        return "clay_elo"
    if "grass" in text:
        return "grass_elo"
    if "carpet" in text:
        # Project rule: use hard ELO fallback for Carpet until separate carpet ELO exists.
        return "hard_elo"
    if "hard" in text or "indoor" in text:
        return "hard_elo"
    return "elo"


def discover_elo_files() -> List[Path]:
    files: List[Path] = []
    for folder in SEARCH_DIRS:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            name = path.name.lower()
            if suffix not in {".csv", ".json"}:
                continue
            if any(hint in name for hint in ELO_FILE_HINTS):
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
        for key in ("players", "data", "items", "elo"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        # Mapping name -> values
        rows = []
        for name, value in payload.items():
            if isinstance(value, dict):
                row = {"player": name, **value}
                rows.append(row)
        return rows
    return []


def row_player_name(row: Dict[str, Any]) -> Optional[str]:
    value = first_present(row, ("player", "name", "player_name", "Player", "Name", "full_name", "fullname"))
    if value:
        return str(value).strip()
    first = first_present(row, ("first_name", "firstname"))
    last = first_present(row, ("last_name", "lastname", "surname"))
    if first and last:
        return f"{first} {last}".strip()
    return None


def row_to_elo(row: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    name = row_player_name(row)
    if not name:
        return None
    output = {
        "player": name,
        "name_key": normalize_name(name),
        "compact_key": compact_name(name),
        "source": source,
        "elo": as_float(first_present(row, ("elo", "overall_elo", "Elo", "overall", "all_elo"))),
        "hard_elo": as_float(first_present(row, ("hard_elo", "hElo", "hard", "HardElo", "hardcourt_elo"))),
        "clay_elo": as_float(first_present(row, ("clay_elo", "cElo", "clay", "ClayElo"))),
        "grass_elo": as_float(first_present(row, ("grass_elo", "gElo", "grass", "GrassElo"))),
        "indoor_elo": as_float(first_present(row, ("indoor_elo", "iElo", "indoor", "IndoorElo"))),
        "yelo": as_float(first_present(row, ("yelo", "yElo", "overall_yelo"))),
        "hard_yelo": as_float(first_present(row, ("hard_yelo", "hardYelo", "hYelo"))),
        "clay_yelo": as_float(first_present(row, ("clay_yelo", "clayYelo", "cYelo"))),
        "grass_yelo": as_float(first_present(row, ("grass_yelo", "grassYelo", "gYelo"))),
    }
    return output


@lru_cache(maxsize=1)
def load_elo_index() -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for path in discover_elo_files():
        rows = load_csv(path) if path.suffix.lower() == ".csv" else load_json(path)
        for row in rows:
            parsed = row_to_elo(row, str(path))
            if not parsed:
                continue
            for key in {parsed["name_key"], parsed["compact_key"]}:
                if key and key not in index:
                    index[key] = parsed
    return index


def find_player(name: Any) -> Optional[Dict[str, Any]]:
    index = load_elo_index()
    norm = normalize_name(name)
    compact = compact_name(name)
    if norm in index:
        return index[norm]
    if compact in index:
        return index[compact]
    # surname/contains fallback kept broad for runtime building
    parts = norm.split()
    surname = parts[-1] if parts else ""
    if surname:
        candidates = [row for key, row in index.items() if key.endswith(surname) or surname in key.split()]
        if len(candidates) == 1:
            return candidates[0]
    return None


def selected_elo_value(player: Dict[str, Any], surface: Optional[str]) -> Tuple[Optional[float], str, List[str]]:
    flags: List[str] = []
    key = surface_elo_key(surface)
    value = as_float(player.get(key))
    if value is not None:
        return value, key, flags
    if key == "hard_elo" and str(surface or "").lower().find("carpet") >= 0:
        flags.append("CARPET_AS_HARD_FALLBACK")
    value = as_float(player.get("elo"))
    if value is not None:
        flags.append("SURFACE_ELO_FALLBACK_OVERALL")
        return value, "elo", flags
    return None, key, flags


def build_elo_context(pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    pick_row = find_player(pick)
    opponent_row = find_player(opponent)
    flags: List[str] = []
    if not pick_row or not opponent_row:
        if not pick_row:
            flags.append("MISSING_ELO_PICK")
        if not opponent_row:
            flags.append("MISSING_ELO_OPPONENT")
        return {
            "status": "NO_DATA",
            "selected_elo_type": surface_elo_key(surface),
            "pick_elo": None,
            "opponent_elo": None,
            "pick_yelo": None,
            "opponent_yelo": None,
            "elo_diff": None,
            "elo_edge": 0.0,
            "source": None,
            "flags": flags + ["MISSING_ELO"],
        }

    pick_elo, selected_key, pick_flags = selected_elo_value(pick_row, surface)
    opponent_elo, _, opponent_flags = selected_elo_value(opponent_row, surface)
    flags.extend(pick_flags)
    flags.extend(opponent_flags)
    if pick_elo is None or opponent_elo is None:
        return {
            "status": "NO_DATA",
            "selected_elo_type": selected_key,
            "pick_elo": pick_elo,
            "opponent_elo": opponent_elo,
            "pick_yelo": pick_row.get("yelo"),
            "opponent_yelo": opponent_row.get("yelo"),
            "elo_diff": None,
            "elo_edge": 0.0,
            "source": pick_row.get("source") or opponent_row.get("source"),
            "flags": flags + ["MISSING_ELO"],
        }

    diff = round(pick_elo - opponent_elo, 1)
    # Broad cap for now. Final calibration later.
    edge = max(min(diff / 1200.0, 0.09), -0.09)
    return {
        "status": "OK",
        "selected_elo_type": selected_key,
        "pick_elo": round(pick_elo, 1),
        "opponent_elo": round(opponent_elo, 1),
        "pick_yelo": pick_row.get("yelo"),
        "opponent_yelo": opponent_row.get("yelo"),
        "elo_diff": diff,
        "elo_edge": round(edge, 4),
        "source": pick_row.get("source") or opponent_row.get("source"),
        "flags": sorted(set(flags)),
    }
