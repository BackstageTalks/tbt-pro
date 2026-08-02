"""
THINQ Player Resolver

Single source of truth for tennis player-name matching across THINQ and CORQ.

Primary data file:
- tennis_name_alias_database.json

Recommended repo location:
- thinq/data/players/tennis_name_alias_database.json

The resolver is intentionally conservative:
- Exact alias/search-key matches resolve automatically.
- Ambiguous aliases are not guessed unless a tour-scoped match is available.
- If no database is present, the resolver falls back to safe normalization only.
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


@dataclass
class PlayerIdentity:
    input_name: str
    canonical_name: str
    normalized_name: str
    player_id: Optional[str] = None
    tour: Optional[str] = None
    country: Optional[str] = None
    rank: Optional[Any] = None
    search_key: Optional[str] = None
    external_player_key: Optional[str] = None
    rapidapi_id: Optional[Any] = None
    ta_slug: Optional[str] = None
    sackmann_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    source: str = "player_resolver"
    match_status: str = "fallback"
    ambiguous: bool = False
    candidate_player_ids: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PlayerResolver:
    def __init__(self, database_file: Optional[str] = None, cache_file: Optional[str] = None) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.database_file = self._find_database_file(database_file)
        self.cache_file = Path(cache_file) if cache_file else self.root / "thinq" / "data" / "players" / "player_resolver_cache.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()
        self.database: Dict[str, Any] = self._load_database()
        self.players_by_id: Dict[str, Dict[str, Any]] = {}
        self.scoped_resolution: Dict[str, Dict[str, Any]] = {}
        self.global_resolution: Dict[str, Dict[str, Any]] = {}
        self._build_indices()

    def resolve(self, player_name: str, tour: Optional[str] = None, country: Optional[str] = None) -> Dict[str, Any]:
        raw = self.clean_player_name(player_name)
        normalized = self.normalize_name(raw)
        key = self.alias_key(raw)
        tour_key = self._normalize_tour(tour)
        cache_key = f"{tour_key or '*'}:{key}"

        cached = self.cache.get(cache_key)
        if cached:
            return cached

        identity = self._resolve_from_database(raw, key, tour_key, country)
        if identity is None:
            identity = PlayerIdentity(
                input_name=raw,
                canonical_name=raw,
                normalized_name=normalized,
                tour=tour_key,
                country=country,
                search_key=key,
                ta_slug=self.build_ta_slug(raw),
                source="fallback_normalizer",
                match_status="fallback",
            ).to_dict()

        self.cache[cache_key] = identity
        self._save_cache()
        return identity

    def canonicalize(self, name: Any, tour: Optional[str] = None) -> str:
        resolved = self.resolve(str(name or ""), tour=tour)
        return str(resolved.get("canonical_name") or self.clean_player_name(name))

    def get_name_candidates(self, name: str, tour: Optional[str] = None, include_raw: bool = True) -> List[str]:
        raw = self.clean_player_name(name)
        if not raw:
            return []

        resolved = self.resolve(raw, tour=tour)
        candidate_values: List[str] = []

        if resolved.get("canonical_name"):
            candidate_values.append(str(resolved["canonical_name"]))

        aliases = resolved.get("aliases")
        if isinstance(aliases, list):
            candidate_values.extend(str(x) for x in aliases if x)

        if include_raw:
            candidate_values.append(raw)

        lowered = raw.lower()
        if lowered.endswith(" jr"):
            candidate_values.append(raw[:-3].strip())
        elif lowered.endswith(" jr."):
            candidate_values.append(raw[:-4].strip())

        # Add common compact/space variants only as lookup candidates, not as display names.
        candidate_values.append(raw.replace("-", " "))
        candidate_values.append(raw.replace(".", " "))

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
            for field in ("player_name", "canonical_name", "name", "player", "player_key", "ta_slug"):
                val = value.get(field)
                if val:
                    yield self.clean_player_name(val)

    def _resolve_from_database(self, raw: str, key: str, tour: Optional[str], country: Optional[str]) -> Optional[Dict[str, Any]]:
        if not key or not self.database:
            return None

        resolution = None
        if tour:
            resolution = self.scoped_resolution.get(f"{tour}:{key}")
        if resolution is None:
            resolution = self.global_resolution.get(key)

        if not isinstance(resolution, dict):
            return None

        status = str(resolution.get("status") or "")
        player_id = resolution.get("resolved_player_id")
        candidates = resolution.get("candidate_player_ids") or []

        if status == "ambiguous" and not player_id:
            # Tour-scoped aliases should already be less ambiguous. If still ambiguous,
            # optionally narrow by country. Otherwise return a safe ambiguous identity.
            if country:
                country_norm = str(country).upper().strip()
                country_matches = [pid for pid in candidates if str(self.players_by_id.get(pid, {}).get("country") or "").upper() == country_norm]
                if len(country_matches) == 1:
                    player_id = country_matches[0]
                    status = "resolved_by_country"
            if not player_id:
                return PlayerIdentity(
                    input_name=raw,
                    canonical_name=raw,
                    normalized_name=self.normalize_name(raw),
                    tour=tour,
                    country=country,
                    search_key=key,
                    ta_slug=self.build_ta_slug(raw),
                    source="alias_database",
                    match_status="ambiguous",
                    ambiguous=True,
                    candidate_player_ids=list(candidates),
                ).to_dict()

        player = self.players_by_id.get(str(player_id or ""))
        if not player:
            return None

        canonical_name = str(player.get("canonical_name") or raw)
        return PlayerIdentity(
            input_name=raw,
            canonical_name=canonical_name,
            normalized_name=self.normalize_name(canonical_name),
            player_id=str(player.get("player_id") or player_id),
            tour=str(player.get("tour") or tour or "").lower() or None,
            country=player.get("country"),
            rank=player.get("rank"),
            search_key=player.get("search_key") or key,
            external_player_key=player.get("external_player_key"),
            ta_slug=self.build_ta_slug(canonical_name),
            aliases=player.get("aliases") if isinstance(player.get("aliases"), list) else None,
            source="alias_database",
            match_status=status or "resolved",
            ambiguous=False,
            candidate_player_ids=list(candidates) if candidates else None,
        ).to_dict()

    def _build_indices(self) -> None:
        self.players_by_id = {}
        self.scoped_resolution = {}
        self.global_resolution = {}

        players = self.database.get("players") if isinstance(self.database, dict) else []
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict) and player.get("player_id"):
                    self.players_by_id[str(player["player_id"])] = player

        scoped = self.database.get("scoped_alias_resolution") if isinstance(self.database, dict) else None
        if isinstance(scoped, dict):
            for key, value in scoped.items():
                if isinstance(value, dict):
                    clean_key = str(key).lower()
                    if ":" not in clean_key and value.get("tour") and value.get("raw_alias_key"):
                        clean_key = f"{str(value['tour']).lower()}:{value['raw_alias_key']}"
                    self.scoped_resolution[clean_key] = value

        # Single-tour database fallback: alias_resolution uses unscoped alias keys.
        alias_resolution = self.database.get("alias_resolution") if isinstance(self.database, dict) else None
        if isinstance(alias_resolution, dict):
            tour = str((self.database.get("metadata") or {}).get("tour") or "").lower()
            for key, value in alias_resolution.items():
                if isinstance(value, dict):
                    if tour in {"atp", "wta"}:
                        self.scoped_resolution[f"{tour}:{key}"] = value
                    self.global_resolution[str(key)] = value

        global_res = self.database.get("global_alias_resolution") if isinstance(self.database, dict) else None
        if isinstance(global_res, dict):
            for key, value in global_res.items():
                if isinstance(value, dict):
                    self.global_resolution[str(key)] = value

    def _find_database_file(self, database_file: Optional[str]) -> Optional[Path]:
        candidates: List[Path] = []
        env_path = os.getenv("TENNIS_NAME_ALIAS_DATABASE")
        if database_file:
            candidates.append(Path(database_file))
        if env_path:
            candidates.append(Path(env_path))
        candidates.extend([
            self.root / "thinq" / "data" / "players" / "tennis_name_alias_database.json",
            self.root / "data" / "name_aliases" / "tennis_name_alias_database.json",
            self.root / "tennis_name_alias_database.json",
            Path("tennis_name_alias_database.json"),
        ])
        for path in candidates:
            try:
                path = path.expanduser()
                if path.exists():
                    return path
            except Exception:
                continue
        return None

    def _load_database(self) -> Dict[str, Any]:
        if not self.database_file:
            return {}
        try:
            payload = json.loads(self.database_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if not self.cache_file.exists():
            return {}
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            # Resolver must never break prediction runs because of a cache write.
            pass

    @staticmethod
    def _normalize_tour(tour: Optional[str]) -> Optional[str]:
        if not tour:
            return None
        text = str(tour).strip().lower()
        if text in {"m", "men", "male", "atp"} or "atp" in text:
            return "atp"
        if text in {"w", "women", "female", "wta"} or "wta" in text:
            return "wta"
        return text or None

    @staticmethod
    def clean_player_name(name: Any) -> str:
        if name is None:
            return ""
        text = str(name).replace("\xa0", " ").strip()
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def normalize_name(name: Any) -> str:
        text = PlayerResolver.clean_player_name(name).lower()
        for src, dst in _SPECIAL_CHARS.items():
            text = text.replace(src, dst)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def alias_key(name: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", PlayerResolver.normalize_name(name))

    @staticmethod
    def build_ta_slug(name: str) -> str:
        normalized = PlayerResolver.normalize_name(name)
        return "".join(part[:1].upper() + part[1:] for part in normalized.split())


_DEFAULT_RESOLVER: Optional[PlayerResolver] = None



def rapidapi_player_id(player_name: str, tour: Optional[str] = None) -> Optional[Any]:
    """Return configured RapidAPI/TennisApi player id when the alias database has one."""
    resolved = get_default_resolver().resolve(player_name, tour=tour)
    for key in ("rapidapi_id", "external_player_key", "player_id", "id"):
        value = resolved.get(key)
        if value not in (None, ""):
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
