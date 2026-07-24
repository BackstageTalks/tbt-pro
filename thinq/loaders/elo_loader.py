"""
THINQ / ELO Loader

Role in project:
- ELO is a THINQ intelligence layer.
- ELO does not create the final match probability.
- CORQ remains the CORE output model.

Primary source:
- Tennis Abstract Elo and yElo report pages.
- Automatic HTML fetch and parse, no manual CSV upload.

Refresh policy:
- Recommended automatic GitHub workflow refresh: Monday night.
- Manual workflow_dispatch is supported as a safe refresh button.
- If refresh fails, loader keeps using the last local cache and returns stale flags.

Sources:
- ATP Elo:  https://tennisabstract.com/reports/atp_elo_ratings.html
- ATP yElo: https://tennisabstract.com/reports/atp_season_yelo_ratings.html
- WTA Elo:  https://tennisabstract.com/reports/wta_elo_ratings.html
- WTA yElo: https://tennisabstract.com/reports/wta_season_yelo_ratings.html

Recommended location:
- thinq/loaders/elo_loader.py

Main cache:
- thinq/data/elo/elo_cache.json

Last refresh metadata:
- thinq/data/elo/elo_last_refresh.json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen


ATP_ELO_URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"
ATP_YELO_URL = "https://tennisabstract.com/reports/atp_season_yelo_ratings.html"
WTA_ELO_URL = "https://tennisabstract.com/reports/wta_elo_ratings.html"
WTA_YELO_URL = "https://tennisabstract.com/reports/wta_season_yelo_ratings.html"

DEFAULT_CACHE_FILE = "thinq/data/elo/elo_cache.json"
DEFAULT_REFRESH_FILE = "thinq/data/elo/elo_last_refresh.json"

CACHE_STALE_DAYS = 10


# -----------------------------------------------------------------------------
# Parsing helpers
# -----------------------------------------------------------------------------


class TableHTMLParser(HTMLParser):
    """Small dependency-free table parser for Tennis Abstract report pages."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[List[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: List[List[str]] = []
        self._current_row: List[str] = []
        self._current_cell: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in ["td", "th"]:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._in_cell and tag in ["td", "th"]:
            cell = clean_text("".join(self._current_cell))
            self._current_row.append(cell)
            self._in_cell = False
        elif self._in_row and tag == "tr":
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._in_row = False
        elif self._in_table and tag == "table":
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(name: Any) -> str:
    text = clean_text(name).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_header(name: Any) -> str:
    text = clean_text(name).lower()
    text = text.replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def parse_float(value: Any) -> Optional[float]:
    text = clean_text(value)
    if not text or text in ["-", "--", "nan"]:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def parse_int(value: Any) -> Optional[int]:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, timeout: int = 40) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 THINQ-ELO-Loader/1.0 (+https://github.com/BackstageTalks/tennis-backstage-talks)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_last_update(text: str) -> Optional[str]:
    cleaned = clean_text(re.sub(r"<[^>]+>", " ", text))
    match = re.search(r"Last update:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", cleaned, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_report_table(text: str, required_headers: List[str]) -> List[List[str]]:
    parser = TableHTMLParser()
    parser.feed(text)
    normalized_required = {normalize_header(h) for h in required_headers}

    for table in parser.tables:
        for row in table[:5]:
            normalized_row = {normalize_header(cell) for cell in row}
            if normalized_required.issubset(normalized_row):
                return table

    # Fallback: first table with Player column.
    for table in parser.tables:
        for row in table[:5]:
            if "player" in {normalize_header(cell) for cell in row}:
                return table

    return []


def rows_to_dicts(table: List[List[str]], required_header: str = "Player") -> List[Dict[str, str]]:
    if not table:
        return []

    header_idx = None
    for idx, row in enumerate(table[:10]):
        normalized = [normalize_header(cell) for cell in row]
        if normalize_header(required_header) in normalized:
            header_idx = idx
            break

    if header_idx is None:
        return []

    headers = [normalize_header(cell) for cell in table[header_idx]]
    output = []
    for row in table[header_idx + 1:]:
        if len(row) < 2:
            continue
        item: Dict[str, str] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            item[header] = row[index] if index < len(row) else ""
        if item.get("player"):
            output.append(item)
    return output


# -----------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------


@dataclass
class EloPlayerData:
    player: str
    canonical_name: str
    normalized_name: str
    tour: Optional[str] = None

    elo_rank: Optional[int] = None
    elo: Optional[float] = None
    hard_elo_rank: Optional[int] = None
    hard_elo: Optional[float] = None
    clay_elo_rank: Optional[int] = None
    clay_elo: Optional[float] = None
    grass_elo_rank: Optional[int] = None
    grass_elo: Optional[float] = None
    indoor_elo: Optional[float] = None

    peak_elo: Optional[float] = None
    peak_month: Optional[str] = None
    official_rank: Optional[int] = None
    log_diff: Optional[float] = None

    season_yelo_rank: Optional[int] = None
    season_yelo: Optional[float] = None
    season_wins: Optional[int] = None
    season_losses: Optional[int] = None
    season_win_pct: Optional[float] = None

    source: str = "tennisabstract"
    last_refresh: Optional[str] = None
    ta_last_update_elo: Optional[str] = None
    ta_last_update_yelo: Optional[str] = None
    missing: bool = False
    cache_used: bool = True
    cache_stale: bool = False
    flags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Loader
# -----------------------------------------------------------------------------


class EloLoader:
    """
    Automatic Tennis Abstract Elo/yElo loader for THINQ.

    Public methods:
    - refresh_all()
    - load_player(player_name, tour=None)
    - load_cache()
    """

    def __init__(
        self,
        cache_file: Optional[str] = None,
        refresh_file: Optional[str] = None,
        auto_refresh_if_missing: bool = False,
    ) -> None:
        self.cache_file = Path(cache_file or DEFAULT_CACHE_FILE)
        self.refresh_file = Path(refresh_file or DEFAULT_REFRESH_FILE)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.refresh_file.parent.mkdir(parents=True, exist_ok=True)
        self.auto_refresh_if_missing = auto_refresh_if_missing
        self._cache: Optional[Dict[str, Any]] = None

    def load_player(self, player_name: str, tour: Optional[str] = None) -> Dict[str, Any]:
        cache = self.load_cache()
        normalized = normalize_name(player_name)
        tour_normalized = str(tour).lower().strip() if tour else None

        player = None
        if tour_normalized in ["atp", "wta"]:
            player = cache.get("players_by_tour", {}).get(tour_normalized, {}).get(normalized)
        if not player:
            player = cache.get("players", {}).get(normalized)

        if player:
            result = dict(player)
            result["cache_used"] = True
            result["cache_stale"] = self.cache_is_stale(cache)
            flags = list(result.get("flags") or [])
            if result["cache_stale"] and "ELO_CACHE_STALE" not in flags:
                flags.append("ELO_CACHE_STALE")
            result["flags"] = flags
            return result

        return self._missing_player(player_name, tour=tour_normalized, cache=cache)

    def load_cache(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache

        if not self.cache_file.exists() and self.auto_refresh_if_missing:
            self.refresh_all()

        if not self.cache_file.exists():
            self._cache = self.empty_cache(error="ELO cache does not exist")
            return self._cache

        try:
            self._cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if not isinstance(self._cache, dict):
                self._cache = self.empty_cache(error="ELO cache is not a JSON object")
        except Exception as exc:
            self._cache = self.empty_cache(error=f"ELO cache read error: {exc}")
        return self._cache

    def refresh_all(self) -> Dict[str, Any]:
        generated_at = utc_now_iso()
        sources = {
            "atp_elo": self._fetch_and_parse_elo(ATP_ELO_URL, tour="atp"),
            "atp_yelo": self._fetch_and_parse_yelo(ATP_YELO_URL, tour="atp"),
            "wta_elo": self._fetch_and_parse_elo(WTA_ELO_URL, tour="wta"),
            "wta_yelo": self._fetch_and_parse_yelo(WTA_YELO_URL, tour="wta"),
        }

        players_by_tour: Dict[str, Dict[str, Any]] = {"atp": {}, "wta": {}}

        for source_key in ["atp_elo", "wta_elo"]:
            source = sources[source_key]
            for normalized, player in source.get("players", {}).items():
                tour = player.get("tour")
                players_by_tour.setdefault(tour, {})[normalized] = player

        for source_key in ["atp_yelo", "wta_yelo"]:
            source = sources[source_key]
            tour = source.get("tour")
            for normalized, yelo in source.get("players", {}).items():
                base = players_by_tour.setdefault(tour, {}).get(normalized)
                if not base:
                    base = {
                        "player": yelo.get("player"),
                        "canonical_name": yelo.get("canonical_name"),
                        "normalized_name": normalized,
                        "tour": tour,
                        "source": "tennisabstract",
                        "flags": [],
                    }
                    players_by_tour[tour][normalized] = base
                base.update({
                    "season_yelo_rank": yelo.get("season_yelo_rank"),
                    "season_yelo": yelo.get("season_yelo"),
                    "season_wins": yelo.get("season_wins"),
                    "season_losses": yelo.get("season_losses"),
                    "season_win_pct": yelo.get("season_win_pct"),
                    "ta_last_update_yelo": source.get("last_update"),
                })

        players: Dict[str, Any] = {}
        for tour, tour_players in players_by_tour.items():
            for normalized, data in tour_players.items():
                data["last_refresh"] = generated_at
                data["cache_used"] = True
                data["missing"] = False
                data["cache_stale"] = False
                data.setdefault("flags", [])
                # Global lookup prefers exact normalized name. If same normalized exists in both tours,
                # keep the first but tour-specific lookup remains authoritative.
                players.setdefault(normalized, data)

        cache = {
            "generated_at": generated_at,
            "source": "tennisabstract",
            "refresh_policy": "weekly_monday_night_plus_manual_workflow_dispatch",
            "sources": {
                key: {
                    "url": value.get("url"),
                    "tour": value.get("tour"),
                    "last_update": value.get("last_update"),
                    "row_count": value.get("row_count"),
                    "error": value.get("error"),
                }
                for key, value in sources.items()
            },
            "players": players,
            "players_by_tour": players_by_tour,
        }

        self.cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        self.refresh_file.write_text(json.dumps({
            "generated_at": generated_at,
            "status": "ok",
            "cache_file": str(self.cache_file),
            "player_count": len(players),
            "sources": cache["sources"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache = cache
        return cache

    def _fetch_and_parse_elo(self, url: str, tour: str) -> Dict[str, Any]:
        result = {"url": url, "tour": tour, "last_update": None, "row_count": 0, "players": {}, "error": None}
        try:
            text = fetch_text(url)
            result["last_update"] = extract_last_update(text)
            table = extract_report_table(text, required_headers=["Player", "Elo"])
            rows = rows_to_dicts(table)
            for row in rows:
                player = clean_text(row.get("player"))
                if not player:
                    continue
                normalized = normalize_name(player)
                official_rank_key = "atp_rank" if tour == "atp" else "wta_rank"
                data = EloPlayerData(
                    player=player,
                    canonical_name=player,
                    normalized_name=normalized,
                    tour=tour,
                    elo_rank=parse_int(row.get("elo_rank") or row.get("rank")),
                    elo=parse_float(row.get("elo")),
                    hard_elo_rank=parse_int(row.get("helo_rank")),
                    hard_elo=parse_float(row.get("helo")),
                    clay_elo_rank=parse_int(row.get("celo_rank")),
                    clay_elo=parse_float(row.get("celo")),
                    grass_elo_rank=parse_int(row.get("gelo_rank")),
                    grass_elo=parse_float(row.get("gelo")),
                    indoor_elo=None,
                    peak_elo=parse_float(row.get("peak_elo")),
                    peak_month=clean_text(row.get("peak_month")) or None,
                    official_rank=parse_int(row.get(official_rank_key)),
                    log_diff=parse_float(row.get("log_diff")),
                    source="tennisabstract",
                    ta_last_update_elo=result["last_update"],
                    flags=[],
                ).to_dict()
                result["players"][normalized] = data
            result["row_count"] = len(result["players"])
        except Exception as exc:
            result["error"] = str(exc)
        return result

    def _fetch_and_parse_yelo(self, url: str, tour: str) -> Dict[str, Any]:
        result = {"url": url, "tour": tour, "last_update": None, "row_count": 0, "players": {}, "error": None}
        try:
            text = fetch_text(url)
            result["last_update"] = extract_last_update(text)
            table = extract_report_table(text, required_headers=["Player", "yElo"])
            rows = rows_to_dicts(table)
            for row in rows:
                player = clean_text(row.get("player"))
                if not player:
                    continue
                normalized = normalize_name(player)
                wins = parse_int(row.get("wins"))
                losses = parse_int(row.get("losses"))
                total = (wins or 0) + (losses or 0)
                win_pct = round((wins or 0) / total, 4) if total else None
                result["players"][normalized] = {
                    "player": player,
                    "canonical_name": player,
                    "normalized_name": normalized,
                    "tour": tour,
                    "season_yelo_rank": parse_int(row.get("rank")),
                    "season_yelo": parse_float(row.get("yelo")),
                    "season_wins": wins,
                    "season_losses": losses,
                    "season_win_pct": win_pct,
                }
            result["row_count"] = len(result["players"])
        except Exception as exc:
            result["error"] = str(exc)
        return result

    @staticmethod
    def empty_cache(error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "generated_at": None,
            "source": "tennisabstract",
            "error": error,
            "sources": {},
            "players": {},
            "players_by_tour": {"atp": {}, "wta": {}},
        }

    @staticmethod
    def cache_is_stale(cache: Dict[str, Any]) -> bool:
        generated_at = cache.get("generated_at")
        if not generated_at:
            return True
        try:
            dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
            return age_seconds > CACHE_STALE_DAYS * 86400
        except Exception:
            return True

    def _missing_player(self, player_name: str, tour: Optional[str], cache: Dict[str, Any]) -> Dict[str, Any]:
        flags = ["MISSING_ELO"]
        if self.cache_is_stale(cache):
            flags.append("ELO_CACHE_STALE")
        return EloPlayerData(
            player=player_name,
            canonical_name=player_name,
            normalized_name=normalize_name(player_name),
            tour=tour,
            source="tennisabstract",
            last_refresh=cache.get("generated_at"),
            missing=True,
            cache_used=True,
            cache_stale=self.cache_is_stale(cache),
            flags=flags,
        ).to_dict()


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh or read THINQ Tennis Abstract ELO cache")
    parser.add_argument("--refresh", action="store_true", help="Fetch Tennis Abstract Elo/yElo pages and rebuild cache")
    parser.add_argument("--player", default=None, help="Player name to print from cache")
    parser.add_argument("--tour", default=None, choices=["atp", "wta"], help="Optional tour for lookup")
    parser.add_argument("--cache-file", default=DEFAULT_CACHE_FILE)
    parser.add_argument("--refresh-file", default=DEFAULT_REFRESH_FILE)
    args = parser.parse_args()

    loader = EloLoader(cache_file=args.cache_file, refresh_file=args.refresh_file)

    if args.refresh:
        cache = loader.refresh_all()
        print(json.dumps({
            "status": "ok",
            "generated_at": cache.get("generated_at"),
            "player_count": len(cache.get("players", {})),
            "sources": cache.get("sources", {}),
        }, ensure_ascii=False, indent=2))
        return

    if args.player:
        print(json.dumps(loader.load_player(args.player, tour=args.tour), ensure_ascii=False, indent=2))
        return

    cache = loader.load_cache()
    print(json.dumps({
        "generated_at": cache.get("generated_at"),
        "player_count": len(cache.get("players", {})),
        "cache_stale": loader.cache_is_stale(cache),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
