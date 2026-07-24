"""User-facing message registry for CORQ/THINQ public outputs.

Raw technical flags stay in JSON for audit/debug, but UI, Telegram and Results
should use this registry and never display raw flags such as RECENT_FORM_NO_DATA.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

FLAG_MESSAGES: Dict[str, Dict[str, Any]] = {
    "RECENT_FORM_NO_DATA": {
        "label": "Form pending",
        "message": "Recent form data is not available yet.",
        "severity": "info",
        "show_public": True,
    },
    "MATCH_DYNAMICS_RECENT_FORM_NEUTRAL": {
        "label": "Form neutral",
        "message": "Recent form is neutral or not strong enough to affect the model.",
        "severity": "neutral",
        "show_public": False,
    },
    "NO_H2H_DATA": {
        "label": "No H2H data",
        "message": "No head-to-head history found.",
        "severity": "info",
        "show_public": True,
    },
    "MISSING_ELO": {
        "label": "ELO unavailable",
        "message": "ELO data is missing for one or both players.",
        "severity": "warning",
        "show_public": True,
    },
    "THINQ_LOW_CONFIDENCE": {
        "label": "Low THINQ confidence",
        "message": "THINQ confidence is limited for this matchup.",
        "severity": "warning",
        "show_public": True,
    },
    "THINQ_SERVICE_UNAVAILABLE": {
        "label": "THINQ unavailable",
        "message": "THINQ intelligence layer is not available for this matchup.",
        "severity": "warning",
        "show_public": True,
    },
    "THINQ_ATTACH_FAILED": {
        "label": "THINQ unavailable",
        "message": "THINQ intelligence layer could not be attached to this matchup.",
        "severity": "warning",
        "show_public": True,
    },
    "SURFACE_UNKNOWN": {
        "label": "Surface unknown",
        "message": "Surface data is missing or unclear.",
        "severity": "info",
        "show_public": True,
    },
    "CARPET_AS_HARD_FALLBACK": {
        "label": "Carpet treated as hard",
        "message": "Carpet surface is evaluated with hard-court ELO fallback.",
        "severity": "info",
        "show_public": True,
    },
    "H2H_PICK_EDGE": {
        "label": "H2H supports pick",
        "message": "Head-to-head history supports the selected pick.",
        "severity": "positive",
        "show_public": False,
    },
    "H2H_OPP_EDGE": {
        "label": "H2H supports opponent",
        "message": "Head-to-head history supports the opponent.",
        "severity": "risk",
        "show_public": False,
    },
    "H2H_NEUTRAL": {
        "label": "H2H neutral",
        "message": "Head-to-head history is neutral.",
        "severity": "neutral",
        "show_public": False,
    },
    "ELO_PICK_EDGE": {
        "label": "ELO supports pick",
        "message": "ELO supports the selected pick.",
        "severity": "positive",
        "show_public": False,
    },
    "RECENT_FORM_NEUTRAL": {
        "label": "Form neutral",
        "message": "Recent form is neutral.",
        "severity": "neutral",
        "show_public": False,
    },
    "SURFACE_FORM_NEUTRAL": {
        "label": "Surface form neutral",
        "message": "Surface form is neutral.",
        "severity": "neutral",
        "show_public": False,
    },
    "WARN_NOT_NOTSTARTED": {
        "label": "Match already active/finished",
        "message": "Match status is not notstarted.",
        "severity": "warning",
        "show_public": False,
    },
    "WARN_STARTED_OR_TOO_CLOSE": {
        "label": "Match started or close",
        "message": "Match is already started or close to start.",
        "severity": "warning",
        "show_public": False,
    },
    "WARN_STATUS_NOT_OPEN": {
        "label": "Status not open",
        "message": "Match status is not open for a clean public pick.",
        "severity": "warning",
        "show_public": False,
    },
    "WARN_RECENT_FORM_NO_DATA": {
        "label": "Form pending",
        "message": "Recent form data is not available yet.",
        "severity": "info",
        "show_public": False,
    },
}

DEFAULT_FLAG_MESSAGE = {
    "label": "Model note",
    "message": "Additional model note is available in audit data.",
    "severity": "info",
    "show_public": False,
}


def describe_flag(flag: Any) -> Dict[str, Any]:
    key = str(flag or "").strip()
    data = dict(FLAG_MESSAGES.get(key, DEFAULT_FLAG_MESSAGE))
    data["flag"] = key
    return data


def public_messages(flags: Iterable[Any], include_hidden: bool = False) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for flag in flags or []:
        item = describe_flag(flag)
        key = item.get("flag")
        if not key or key in seen:
            continue
        seen.add(key)
        if include_hidden or item.get("show_public"):
            output.append(item)
    return output


def public_message_labels(flags: Iterable[Any], include_hidden: bool = False) -> List[str]:
    return [item.get("label") for item in public_messages(flags, include_hidden=include_hidden) if item.get("label")]
