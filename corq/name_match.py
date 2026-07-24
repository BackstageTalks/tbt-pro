"""Small robust tennis player name matching helpers.

Goal:
- Match full names, abbreviated names and reversed names without pulling in
  old project ballast.

Examples:
- Tomas Martin Etcheverry == T. Etcheverry
- Tomas Martin Etcheverry == Etcheverry Tomas Martin
- Tereza Valentova == T. Valentova
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, List, Set

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


def _tokens(value: Any) -> List[str]:
    return normalize_name(value).split()


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

    if len(tokens) >= 3:
        last_two = " ".join(tokens[-2:])
        variants.add(last_two)
        variants.add(compact_name(last_two))
        variants.add(f"{first[0]} {last_two}")
        variants.add(f"{first[0]}{compact_name(last_two)}")

    return {item for item in variants if item}


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
        return 0.96

    a_tokens = _tokens(a)
    b_tokens = _tokens(b)
    if a_tokens and b_tokens and a_tokens[-1] == b_tokens[-1]:
        # surname match, but not enough alone for max confidence
        return max(0.78, SequenceMatcher(None, a_compact, b_compact).ratio())

    if a_compact and b_compact and (a_compact in b_compact or b_compact in a_compact):
        return 0.82

    return SequenceMatcher(None, a_compact, b_compact).ratio()


def names_match(a: Any, b: Any, threshold: float = 0.78) -> bool:
    return name_match_score(a, b) >= threshold
