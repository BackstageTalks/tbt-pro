import html
import json
from pathlib import Path

EXPLANATIONS_PATH = Path(__file__).with_name("explanations.json")

_FALLBACK_EXPLANATIONS = {
    "corq_box": {
        "title": "CorQ",
        "text": "CorQ is the final win probability for the displayed pick.",
    },
    "thinq_box": {
        "title": "ThinQ",
        "text": "ThinQ is the overall data quality behind the match analysis.",
    },
}


def load_explanations(path: Path | str | None = None) -> dict:
    """Load tooltip explanations from JSON.

    Tooltip text is intentionally stored in corq/web/explanations.json so it can
    be edited without changing the web renderer.
    """
    p = Path(path) if path else EXPLANATIONS_PATH
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return dict(_FALLBACK_EXPLANATIONS)


_EXPLANATIONS = load_explanations()


def reload_explanations() -> None:
    """Reload explanations after editing explanations.json."""
    global _EXPLANATIONS
    _EXPLANATIONS = load_explanations()


def get_explanation(key: str) -> dict:
    item = _EXPLANATIONS.get(key) or {}
    if not isinstance(item, dict):
        return {}
    return item


def tooltip_icon(key: str, css_class: str = "info-dot") -> str:
    """Return a small accessible information icon with tooltip text."""
    item = get_explanation(key)
    title = html.escape(str(item.get("title") or "Info"), quote=True)
    text = html.escape(str(item.get("text") or item.get("short") or "No explanation available."), quote=True)
    return (
        f'<span class="{css_class}" tabindex="0" role="button" '
        f'aria-label="{title}: {text}" data-tip-title="{title}" data-tip-text="{text}">i</span>'
    )


def tooltip_css() -> str:
    """CSS for the info icons and hover/focus tooltip bubbles."""
    return '\n.info-dot {\n  display: inline-flex;\n  align-items: center;\n  justify-content: center;\n  width: 15px;\n  height: 15px;\n  margin-left: 5px;\n  border-radius: 999px;\n  border: 1px solid rgba(125, 211, 252, 0.70);\n  color: #7dd3fc;\n  background: rgba(14, 165, 233, 0.08);\n  font-size: 10px;\n  font-weight: 800;\n  line-height: 1;\n  cursor: help;\n  position: relative;\n  vertical-align: middle;\n}\n.info-dot::after {\n  content: attr(data-tip-title) "\\A" attr(data-tip-text);\n  white-space: pre-line;\n  pointer-events: none;\n  position: absolute;\n  z-index: 50;\n  left: 50%;\n  top: 22px;\n  transform: translateX(-50%);\n  width: min(300px, 72vw);\n  padding: 10px 12px;\n  border: 1px solid rgba(56, 189, 248, 0.35);\n  border-radius: 12px;\n  background: rgba(2, 12, 27, 0.98);\n  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);\n  color: #cbd5e1;\n  font-size: 11px;\n  font-weight: 600;\n  line-height: 1.35;\n  opacity: 0;\n  visibility: hidden;\n  transition: opacity .14s ease, visibility .14s ease;\n}\n.info-dot:hover::after,\n.info-dot:focus::after {\n  opacity: 1;\n  visibility: visible;\n}\n'
