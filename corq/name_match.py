"""Robust tennis player name matching helpers.

Goals:
- Match full names, abbreviated names and reversed names.
- Normalize accents, punctuation, suffixes and common spelling variants.
- Provide high-confidence matching for odds labels vs event player labels.

Examples:
- Tomas Martin Etcheverry == T. Etcheverry
- Tomas Martin Etcheverry == Etcheverry Tomas Martin
- Liudmila Samsonova == Ludmila Samsonova
- Xinyu Wang == Wang Xinyu
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Set

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
        "ı": "i", "İ": "I",
    }
)

# Keep this list deliberately small and tennis-focused.  It solves the common
# odds-feed spelling variants without making fuzzy surname-only matches too loose.
_TOKEN_ALIASES: Dict[str, str] = {
    "ludmila": "liudmila",
    "ludmilla": "liudmila",
    "liudmyla": "liudmila",
    "kateryna": "katerina",
    "katarina": "katerina",
    "anastasiya": "anastasia",
    "anastasija": "anastasia",
    "yuliya": "julia",
    "jule": "julia",
    "xinyu": "xinyu",
    "xin": "xinyu",
    "ching": "qing",
    "chingwen": "qingwen",
    "qinwen": "qingwen",
    "mcnally": "mcnally",
    "mc": "mc",
}

_SUFFIX_TOKENS = {
    "jr", "junior", "sr", "senior", "ii", "iii", "iv",
}

_PARTICLE_TOKENS = {
    "de", "del", "della", "di", "da", "dos", "das", "van", "von", "la", "le",
}


def _strip_bracketed_rank(value: str) -> str:
    # Remove rank-like decorations from labels, e.g. "Player Name (42)".
    return re.sub(r"\((?:\d+|nr|unr|x)\)", " ", value, flags=re.I)


def _canonical_token(token: str) -> str:
    token = token.strip().lower()
    if token in _SUFFIX_TOKENS:
        return ""
    return _TOKEN_ALIASES.get(token, token)


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().translate(_TRANSLATE).lower()
    text = _strip_bracketed_rank(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace(".", " ").replace("-", " ").replace("_", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [_canonical_token(tok) for tok in text.split()]
    tokens = [tok for tok in tokens if tok]
    return " ".join(tokens)


def compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def _tokens(value: Any) -> List[str]:
    return normalize_name(value).split()


def _without_particles(tokens: Iterable[str]) -> List[str]:
    return [tok for tok in tokens if tok not in _PARTICLE_TOKENS]


def _initials(tokens: List[str]) -> str:
    return "".join(tok[0] for tok in tokens if tok)


def name_variants(value: Any) -> Set[str]:
    tokens = _tokens(value)
    variants: Set[str] = set()
    normalized = " ".join(tokens)
    compact = compact_name(value)
    if normalized:
        variants.add(normalized)
    if compact:
        variants.add(compact)
    if not tokens:
        return variants

    no_particles = _without_particles(tokens)
    if no_particles and no_particles != tokens:
        variants.add(" ".join(no_particles))
        variants.add(compact_name(" ".join(no_particles)))

    first = tokens[0]
    last = tokens[-1]
    variants.add(last)
    variants.add(compact_name(last))

    if len(tokens) >= 2:
        variants.add(f"{first[0]} {last}")
        variants.add(f"{first[0]}{last}")
        variants.add(f"{last} {first[0]}")
        variants.add(f"{last}{first[0]}")
        variants.add(" ".join(reversed(tokens)))
        variants.add(compact_name(" ".join(reversed(tokens))))
        variants.add(f"{_initials(tokens[:-1])} {last}")
        variants.add(f"{_initials(tokens[:-1])}{last}")

    if len(tokens) >= 3:
        last_two = " ".join(tokens[-2:])
        variants.add(last_two)
        variants.add(compact_name(last_two))
        variants.add(f"{first[0]} {last_two}")
        variants.add(f"{first[0]}{compact_name(last_two)}")
        variants.add(" ".join([tokens[-1], *tokens[:-1]]))
        variants.add(compact_name(" ".join([tokens[-1], *tokens[:-1]])))

    return {item for item in variants if item}


def _surname_score(a_tokens: List[str], b_tokens: List[str], a_compact: str, b_compact: str) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    if a_tokens[-1] != b_tokens[-1]:
        return 0.0
    # Same surname + matching first initial is strong enough for odds labels.
    if a_tokens[0][0] == b_tokens[0][0]:
        return 0.93
    # Same surname alone is possible, but not max confidence.
    return max(0.78, SequenceMatcher(None, a_compact, b_compact).ratio())


def name_match_score(a: Any, b: Any) -> float:
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0

    a_compact = compact_name(a)
    b_compact = compact_name(b)
    if a_compact and a_compact == b_compact:
        return 1.0

    a_variants = name_variants(a)
    b_variants = name_variants(b)
    if a_variants.intersection(b_variants):
        return 0.97

    a_tokens = _tokens(a)
    b_tokens = _tokens(b)
    surname = _surname_score(a_tokens, b_tokens, a_compact, b_compact)
    if surname:
        return surname

    if a_compact and b_compact and (a_compact in b_compact or b_compact in a_compact):
        return 0.84

    # Reversed-name similarity catches "Wang Xinyu" vs "Xinyu Wang" even when
    # aliases/variants did not hit for some reason.
    reversed_a = compact_name(" ".join(reversed(a_tokens))) if a_tokens else ""
    reversed_b = compact_name(" ".join(reversed(b_tokens))) if b_tokens else ""
    base = SequenceMatcher(None, a_compact, b_compact).ratio()
    rev = max(
        SequenceMatcher(None, reversed_a, b_compact).ratio() if reversed_a else 0.0,
        SequenceMatcher(None, a_compact, reversed_b).ratio() if reversed_b else 0.0,
    )
    return max(base, rev)


def names_match(a: Any, b: Any, threshold: float = 0.78) -> bool:
    return name_match_score(a, b) >= threshold
