"""Public message registry for technical flags."""
from __future__ import annotations
from typing import Iterable, List

FLAG_MESSAGES = {
    "RECENT_FORM_NO_DATA": {"label": "Form pending", "show_public": True},
    "RECENT_FORM_NO_PLAYER_MATCHES": {"label": "Form pending", "show_public": True},
    "MATCH_DYNAMICS_RECENT_FORM_NEUTRAL": {"label": "", "show_public": False},
    "NO_H2H_DATA": {"label": "H2H unavailable", "show_public": True},
    "MISSING_ELO": {"label": "ELO unavailable", "show_public": True},
    "SURFACE_UNKNOWN": {"label": "Surface unknown", "show_public": True},
    "SURFACE_RECENT_FORM_THIN": {"label": "Surface form thin", "show_public": True},
    "CARPET_AS_HARD_FALLBACK": {"label": "", "show_public": False},
    "DEFAULT_SCORE_VALUE_TRAP": {"label": "Low data value risk", "show_public": True},
    "NO_INTELLIGENCE_OUTSIDER_VALUE_TRAP": {"label": "Low data outsider risk", "show_public": True},
    "DIRECT_BY_NUMERIC_OUTCOME": {"label": "", "show_public": False},
    "REVERSED_BY_NUMERIC_OUTCOME": {"label": "", "show_public": False},
}

def flag_label(flag: str) -> str | None:
    item = FLAG_MESSAGES.get(str(flag))
    if item is None or not item.get("show_public", False):
        return None
    label = str(item.get("label") or "").strip()
    return label or None

def public_flag_labels(flags: Iterable[str], max_items: int = 4) -> List[str]:
    out: List[str] = []
    seen = set()
    for flag in flags:
        label = flag_label(str(flag))
        if not label or label in seen:
            continue
        out.append(label)
        seen.add(label)
        if len(out) >= max_items:
            break
    return out
