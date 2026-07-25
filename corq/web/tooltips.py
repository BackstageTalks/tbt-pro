from __future__ import annotations

import html
import json
from pathlib import Path

EXPLANATIONS_PATH = Path(__file__).with_name("explanations.json")

_FALLBACK = {
    "corq_box": {"title": "CorQ", "text": "CorQ is the final win probability for the displayed pick."},
    "thinq_box": {"title": "ThinQ", "text": "ThinQ is the overall data quality behind the match analysis."},
}


def load_explanations(path: Path | str | None = None) -> dict:
    p = Path(path) if path else EXPLANATIONS_PATH
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return dict(_FALLBACK)

_EXPLANATIONS = load_explanations()


def tooltip_icon(key: str, css_class: str = "info-dot") -> str:
    item = _EXPLANATIONS.get(key) or {}
    title = html.escape(str(item.get("title") or "Info"), quote=True)
    text = html.escape(str(item.get("text") or "No explanation available."), quote=True)
    return (
        f'<span class="{css_class}" tabindex="0" role="button" '
        f'aria-label="{title}: {text}" data-tip-title="{title}" data-tip-text="{text}">i</span>'
    )


def tooltip_css() -> str:
    return '\n.info-dot{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;margin-left:6px;border-radius:999px;border:1px solid rgba(125,211,252,.72);color:#7dd3fc;background:rgba(14,165,233,.10);font-size:10px;font-weight:900;line-height:1;cursor:help;position:relative;vertical-align:middle;text-transform:none;letter-spacing:0}.info-dot::after{content:attr(data-tip-title) "\\A" attr(data-tip-text);white-space:pre-line;pointer-events:none;position:absolute;z-index:999;left:50%;top:22px;transform:translateX(-50%);width:min(320px,75vw);padding:10px 12px;border:1px solid rgba(56,189,248,.42);border-radius:12px;background:rgba(2,12,27,.98);box-shadow:0 18px 40px rgba(0,0,0,.48);color:#cbd5e1;font-size:11px;font-weight:600;line-height:1.35;text-transform:none;letter-spacing:0;opacity:0;visibility:hidden;transition:opacity .14s ease,visibility .14s ease}.info-dot:hover::after,.info-dot:focus::after{opacity:1;visibility:visible}\n'
