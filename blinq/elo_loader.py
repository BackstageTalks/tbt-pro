
"""BlinQ independent ELO loader.

Provides separate overall ELO and surface ELO signals.
All returned edges are oriented from pick -> opponent:
- positive edge = advantage pick
- negative edge = advantage opponent
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SEARCH_DIRS = [Path("blinq/data/elo")]
ELO_FILE_HINTS = ("elo", "rating", "tennisabstract", "ta")
ELO_OUTPUT_PATH = Path("blinq/data/elo/elo_ratings.json")
ATP_ELO_URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"
WTA_ELO_URL = "https://tennisabstract.com/reports/wta_elo_ratings.html"
USER_AGENT = os.getenv(
    "TA_ELO_USER_AGENT",
    "Mozilla/5.0 (compatible; BlinQ-ELO-Cache/1.0; +https://backstagetalks.example)",
)
REQUEST_TIMEOUT = int(os.getenv("TA_ELO_REQUEST_TIMEOUT_SECONDS", "25"))
REQUEST_DELAY_SECONDS = float(os.getenv("TA_ELO_REQUEST_DELAY_SECONDS", "0.35"))

_TRANSLATE = str.maketrans({"ł":"l","Ł":"L","đ":"d","Đ":"D","ð":"d","Ð":"D","þ":"th","Þ":"Th","ß":"ss","ø":"o","Ø":"O","æ":"ae","Æ":"Ae","œ":"oe","Œ":"Oe"})


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
            if not path.is_file() or path.suffix.lower() not in {".csv", ".json"}:
                continue
            if any(hint in path.name.lower() for hint in ELO_FILE_HINTS):
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
        for key in ("players", "data", "items", "elo", "ratings"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                rows: List[Dict[str, Any]] = []
                for name, record in value.items():
                    if not isinstance(record, dict):
                        continue
                    merged = dict(record)
                    if not merged.get("player"):
                        merged["player"] = name
                    if not merged.get("normalized_name"):
                        merged["normalized_name"] = normalize_name(merged.get("player") or name)
                    rows.append(merged)
                return rows
        rows: List[Dict[str, Any]] = []
        for name, value in payload.items():
            if not isinstance(value, dict):
                continue
            merged = dict(value)
            if not merged.get("player"):
                merged["player"] = name
            rows.append(merged)
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
    return {
        "player": name,
        "name_key": normalize_name(name),
        "compact_key": compact_name(name),
        "source": source,
        "elo": as_float(first_present(row, ("elo", "overall_elo", "Elo", "overall", "all_elo", "rating"))),
        "hard_elo": as_float(first_present(row, ("hard_elo", "hElo", "hard", "HardElo", "hardcourt_elo"))),
        "clay_elo": as_float(first_present(row, ("clay_elo", "cElo", "clay", "ClayElo"))),
        "grass_elo": as_float(first_present(row, ("grass_elo", "gElo", "grass", "GrassElo"))),
        "indoor_elo": as_float(first_present(row, ("indoor_elo", "iElo", "indoor", "IndoorElo"))),
        "yelo": as_float(first_present(row, ("yelo", "yElo", "overall_yelo"))),
        "hard_yelo": as_float(first_present(row, ("hard_yelo", "hardYelo", "hYelo"))),
        "clay_yelo": as_float(first_present(row, ("clay_yelo", "clayYelo", "cYelo"))),
        "grass_yelo": as_float(first_present(row, ("grass_yelo", "grassYelo", "gYelo"))),
    }


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
    surname = norm.split()[-1] if norm.split() else ""
    if surname:
        candidates = [row for key, row in index.items() if key.endswith(surname) or surname in key.split()]
        if len(candidates) == 1:
            return candidates[0]
    return None


def edge_from_diff(diff: Optional[float], cap: float) -> float:
    if diff is None:
        return 0.0
    # 1200 ELO points roughly maps to a 100 percentage-point swing in this edge space.
    return round(max(min(diff / 1200.0, cap), -cap), 4)


def value_for_key(row: Dict[str, Any], key: str) -> Optional[float]:
    value = as_float(row.get(key))
    if value is not None:
        return value
    return None


def selected_surface_value(row: Dict[str, Any], surface: Optional[str]) -> Tuple[Optional[float], str, List[str]]:
    flags: List[str] = []
    key = surface_elo_key(surface)
    value = value_for_key(row, key)
    if value is not None:
        return value, key, flags
    if key == "hard_elo" and "carpet" in str(surface or "").lower():
        flags.append("CARPET_AS_HARD_FALLBACK")
    fallback = value_for_key(row, "elo")
    if fallback is not None:
        flags.append("SURFACE_ELO_FALLBACK_OVERALL")
        return fallback, "elo", flags
    return None, key, flags


def build_elo_context(pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
    pick_row = find_player(pick)
    opponent_row = find_player(opponent)
    selected_key = surface_elo_key(surface)
    flags: List[str] = []
    if not pick_row or not opponent_row:
        if not pick_row:
            flags.append("MISSING_ELO_PICK")
        if not opponent_row:
            flags.append("MISSING_ELO_OPPONENT")
        return {
            "status": "NO_DATA",
            "selected_elo_type": selected_key,
            "overall_pick_elo": None,
            "overall_opponent_elo": None,
            "surface_pick_elo": None,
            "surface_opponent_elo": None,
            "pick_elo": None,
            "opponent_elo": None,
            "overall_elo_diff": None,
            "surface_elo_diff": None,
            "overall_elo_edge": 0.0,
            "surface_elo_edge": 0.0,
            "elo_edge": 0.0,
            "pick_yelo": None,
            "opponent_yelo": None,
            "source": None,
            "flags": flags + ["MISSING_ELO"],
        }

    overall_pick = value_for_key(pick_row, "elo")
    overall_opp = value_for_key(opponent_row, "elo")
    surface_pick, selected_key, pick_flags = selected_surface_value(pick_row, surface)
    surface_opp, _, opp_flags = selected_surface_value(opponent_row, surface)
    flags.extend(pick_flags)
    flags.extend(opp_flags)

    overall_diff = round(overall_pick - overall_opp, 1) if overall_pick is not None and overall_opp is not None else None
    surface_diff = round(surface_pick - surface_opp, 1) if surface_pick is not None and surface_opp is not None else None
    overall_edge = edge_from_diff(overall_diff, 0.07)
    surface_edge = edge_from_diff(surface_diff, 0.08)
    status = "OK" if surface_diff is not None or overall_diff is not None else "NO_DATA"
    if status != "OK":
        flags.append("MISSING_ELO")
    return {
        "status": status,
        "selected_elo_type": selected_key,
        "overall_pick_elo": round(overall_pick, 1) if overall_pick is not None else None,
        "overall_opponent_elo": round(overall_opp, 1) if overall_opp is not None else None,
        "surface_pick_elo": round(surface_pick, 1) if surface_pick is not None else None,
        "surface_opponent_elo": round(surface_opp, 1) if surface_opp is not None else None,
        "pick_elo": round(surface_pick, 1) if surface_pick is not None else None,
        "opponent_elo": round(surface_opp, 1) if surface_opp is not None else None,
        "overall_elo_diff": overall_diff,
        "surface_elo_diff": surface_diff,
        "elo_diff": surface_diff,
        "overall_elo_edge": overall_edge,
        "surface_elo_edge": surface_edge,
        "elo_edge": surface_edge if surface_diff is not None else overall_edge,
        "pick_yelo": pick_row.get("yelo"),
        "opponent_yelo": opponent_row.get("yelo"),
        "source": pick_row.get("source") or opponent_row.get("source"),
        "flags": sorted(set(flags)),
    }



def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def fetch_url(url: str, retries: int = 2) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 + attempt * 0.5)
    raise RuntimeError(f"TA ELO fetch failed url={url} error={last_error}")


def try_read_html_tables(html_text: str) -> List[Any]:
    try:
        import pandas as pd  # type: ignore
        return pd.read_html(StringIO(html_text))
    except Exception:
        return []


def flatten_columns(df: Any) -> Any:
    try:
        df = df.copy()
        columns = []
        for col in df.columns:
            if isinstance(col, tuple):
                parts = [str(x).strip() for x in col if str(x).strip() and not str(x).startswith("Unnamed")]
                columns.append(" ".join(parts).strip())
            else:
                columns.append(str(col).strip())
        df.columns = columns
        return df
    except Exception:
        return df


def clean_column_name(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def table_value(row: Dict[str, Any], aliases: Iterable[str]) -> Any:
    normalized = {clean_column_name(k): v for k, v in row.items()}
    for alias in aliases:
        key = clean_column_name(alias)
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    return None


def parse_elo_tables(html_text: str, tour: str, source_url: str) -> List[Dict[str, Any]]:
    tables = try_read_html_tables(html_text)
    rows_out: List[Dict[str, Any]] = []
    for table in tables:
        table = flatten_columns(table)
        try:
            rows = table.to_dict(orient="records")
        except Exception:
            continue
        for row in rows:
            player = table_value(row, ("Player", "Name"))
            elo = as_float(table_value(row, ("Elo", "Overall Elo", "Rating")))
            if not player or elo is None:
                continue
            name = str(player).replace("\xa0", " ").strip()
            if not name or name.lower() in {"player", "nan"}:
                continue
            record = {
                "player": name,
                "player_name": name,
                "tour": tour,
                "name_key": normalize_name(name),
                "compact_key": compact_name(name),
                "elo": elo,
                "hard_elo": as_float(table_value(row, ("hElo", "Hard Elo", "Hard"))),
                "clay_elo": as_float(table_value(row, ("cElo", "Clay Elo", "Clay"))),
                "grass_elo": as_float(table_value(row, ("gElo", "Grass Elo", "Grass"))),
                "source": source_url,
                "updated_at": now_iso(),
            }
            rows_out.append({k: v for k, v in record.items() if v is not None})
    # Deduplicate by compact key while preserving order.
    dedup: Dict[str, Dict[str, Any]] = {}
    for rec in rows_out:
        key = str(rec.get("compact_key") or compact_name(rec.get("player")))
        if key and key not in dedup:
            dedup[key] = rec
    return list(dedup.values())


def build_ta_elo_cache(output_path: Path = ELO_OUTPUT_PATH) -> Dict[str, Any]:
    sources = [
        ("atp", ATP_ELO_URL),
        ("wta", WTA_ELO_URL),
    ]
    players: Dict[str, Dict[str, Any]] = {}
    stats = {"sources": len(sources), "players": 0, "failed": 0}
    errors: List[str] = []
    for tour, url in sources:
        try:
            html_text = fetch_url(url)
            rows = parse_elo_tables(html_text, tour=tour, source_url=url)
            for rec in rows:
                key = str(rec.get("compact_key") or compact_name(rec.get("player")))
                if key:
                    players[key] = rec
            print(f"[ELO] {tour} rows={len(rows)} url={url}")
            time.sleep(REQUEST_DELAY_SECONDS)
        except Exception as exc:
            stats["failed"] += 1
            errors.append(f"{tour}: {exc}")
            print(f"[ELO] failed {tour}: {exc}")
    stats["players"] = len(players)
    payload = {
        "generated_at": now_iso(),
        "source": "tennis_abstract_elo_ratings",
        "sources": {"atp": ATP_ELO_URL, "wta": WTA_ELO_URL},
        "profile_count": len(players),
        "stats": stats,
        "errors": errors,
        "players": players,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    load_elo_index.cache_clear()
    print(f"[ELO] wrote {output_path} players={len(players)}")
    if not players:
        raise RuntimeError("ELO cache update produced zero players")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect Tennis Abstract ELO cache")
    parser.add_argument("--update", action="store_true", help="Fetch TA ATP/WTA Elo reports and write cache")
    parser.add_argument("--output", default=str(ELO_OUTPUT_PATH), help="Output JSON path")
    args = parser.parse_args()
    if args.update:
        build_ta_elo_cache(Path(args.output))
    else:
        index = load_elo_index()
        print(f"Loaded ELO index players={len(index)}")


if __name__ == "__main__":
    main()
