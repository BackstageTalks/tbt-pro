"""
THINQ Player Resolver

Single source of truth for tennis player-name matching across THINQ, CORQ,
H2H, ELO, Results and render.

Primary sources, in order:
1. thinq/data/players/tennis_name_alias_database.json  - manual canonical aliases
2. thinq/data/players/player_registry.json             - generated API/ELO registry
3. safe normalization fallback

Design rules:
- Never guess between ambiguous players.
- Prefer API player id when present.
- Keep display names clean and readable.
- Normalize accents, punctuation, apostrophes and common mojibake safely.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_SPECIAL_CHARS = {
    "ł": "l",
    "Ł": "L",
    "đ": "d",
    "Đ": "D",
    "ð": "d",
    "Ð": "D",
    "þ": "th",
    "Þ": "Th",
    "ß": "ss",
    "ø": "o",
    "Ø": "O",
    "æ": "ae",
    "Æ": "AE",
    "œ": "oe",
    "Œ": "OE",
    "ı": "i",
    "İ": "I",
}

_MOJIBAKE_REPLACEMENTS = {
    "Ä‡": "ć",
    "Ä": "ć",
    "Ä": "č",
    "Ä": "Đ",
    "Ä‘": "đ",
    "Å¡": "š",
    "Å½": "Ž",
    "Å¾": "ž",
    "Ä…": "ą",
    "Ä™": "ę",
    "Å‚": "ł",
    "Å„": "ń",
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã±": "ñ",
    "Ã§": "ç",
    "Ã¼": "ü",
    "Ã¶": "ö",
    "Ã¤": "ä",
    "Ãë": "ë",
    "Ã¨": "è",
    "Ã¢": "â",
    "Ã£": "ã",
    "Ã¸": "ø",
    "Ãœ": "Ü",
    "Ã–": "Ö",
    "Ã„": "Ä",
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€�": '"',
    "â€“": "-",
    "â€”": "-",
}

_BLANK_VALUES = {None, "", "N/A", "NA", "-", "None", "null"}


@dataclass
class PlayerIdentity:
    input_name: str
    canonical_name: str
    normalized_name: str
    display_name: Optional[str] = None
    compact_key: Optional[str] = None
    player_id: Optional[str] = None
    api_team_id: Optional[Any] = None
    rapidapi_id: Optional[Any] = None
    tour: Optional[str] = None
    country: Optional[str] = None
    rank: Optional[Any] = None
    search_key: Optional[str] = None
    external_player_key: Optional[str] = None
    ta_slug: Optional[str] = None
    sackmann_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    source: str = "player_resolver"
    match_status: str = "fallback"
    ambiguous: bool = False
    candidate_player_ids: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get("display_name") is None:
            payload["display_name"] = payload.get("canonical_name")
        if payload.get("compact_key") is None:
            payload["compact_key"] = PlayerResolver.alias_key(payload.get("canonical_name"))
        return payload


class PlayerResolver:
    def __init__(self, database_file: Optional[str] = None, cache_file: Optional[str] = None, registry_file: Optional[str] = None) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.database_file = self._find_database_file(database_file)
        self.registry_file = Path(registry_file) if registry_file else self.root / "thinq" / "data" / "players" / "player_registry.json"
        self.cache_file = Path(cache_file) if cache_file else self.root / "thinq" / "data" / "players" / "player_resolver_cache.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()
        self.database: Dict[str, Any] = self._load_database()
        self.registry: Dict[str, Any] = self._load_json(self.registry_file)
        self.players_by_id: Dict[str, Dict[str, Any]] = {}
        self.global_resolution: Dict[str, Dict[str, Any]] = {}
        self.scoped_resolution: Dict[str, Dict[str, Any]] = {}
        self._build_indices()

    def resolve(self, player_name: Any, tour: Optional[str] = None, country: Optional[str] = None, player_id: Optional[Any] = None) -> Dict[str, Any]:
        raw = self.clean_player_name(player_name)
        fixed = self.fix_mojibake(raw)
        normalized = self.normalize_name(fixed)
        key = self.alias_key(fixed)
        tour_key = self._normalize_tour(tour)
        pid = self._as_id(player_id)
        cache_key = f"{tour_key or '*'}:{pid or '*'}:{key}"

        cached = self.cache.get(cache_key)
        if cached:
            return cached

        identity = self._resolve_by_id(pid, fixed, tour_key, country)
        if identity is None:
            identity = self._resolve_from_database(fixed, key, tour_key, country)
        if identity is None:
            identity = PlayerIdentity(
                input_name=raw,
                canonical_name=fixed,
                display_name=fixed,
                normalized_name=normalized,
                compact_key=key,
                player_id=str(pid) if pid is not None else None,
                api_team_id=pid,
                tour=tour_key,
                country=country,
                search_key=key,
                ta_slug=self.build_ta_slug(fixed),
                source="fallback_normalizer",
                match_status="fallback",
            ).to_dict()

        self.cache[cache_key] = identity
        self._save_cache()
        return identity

    def canonicalize(self, name: Any, tour: Optional[str] = None) -> str:
        resolved = self.resolve(name, tour=tour)
        return str(resolved.get("canonical_name") or self.clean_player_name(name))

    def get_name_candidates(self, name: Any, tour: Optional[str] = None, include_raw: bool = True) -> List[str]:
        raw = self.clean_player_name(name)
        if not raw:
            return []
        fixed = self.fix_mojibake(raw)
        resolved = self.resolve(fixed, tour=tour)
        candidate_values: List[str] = []
        for field in ("canonical_name", "display_name", "sackmann_name"):
            if resolved.get(field):
                candidate_values.append(str(resolved[field]))
        aliases = resolved.get("aliases")
        if isinstance(aliases, list):
            candidate_values.extend(str(x) for x in aliases if x)
        if include_raw:
            candidate_values.extend([raw, fixed])
        lowered = fixed.lower()
        if lowered.endswith(" jr"):
            candidate_values.append(fixed[:-3].strip())
        elif lowered.endswith(" jr."):
            candidate_values.append(fixed[:-4].strip())
        candidate_values.append(fixed.replace("-", " "))
        candidate_values.append(fixed.replace(".", " "))

        out: List[str] = []
        seen = set()
        for candidate in candidate_values:
            candidate = self.clean_player_name(candidate)
            candidate_key = self.alias_key(candidate)
            if candidate and candidate_key and candidate_key not in seen:
                out.append(candidate)
                seen.add(candidate_key)
        return out

    def find_profile(self, player_name: str, profiles_by_name: Dict[str, Any], tour: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not isinstance(profiles_by_name, dict):
            return None
        lookup: Dict[str, Any] = {}
        for key, value in profiles_by_name.items():
            for indexed in self._profile_index_names(key, value):
                indexed_key = self.alias_key(indexed)
                if indexed_key and indexed_key not in lookup:
                    lookup[indexed_key] = value
        for candidate in self.get_name_candidates(player_name, tour=tour):
            hit = lookup.get(self.alias_key(candidate))
            if hit:
                return hit
        return None

    def _profile_index_names(self, key: Any, value: Any) -> Iterable[str]:
        yield self.clean_player_name(key)
        if isinstance(value, dict):
            for field in ("player_name", "canonical_name", "display_name", "name", "player", "player_key", "ta_slug"):
                val = value.get(field)
                if val:
                    yield self.clean_player_name(val)

    def _resolve_by_id(self, player_id: Optional[int], raw: str, tour: Optional[str], country: Optional[str]) -> Optional[Dict[str, Any]]:
        if player_id is None:
            return None
        player = self.players_by_id.get(str(player_id)) or self.players_by_id.get(f"api:{player_id}") or self.players_by_id.get(f"id:{player_id}")
        if not player:
            return None
        return self._identity_from_player(player, raw, self.alias_key(raw), tour, country, "resolved_by_id")

    def _resolve_from_database(self, raw: str, key: str, tour: Optional[str], country: Optional[str]) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        resolution = None
        if tour:
            resolution = self.scoped_resolution.get(f"{tour}:{key}")
        if resolution is None:
            resolution = self.global_resolution.get(key)
        if not isinstance(resolution, dict):
            return None

        status = str(resolution.get("status") or "resolved")
        player_id = resolution.get("resolved_player_id") or resolution.get("player_id") or resolution.get("api_team_id")
        candidates = resolution.get("candidate_player_ids") or []
        if status == "ambiguous" and not player_id:
            if country:
                country_norm = str(country).upper().strip()
                country_matches = [pid for pid in candidates if str(self.players_by_id.get(str(pid), {}).get("country") or "").upper() == country_norm]
                if len(country_matches) == 1:
                    player_id = country_matches[0]
                    status = "resolved_by_country"
            if not player_id:
                return PlayerIdentity(
                    input_name=raw,
                    canonical_name=raw,
                    display_name=raw,
                    normalized_name=self.normalize_name(raw),
                    compact_key=key,
                    tour=tour,
                    country=country,
                    search_key=key,
                    ta_slug=self.build_ta_slug(raw),
                    source="player_alias_database",
                    match_status="ambiguous",
                    ambiguous=True,
                    candidate_player_ids=list(candidates),
                ).to_dict()
        player = self.players_by_id.get(str(player_id or "")) or self.players_by_id.get(f"api:{player_id}")
        if not player:
            return None
        return self._identity_from_player(player, raw, key, tour, country, status)

    def _identity_from_player(self, player: Dict[str, Any], raw: str, key: str, tour: Optional[str], country: Optional[str], status: str) -> Dict[str, Any]:
        canonical_name = self.clean_player_name(player.get("canonical_name") or player.get("display_name") or player.get("name") or raw)
        canonical_name = self.fix_mojibake(canonical_name)
        api_team_id = self._as_id(player.get("api_team_id") or player.get("rapidapi_id") or player.get("player_id") or player.get("id"))
        player_id = player.get("player_id") or player.get("registry_key") or (f"api:{api_team_id}" if api_team_id is not None else None)
        aliases = self._unique_names([canonical_name, player.get("name"), player.get("display_name"), player.get("sackmann_name")] + list(player.get("aliases") or []))
        return PlayerIdentity(
            input_name=raw,
            canonical_name=canonical_name,
            display_name=canonical_name,
            normalized_name=self.normalize_name(canonical_name),
            compact_key=self.alias_key(canonical_name),
            player_id=str(player_id) if player_id not in _BLANK_VALUES else None,
            api_team_id=api_team_id,
            rapidapi_id=api_team_id,
            tour=str(player.get("tour") or tour or "").upper() or None,
            country=player.get("country") or country,
            rank=player.get("rank") or player.get("api_rank"),
            search_key=player.get("search_key") or key,
            external_player_key=player.get("external_player_key") or player.get("registry_key"),
            ta_slug=player.get("ta_slug") or self.build_ta_slug(canonical_name),
            sackmann_name=player.get("sackmann_name"),
            aliases=aliases,
            source=str(player.get("source") or "player_registry"),
            match_status=status or "resolved",
        ).to_dict()

    def _build_indices(self) -> None:
        self.players_by_id = {}
        self.global_resolution = {}
        self.scoped_resolution = {}

        for player in self._iter_database_players():
            self._index_player(player, source="player_alias_database")
        for player in self._iter_registry_players():
            self._index_player(player, source="player_registry")

    def _index_player(self, player: Dict[str, Any], source: str) -> None:
        if not isinstance(player, dict):
            return
        item = dict(player)
        item.setdefault("source", source)
        api_team_id = self._as_id(item.get("api_team_id") or item.get("rapidapi_id") or item.get("player_id") or item.get("id"))
        registry_key = str(item.get("registry_key") or "")
        player_id = str(item.get("player_id") or registry_key or (f"api:{api_team_id}" if api_team_id is not None else ""))
        if api_team_id is not None:
            item["api_team_id"] = api_team_id
            item["rapidapi_id"] = api_team_id
            self.players_by_id[str(api_team_id)] = item
            self.players_by_id[f"api:{api_team_id}"] = item
            self.players_by_id[f"id:{api_team_id}"] = item
        if player_id:
            self.players_by_id[player_id] = item
        if registry_key:
            self.players_by_id[registry_key] = item

        names = [item.get("canonical_name"), item.get("display_name"), item.get("name"), item.get("sackmann_name")]
        names.extend(item.get("aliases") if isinstance(item.get("aliases"), list) else [])
        names.extend([item.get("normalized_name"), item.get("compact_key"), item.get("elo_name_key"), item.get("elo_compact_key")])
        tour = self._normalize_tour(item.get("tour"))
        resolved_id = player_id or (f"api:{api_team_id}" if api_team_id is not None else None)
        for name in names:
            name_key = self.alias_key(name)
            if not name_key or not resolved_id:
                continue
            resolution = {"status": "resolved", "resolved_player_id": resolved_id, "source": source}
            self.global_resolution.setdefault(name_key, resolution)
            if tour:
                self.scoped_resolution.setdefault(f"{tour}:{name_key}", resolution)

        alias_resolution = self.database.get("alias_resolution") if isinstance(self.database, dict) else None
        if isinstance(alias_resolution, dict):
            for alias, value in alias_resolution.items():
                alias_norm = self.alias_key(alias)
                if alias_norm and isinstance(value, str):
                    self.global_resolution[alias_norm] = {"status": "resolved", "resolved_player_id": value, "source": "alias_resolution"}
                elif alias_norm and isinstance(value, dict):
                    self.global_resolution[alias_norm] = value

    def _iter_database_players(self) -> Iterable[Dict[str, Any]]:
        players = self.database.get("players") if isinstance(self.database, dict) else []
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict):
                    yield player
        elif isinstance(players, dict):
            for key, player in players.items():
                if isinstance(player, dict):
                    item = dict(player)
                    item.setdefault("registry_key", key)
                    if key.startswith("api:") and not item.get("api_team_id"):
                        item["api_team_id"] = key.split(":", 1)[1]
                    yield item

    def _iter_registry_players(self) -> Iterable[Dict[str, Any]]:
        players = self.registry.get("players") if isinstance(self.registry, dict) else []
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict):
                    yield player
        elif isinstance(players, dict):
            for key, player in players.items():
                if isinstance(player, dict):
                    item = dict(player)
                    item.setdefault("registry_key", key)
                    if key.startswith("api:") and not item.get("api_team_id"):
                        item["api_team_id"] = key.split(":", 1)[1]
                    yield item

    def _find_database_file(self, database_file: Optional[str]) -> Optional[Path]:
        if database_file:
            path = Path(database_file)
            return path if path.exists() else None
        env_path = os.getenv("THINQ_PLAYER_ALIAS_DATABASE")
        candidates = []
        if env_path:
            candidates.append(Path(env_path))
        root = Path(__file__).resolve().parents[2]
        candidates.extend([
            root / "thinq" / "data" / "players" / "tennis_name_alias_database.json",
            root / "data" / "players" / "tennis_name_alias_database.json",
        ])
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_database(self) -> Dict[str, Any]:
        if self.database_file is None:
            return {}
        payload = self._load_json(self.database_file)
        return payload if isinstance(payload, dict) else {}

    def _load_json(self, path: Optional[Path]) -> Dict[str, Any]:
        try:
            if path and path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            print(f"[player_resolver] failed to read {path}: {exc}")
        return {}

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        payload = self._load_json(self.cache_file)
        return payload if isinstance(payload, dict) else {}

    def _save_cache(self) -> None:
        try:
            self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _normalize_tour(tour: Optional[str]) -> Optional[str]:
        text = str(tour or "").strip().upper()
        if not text:
            return None
        if text in {"M", "MEN", "MALE"}:
            return "ATP"
        if text in {"F", "WOMEN", "FEMALE"}:
            return "WTA"
        return text

    @staticmethod
    def _as_id(value: Any) -> Optional[int]:
        try:
            if value in _BLANK_VALUES:
                return None
            text = str(value)
            if text.startswith("api:") or text.startswith("id:"):
                text = text.split(":", 1)[1]
            return int(float(text))
        except Exception:
            return None

    @staticmethod
    def clean_player_name(name: Any) -> str:
        text = str(name or "").strip()
        text = PlayerResolver.fix_mojibake(text)
        text = text.replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def fix_mojibake(value: Any) -> str:
        text = str(value or "")
        for bad, good in _MOJIBAKE_REPLACEMENTS.items():
            text = text.replace(bad, good)
        return text

    @staticmethod
    def normalize_name(name: Any) -> str:
        text = PlayerResolver.clean_player_name(name).lower()
        text = "".join(_SPECIAL_CHARS.get(ch, ch) for ch in text)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    @staticmethod
    def alias_key(name: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", PlayerResolver.normalize_name(name))

    @staticmethod
    def build_ta_slug(name: str) -> str:
        normalized = PlayerResolver.normalize_name(name)
        return normalized.replace(" ", "-")

    @staticmethod
    def _unique_names(values: Iterable[Any]) -> List[str]:
        out: List[str] = []
        seen = set()
        for value in values:
            text = PlayerResolver.clean_player_name(value)
            key = PlayerResolver.alias_key(text)
            if text and key and key not in seen:
                out.append(text)
                seen.add(key)
        return out


_DEFAULT_RESOLVER: Optional[PlayerResolver] = None


def rapidapi_player_id(player_name: str, tour: Optional[str] = None) -> Optional[Any]:
    resolved = get_default_resolver().resolve(player_name, tour=tour)
    for key in ("api_team_id", "rapidapi_id", "external_player_key", "player_id", "id"):
        value = resolved.get(key)
        if value not in _BLANK_VALUES:
            return value
    return None


def get_default_resolver() -> PlayerResolver:
    global _DEFAULT_RESOLVER
    if _DEFAULT_RESOLVER is None:
        _DEFAULT_RESOLVER = PlayerResolver()
    return _DEFAULT_RESOLVER


def resolve_player(player_name: str, tour: Optional[str] = None, country: Optional[str] = None) -> Dict[str, Any]:
    return get_default_resolver().resolve(player_name, tour=tour, country=country)


def canonical_player_name(player_name: str, tour: Optional[str] = None) -> str:
    return get_default_resolver().canonicalize(player_name, tour=tour)


def get_player_name_candidates(player_name: str, tour: Optional[str] = None) -> List[str]:
    return get_default_resolver().get_name_candidates(player_name, tour=tour)


def find_profile_for_player(player_name: str, profiles_by_name: Dict[str, Any], tour: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return get_default_resolver().find_profile(player_name, profiles_by_name, tour=tour)


def normalize_name(name: Any) -> str:
    return PlayerResolver.normalize_name(name)


def alias_key(name: Any) -> str:
    return PlayerResolver.alias_key(name)
