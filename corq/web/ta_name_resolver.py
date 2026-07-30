# corq/web/ta_name_resolver.py
"""
Compatibility wrapper around thinq.loaders.player_resolver.

All player-name matching now comes from one shared database:
- tennis_name_alias_database.json

Keep this file so existing CORQ imports do not break, but do not maintain
separate hard-coded name aliases here anymore.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from thinq.loaders.player_resolver import (
        canonical_player_name,
        find_profile_for_player,
        get_player_name_candidates,
    )
except Exception:  # pragma: no cover - safe fallback for isolated render contexts
    canonical_player_name = None
    find_profile_for_player = None
    get_player_name_candidates = None


def clean_player_name(name: str) -> str:
    if not name:
        return ""
    return " ".join(str(name).replace("\xa0", " ").strip().split())


def get_ta_name_candidates(name: str, tour: Optional[str] = None) -> List[str]:
    raw = clean_player_name(name)
    if not raw:
        return []
    if get_player_name_candidates is not None:
        candidates = get_player_name_candidates(raw, tour=tour)
    else:
        candidates = [raw]
    out: List[str] = []
    seen = set()
    for candidate in candidates:
        candidate = clean_player_name(candidate)
        key = candidate.lower()
        if candidate and key not in seen:
            out.append(candidate)
            seen.add(key)
    return out


def normalize_player_name_for_ta(name: str, tour: Optional[str] = None) -> str:
    raw = clean_player_name(name)
    if not raw:
        return ""
    if canonical_player_name is not None:
        return clean_player_name(canonical_player_name(raw, tour=tour))
    return raw


def find_ta_profile_for_player(player_name: str, ta_profiles_by_name: Dict[str, Any], tour: Optional[str] = None):
    if not isinstance(ta_profiles_by_name, dict):
        return None
    if find_profile_for_player is not None:
        profile = find_profile_for_player(player_name, ta_profiles_by_name, tour=tour)
        if profile:
            return profile

    # Defensive fallback: exact normalized lookup only.
    lookup = {}
    for key, value in ta_profiles_by_name.items():
        lookup[clean_player_name(key).lower()] = value
    for candidate_name in get_ta_name_candidates(player_name, tour=tour):
        profile = lookup.get(clean_player_name(candidate_name).lower())
        if profile:
            return profile
    return None
