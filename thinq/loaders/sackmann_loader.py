"""
THINQ / History Sackmann Loader

Role in project:
- Sackmann is a historical data source.
- History is the normalized historical feature layer.
- THINQ is the intelligence layer for CORQ.
- This loader does not produce final match probability.

Output is designed for CORQ/THINQ feature consumption:
- recent form
- surface form
- level form
- sample size
- basic data confidence

Notes:
- Network loading uses Jeff Sackmann GitHub CSV files.
- TennisMyLife fallback is preserved from the original root-level loader.
- Doubles are excluded.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


GITHUB_SOURCES = [
    {
        "label": "ATP_MAIN",
        "url": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{}.csv",
    },
    {
        "label": "ATP_QUAL_CHALL",
        "url": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_qual_chall_{}.csv",
    },
    {
        "label": "WTA_MAIN",
        "url": "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{}.csv",
    },
]

TML_FILES_API = "https://stats.tennismylife.org/api/data-files"


# -----------------------------------------------------------------------------
# Generic source helpers, preserved and cleaned from original sackmann_loader.py
# -----------------------------------------------------------------------------


def get_text(url: str, timeout: int = 30) -> Optional[str]:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.text
    except Exception as exc:
        print("GET TEXT ERROR:", url, exc)
        return None


def fetch_csv_rows(url: str) -> List[Dict[str, Any]]:
    text = get_text(url)
    if not text:
        return []
    if "," not in text:
        return []
    try:
        return list(csv.DictReader(StringIO(text)))
    except Exception as exc:
        print("CSV READ ERROR:", url, exc)
        return []


def normalize_col_name(name: Any) -> str:
    if name is None:
        return ""
    value = str(name).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def normalize_player_name(name: Any) -> str:
    if name is None:
        return ""
    text = str(name).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_column_map(row: Dict[str, Any]) -> Dict[str, str]:
    column_map = {}
    for key in row.keys():
        column_map[normalize_col_name(key)] = key
    return column_map


def get_first(row: Dict[str, Any], candidates: List[str]) -> Optional[Any]:
    column_map = build_column_map(row)
    for candidate in candidates:
        normalized = normalize_col_name(candidate)
        original_key = column_map.get(normalized)
        if original_key is not None:
            value = row.get(original_key)
            if value not in [None, ""]:
                return value
    return None


def parse_date(value: Any) -> str:
    if not value:
        return "0"
    text = str(value).strip()

    # Sackmann: 20240701
    if re.match(r"^\d{8}$", text):
        return text

    # ISO: 2024-07-01
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text[:10]).strftime("%Y%m%d")
    except Exception:
        pass

    # Tennis-data style: 01/07/2024
    for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"]:
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y%m%d")
        except Exception:
            continue

    numbers = re.findall(r"\d+", text)
    if len(numbers) >= 3:
        joined = "".join(numbers[:3])
        if len(joined) >= 8:
            return joined[:8]

    return "0"


def date_to_datetime(value: Any) -> Optional[datetime]:
    parsed = parse_date(value)
    if not parsed or parsed == "0":
        return None
    try:
        return datetime.strptime(parsed, "%Y%m%d")
    except Exception:
        return None


def detect_winner_loser(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    # Jeff Sackmann format
    winner = get_first(row, ["winner_name", "winner", "Winner", "match_winner"])
    loser = get_first(row, ["loser_name", "loser", "Loser", "match_loser"])
    if winner and loser:
        return str(winner).strip(), str(loser).strip()

    # Home/Away + winner code formats
    home = get_first(row, [
        "home_player", "home_name", "home", "player_home", "player1",
        "player_1", "home_team",
    ])
    away = get_first(row, [
        "away_player", "away_name", "away", "player_away", "player2",
        "player_2", "away_team",
    ])
    winner_code = get_first(row, [
        "winner_code", "winner_id", "winner", "result", "match_winner_code",
    ])

    if home and away and winner_code is not None:
        code = str(winner_code).strip().lower()
        if code in ["1", "home", "h", "player1", "player_1"]:
            return str(home).strip(), str(away).strip()
        if code in ["2", "away", "a", "player2", "player_2"]:
            return str(away).strip(), str(home).strip()

    return None, None


def get_surface(row: Dict[str, Any]) -> str:
    return str(get_first(row, ["surface", "Surface", "court", "Court"]) or "Hard").strip()


def get_tournament(row: Dict[str, Any]) -> str:
    return str(get_first(row, ["tourney_name", "tournament", "Tournament", "event", "Event"]) or "").strip()


def get_level(row: Dict[str, Any]) -> str:
    return str(get_first(row, ["tourney_level", "level", "Level", "category", "Category"]) or "").strip()


def get_date(row: Dict[str, Any]) -> str:
    return parse_date(get_first(row, ["tourney_date", "date", "Date", "match_date", "start_date"]))


def parse_rows(rows: List[Dict[str, Any]], source_label: str) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []

    for row in rows:
        try:
            winner, loser = detect_winner_loser(row)
            if not winner or not loser:
                continue

            # Exclude doubles.
            if "/" in winner or "/" in loser:
                continue

            parsed.append({
                "player1": winner,
                "player2": loser,
                "winner": winner,
                "loser": loser,
                "surface": get_surface(row),
                "date": get_date(row),
                "tournament": get_tournament(row),
                "level": get_level(row),
                "source": source_label,
            })
        except Exception:
            continue

    return parsed


def load_github_source_year(source: Dict[str, str], year: int) -> List[Dict[str, Any]]:
    url = source["url"].format(year)
    label = source["label"]
    rows = fetch_csv_rows(url)
    if not rows:
        print(label, year, "rows: 0")
        return []
    parsed = parse_rows(rows, label)
    print(label, year, "rows:", len(rows), "parsed:", len(parsed))
    return parsed


def fetch_tml_file_list() -> List[Dict[str, Any]]:
    try:
        response = requests.get(TML_FILES_API, timeout=30)
        if response.status_code != 200:
            print("TML API ERROR:", response.status_code)
            return []
        data = response.json()
        files = data.get("files", [])
        if not isinstance(files, list):
            return []
        return files
    except Exception as exc:
        print("TML API FETCH ERROR:", exc)
        return []


def tml_file_matches_year(file_obj: Dict[str, Any], year: int) -> bool:
    name = str(file_obj.get("name", "")).lower()
    url = str(file_obj.get("url", "")).lower()

    if not name.endswith(".csv") and not url.endswith(".csv"):
        return False
    if str(year) not in name and str(year) not in url:
        return False

    banned = ["rank", "ranking", "player", "database", "ongoing_tourney"]
    for bad in banned:
        if bad in name:
            return False

    keywords = [str(year), "challenger", "qual", "atp", "wta"]
    return any(keyword in name for keyword in keywords)


def load_tml_years(start_year: int, end_year: int) -> List[Dict[str, Any]]:
    file_list = fetch_tml_file_list()
    if not file_list:
        print("TML FILE LIST EMPTY")
        return []

    all_matches: List[Dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        year_files = [f for f in file_list if tml_file_matches_year(f, year)]
        print("TML YEAR", year, "FILES:", len(year_files))

        for file_obj in year_files:
            name = file_obj.get("name", "")
            url = file_obj.get("url")
            if not url:
                continue

            rows = fetch_csv_rows(url)
            if not rows:
                print("TML", year, name, "rows: 0")
                continue

            label = f"TML_{name}"
            parsed = parse_rows(rows, label)
            print("TML", year, name, "rows:", len(rows), "parsed:", len(parsed))
            all_matches.extend(parsed)

    return all_matches


def load_all_matches(start_year: int = 2018, end_year: int = 2030) -> List[Dict[str, Any]]:
    all_matches: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}

    print("LOADING GITHUB / SACKMANN SOURCES...")
    for year in range(start_year, end_year + 1):
        print("LOADING YEAR:", year)
        for source in GITHUB_SOURCES:
            matches = load_github_source_year(source, year)
            if not matches:
                continue
            label = source["label"]
            source_counts[label] = source_counts.get(label, 0) + len(matches)
            all_matches.extend(matches)

    if len(all_matches) < 1000:
        print("GITHUB SOURCES TOO SMALL, TRYING TENNISMYLIFE FALLBACK...")
        tml_matches = load_tml_years(start_year, end_year)
        for match in tml_matches:
            label = match.get("source", "TML")
            source_counts[label] = source_counts.get(label, 0) + 1
        all_matches.extend(tml_matches)

    # Deduplicate.
    deduped: Dict[Tuple[Any, Any, Any, Any, Any], Dict[str, Any]] = {}
    for match in all_matches:
        key = (
            match.get("date"),
            match.get("player1"),
            match.get("player2"),
            match.get("winner"),
            match.get("surface"),
        )
        deduped[key] = match

    output = list(deduped.values())
    output.sort(key=lambda x: x.get("date") or "0")

    print("TOTAL MATCHES:", len(output))
    print("SOURCE COUNTS:", source_counts)
    return output


# -----------------------------------------------------------------------------
# THINQ / History feature layer
# -----------------------------------------------------------------------------


@dataclass
class HistoryPlayerData:
    player: str

    last5_win_pct: Optional[float] = None
    last10_win_pct: Optional[float] = None
    last20_win_pct: Optional[float] = None

    surface: Optional[str] = None
    surface_win_pct_52w: Optional[float] = None
    surface_win_pct_career: Optional[float] = None
    surface_momentum: Optional[float] = None

    level: Optional[str] = None
    level_win_pct: Optional[float] = None

    avg_opponent_rating_20: Optional[float] = None
    avg_opponent_rank_20: Optional[float] = None
    top50_win_pct_52w: Optional[float] = None

    sample_size_matches: int = 0
    surface_sample_size_52w: int = 0
    surface_sample_size_career: int = 0
    level_sample_size: int = 0

    data_confidence: Optional[float] = None
    source: str = "sackmann_history"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SackmannLoader:
    """
    History/Sackmann loader for THINQ.

    Public methods expected by thinq/loaders/thinq_loader.py:
    - load_player(player_name, surface=None, level=None)
    - load_match(player1, player2, surface=None, level=None)

    This loader returns normalized feature data only. It does not produce final odds,
    final prediction probability, TOP7 ranking, or model pick.
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        cache_file: Optional[str] = None,
        start_year: int = 2018,
        end_year: Optional[int] = None,
        refresh: bool = False,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path("thinq/data/history")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = Path(cache_file) if cache_file else self.data_dir / "sackmann_matches_cache.json"
        self.start_year = start_year
        self.end_year = end_year or datetime.utcnow().year
        self.refresh = refresh
        self._matches: Optional[List[Dict[str, Any]]] = None

    def load_matches(self) -> List[Dict[str, Any]]:
        if self._matches is not None:
            return self._matches

        if self.cache_file.exists() and not self.refresh:
            try:
                self._matches = json.loads(self.cache_file.read_text(encoding="utf-8"))
                return self._matches
            except Exception as exc:
                print("SACKMANN CACHE READ ERROR:", exc)

        matches = load_all_matches(self.start_year, self.end_year)
        self._matches = matches

        try:
            self.cache_file.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print("SACKMANN CACHE WRITE ERROR:", exc)

        return matches

    def load_player(
        self,
        player_name: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        matches = self.load_matches()
        player_key = normalize_player_name(player_name)
        as_of_dt = date_to_datetime(as_of_date) if as_of_date else None

        player_matches = []
        for match in matches:
            match_dt = date_to_datetime(match.get("date"))
            if as_of_dt and match_dt and match_dt > as_of_dt:
                continue

            p1 = normalize_player_name(match.get("player1"))
            p2 = normalize_player_name(match.get("player2"))
            if player_key not in [p1, p2]:
                continue

            enriched = dict(match)
            enriched["_match_dt"] = match_dt
            enriched["_is_win"] = normalize_player_name(match.get("winner")) == player_key
            enriched["_opponent"] = match.get("player2") if p1 == player_key else match.get("player1")
            player_matches.append(enriched)

        player_matches.sort(key=lambda item: item.get("date") or "0", reverse=True)

        recent_5 = self._win_pct(player_matches[:5])
        recent_10 = self._win_pct(player_matches[:10])
        recent_20 = self._win_pct(player_matches[:20])

        surface_matches_career = self._filter_surface(player_matches, surface)
        surface_matches_52w = self._filter_last_days(surface_matches_career, 365, as_of_dt)

        surface_win_pct_52w = self._win_pct(surface_matches_52w)
        surface_win_pct_career = self._win_pct(surface_matches_career)
        surface_momentum = self._safe_diff(surface_win_pct_52w, surface_win_pct_career)

        level_matches = self._filter_level(player_matches, level)
        level_win_pct = self._win_pct(level_matches)

        data_confidence = self._data_confidence(
            total_matches=len(player_matches),
            surface_matches=len(surface_matches_52w),
            level_matches=len(level_matches),
        )

        data = HistoryPlayerData(
            player=player_name,
            last5_win_pct=recent_5,
            last10_win_pct=recent_10,
            last20_win_pct=recent_20,
            surface=surface,
            surface_win_pct_52w=surface_win_pct_52w,
            surface_win_pct_career=surface_win_pct_career,
            surface_momentum=surface_momentum,
            level=level,
            level_win_pct=level_win_pct,
            avg_opponent_rating_20=None,  # Filled later after ELOQ is connected.
            avg_opponent_rank_20=None,    # Filled later if ranking source is added.
            top50_win_pct_52w=None,       # Filled later if rankings are connected.
            sample_size_matches=len(player_matches),
            surface_sample_size_52w=len(surface_matches_52w),
            surface_sample_size_career=len(surface_matches_career),
            level_sample_size=len(level_matches),
            data_confidence=data_confidence,
        )
        return data.to_dict()

    def load_match(
        self,
        player1: str,
        player2: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        p1 = self.load_player(player1, surface=surface, level=level, as_of_date=as_of_date)
        p2 = self.load_player(player2, surface=surface, level=level, as_of_date=as_of_date)

        return {
            "player1": p1,
            "player2": p2,
            "surface": surface,
            "level": level,
            "History_edges": self._build_basic_edges(p1, p2),
        }

    @staticmethod
    def _win_pct(matches: List[Dict[str, Any]]) -> Optional[float]:
        if not matches:
            return None
        wins = sum(1 for match in matches if match.get("_is_win"))
        return round(wins / len(matches), 4)

    @staticmethod
    def _safe_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return round(a - b, 4)

    @staticmethod
    def _filter_surface(matches: List[Dict[str, Any]], surface: Optional[str]) -> List[Dict[str, Any]]:
        if not surface:
            return matches
        s = str(surface).strip().lower()
        return [m for m in matches if str(m.get("surface", "")).strip().lower() == s]

    @staticmethod
    def _filter_level(matches: List[Dict[str, Any]], level: Optional[str]) -> List[Dict[str, Any]]:
        if not level:
            return matches
        target = str(level).strip().lower()
        return [m for m in matches if str(m.get("level", "")).strip().lower() == target]

    @staticmethod
    def _filter_last_days(
        matches: List[Dict[str, Any]],
        days: int,
        as_of_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        dated = [m for m in matches if m.get("_match_dt")]
        if not dated:
            return []

        anchor = as_of_dt or max(m["_match_dt"] for m in dated if m.get("_match_dt"))
        cutoff = anchor - timedelta(days=days)
        return [m for m in dated if cutoff <= m["_match_dt"] <= anchor]

    @staticmethod
    def _data_confidence(total_matches: int, surface_matches: int, level_matches: int) -> float:
        total_score = min(total_matches / 30, 1.0)
        surface_score = min(surface_matches / 10, 1.0)
        level_score = min(level_matches / 8, 1.0)
        confidence = (0.50 * total_score) + (0.35 * surface_score) + (0.15 * level_score)
        return round(confidence, 4)

    @staticmethod
    def _edge_from_pct_diff(a: Optional[float], b: Optional[float], cap: float = 0.12) -> Optional[float]:
        if a is None or b is None:
            return None
        raw = a - b
        if raw > cap:
            raw = cap
        if raw < -cap:
            raw = -cap
        return round(raw, 4)

    def _build_basic_edges(self, p1: Dict[str, Any], p2: Dict[str, Any]) -> Dict[str, Optional[float]]:
        return {
            "recent_form_edge": self._edge_from_pct_diff(p1.get("last10_win_pct"), p2.get("last10_win_pct")),
            "surface_form_edge": self._edge_from_pct_diff(
                p1.get("surface_win_pct_52w"),
                p2.get("surface_win_pct_52w"),
            ),
            "level_form_edge": self._edge_from_pct_diff(p1.get("level_win_pct"), p2.get("level_win_pct")),
            "History_confidence": round(
                ((p1.get("data_confidence") or 0.0) + (p2.get("data_confidence") or 0.0)) / 2,
                4,
            ),
        }


if __name__ == "__main__":
    loader = SackmannLoader(start_year=2024, end_year=datetime.utcnow().year)
    sample = loader.load_player("Paula Badosa", surface="Clay")
    print(json.dumps(sample, ensure_ascii=False, indent=2))
