# corq/web/ta_name_resolver.py

TA_NAME_ALIASES = {
    'martin damm jr': 'Martin Damm',
    'martin damm jr.': 'Martin Damm',
    'catherine mcnally': 'Caty Mcnally',
    'catherine mcnally.': 'Caty Mcnally',
    'caty mcnally': 'Caty Mcnally',
    'anastasia soboleva': 'Anastasiya Soboleva',
    'anastasiya soboleva': 'Anastasiya Soboleva',
    'miriam bulgaru': 'Miriam Bianca Bulgaru',
    'miriam bianca bulgaru': 'Miriam Bianca Bulgaru',
}


def clean_player_name(name: str) -> str:
    if not name:
        return ''
    return ' '.join(str(name).strip().split())


def get_ta_name_candidates(name: str) -> list:
    raw = clean_player_name(name)
    if not raw:
        return []
    key = raw.lower()
    candidates = []
    if key in TA_NAME_ALIASES:
        candidates.append(TA_NAME_ALIASES[key])
    candidates.append(raw)
    lowered = raw.lower()
    if lowered.endswith(' jr'):
        candidates.append(raw[:-3].strip())
    elif lowered.endswith(' jr.'):
        candidates.append(raw[:-4].strip())
    out = []
    seen = set()
    for candidate in candidates:
        candidate = clean_player_name(candidate)
        candidate_key = candidate.lower()
        if candidate and candidate_key not in seen:
            out.append(candidate)
            seen.add(candidate_key)
    return out


def normalize_player_name_for_ta(name: str) -> str:
    candidates = get_ta_name_candidates(name)
    return candidates[0] if candidates else ''


def find_ta_profile_for_player(player_name: str, ta_profiles_by_name: dict):
    if not isinstance(ta_profiles_by_name, dict):
        return None
    lookup = {}
    for key, value in ta_profiles_by_name.items():
        lookup[clean_player_name(key).lower()] = value
    for candidate_name in get_ta_name_candidates(player_name):
        profile = lookup.get(candidate_name.lower())
        if profile:
            return profile
    return None
