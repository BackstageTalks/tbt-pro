"""User-facing message registry for CorQ/ThinQ/CloQ public output.

Raw technical flags should stay in JSON, but public pages should use these
labels or hide low-value internal flags.
"""

FLAG_MESSAGES = {
    "RECENT_FORM_NO_DATA": {"label": "Recent form pending", "show_public": True, "severity": "info"},
    "RECENT_FORM_NO_PLAYER_MATCHES": {"label": "Recent form pending", "show_public": True, "severity": "info"},
    "MATCH_DYNAMICS_RECENT_FORM_NEUTRAL": {"label": "Recent form neutral", "show_public": False, "severity": "neutral"},
    "NO_H2H_DATA": {"label": "No previous H2H matches", "show_public": True, "severity": "info"},
    "H2H_NO_PREVIOUS_MATCHES": {"label": "No previous H2H matches", "show_public": True, "severity": "info"},
    "MISSING_ELO": {"label": "ELO coverage missing", "show_public": True, "severity": "warning"},
    "MISSING_ELO_PICK": {"label": "Pick ELO unavailable", "show_public": False, "severity": "warning"},
    "MISSING_ELO_OPPONENT": {"label": "Opponent ELO unavailable", "show_public": False, "severity": "warning"},
    "DIRECT_BY_NUMERIC_OUTCOME": {"label": "Odds confirmed", "show_public": False, "severity": "info"},
    "REVERSED_BY_NUMERIC_OUTCOME": {"label": "Odds confirmed", "show_public": False, "severity": "info"},
    "DIRECT_OR_LABEL_UNKNOWN": {"label": "Odds orientation unconfirmed", "show_public": True, "severity": "warning"},
    "DEFAULT_SCORE_VALUE_TRAP": {"label": "Low data value risk", "show_public": True, "severity": "warning"},
    "NO_INTELLIGENCE_OUTSIDER_VALUE_TRAP": {"label": "Low data outsider risk", "show_public": True, "severity": "warning"},
    "LOW_THINQ_CONFIDENCE": {"label": "Low ThinQ data confidence", "show_public": True, "severity": "warning"},
}


def public_flag_labels(flags):
    """Return public labels for internal flags."""
    out = []
    for flag in flags or []:
        item = FLAG_MESSAGES.get(str(flag), None)
        if item is None:
            continue
        if item.get("show_public"):
            out.append(item.get("label") or str(flag))
    return out
