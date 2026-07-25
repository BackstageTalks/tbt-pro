from __future__ import annotations

FLAG_MESSAGES = {
    "RECENT_FORM_NO_DATA": {"label": "Form pending", "show_public": True},
    "RECENT_FORM_NO_PLAYER_MATCHES": {"label": "Form pending", "show_public": True},
    "NO_H2H_DATA": {"label": "No previous matches", "show_public": True},
    "H2H_NO_DATA": {"label": "No previous matches", "show_public": True},
    "MATCH_DYNAMICS_RECENT_FORM_NEUTRAL": {"label": "", "show_public": False},
    "DIRECT_BY_NUMERIC_OUTCOME": {"label": "Confirmed", "show_public": False},
    "REVERSED_BY_NUMERIC_OUTCOME": {"label": "Confirmed", "show_public": False},
    "DIRECT_OR_LABEL_UNKNOWN": {"label": "Odds direction unconfirmed", "show_public": True},
    "MISSING_ELO": {"label": "ELO unavailable", "show_public": True},
    "DEFAULT_SCORE_VALUE_TRAP": {"label": "Low data value risk", "show_public": True},
    "NO_INTELLIGENCE_OUTSIDER_VALUE_TRAP": {"label": "Low data outsider risk", "show_public": True},
}

def flag_message(flag: str) -> dict:
    key = str(flag or "").strip()
    return FLAG_MESSAGES.get(key, {"label": key.replace("_", " ").title(), "show_public": True})

def public_flag_labels(flags) -> list[str]:
    labels = []
    seen = set()
    for flag in flags or []:
        meta = flag_message(flag)
        label = meta.get("label") or ""
        if not meta.get("show_public", True) or not label:
            continue
        if label not in seen:
            labels.append(label)
            seen.add(label)
    return labels
