"""
THINQ Player Resolver

Purpose:
- Keep player naming clean across History, ELO, TA, H2H and CORQ.
- Normalize aliases and provide stable canonical player metadata.
- Store local cache under thinq/data/players/player_resolver_cache.json.

This resolver is intentionally conservative:
- It never guesses IDs if they are not known.
- It safely returns canonical_name even without API IDs.
- API/provider-specific IDs can be added later without changing CORQ.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PlayerIdentity:
    input_name: str
    canonical_name: str
    normalized_name: str
    tour: Optional[str] = None
    rapidapi_id: Optional[Any] = None
    ta_slug: Optional[str] = None
    sackmann_name: Optional[str] = None
    aliases: Optional[list] = None
    source: str = "local_resolver"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PlayerResolver:
    def __init__(self, cache_file: Optional[str] = None) -> None:
        self.cache_file = Path(cache_file) if cache_file else Path("thinq/data/players/player_resolver_cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def resolve(self, player_name: str, tour: Optional[str] = None) -> Dict[str, Any]:
        normalized = self.normalize_name(player_name)
        cached = self.cache.get(normalized)
        if cached:
            if tour and not cached.get("tour"):
                cached["tour"] = tour
                self.cache[normalized] = cached
                self._save_cache()
            return cached

        canonical = self.canonicalize(player_name)
        identity = PlayerIdentity(
            input_name=player_name,
            canonical_name=canonical,
            normalized_name=normalized,
            tour=tour,
            ta_slug=self.build_ta_slug(canonical),
            sackmann_name=canonical,
            aliases=[player_name] if player_name != canonical else [],
        ).to_dict()
        self.cache[normalized] = identity
        self._save_cache()
        return identity

    def register_alias(
        self,
        canonical_name: str,
        alias: str,
        tour: Optional[str] = None,
        rapidapi_id: Optional[Any] = None,
        ta_slug: Optional[str] = None,
        sackmann_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        canonical_identity = self.resolve(canonical_name, tour=tour)
        canonical_identity["rapidapi_id"] = rapidapi_id if rapidapi_id is not None else canonical_identity.get("rapidapi_id")
        canonical_identity["ta_slug"] = ta_slug or canonical_identity.get("ta_slug")
        canonical_identity["sackmann_name"] = sackmann_name or canonical_identity.get("sackmann_name")

        aliases = canonical_identity.get("aliases") or []
        if alias not in aliases and alias != canonical_identity.get("canonical_name"):
            aliases.append(alias)
        canonical_identity["aliases"] = aliases

        self.cache[self.normalize_name(canonical_name)] = canonical_identity
        self.cache[self.normalize_name(alias)] = canonical_identity
        self._save_cache()
        return canonical_identity

    @staticmethod
    def normalize_name(name: Any) -> str:
        if name is None:
            return ""
        text = str(name).strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def canonicalize(name: Any) -> str:
        text = str(name or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def build_ta_slug(name: str) -> str:
        # Tennis Abstract slugs are not perfectly uniform, but this is a stable default.
        normalized = PlayerResolver.normalize_name(name)
        return "".join(part.capitalize() for part in normalized.split())

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if not self.cache_file.exists():
            return {}
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
