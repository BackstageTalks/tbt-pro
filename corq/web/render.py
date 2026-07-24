"""Simple robust renderer for the clean CORQ runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone
import html

BASE_URL = "https://backstagetalks.github.io/tennis-backstage-talks"
PUBLIC_DIR = Path("public")


def safe(value: Any, default: str = "-") -> str:
    if value is None or value == "":
        return default
    return html.escape(str(value))


def pct(value: Any) -> str:
    try:
        number = float(value)
        if abs(number) <= 1.0:
            number *= 100.0
        return f"{number:.1f}%"
    except Exception:
        return "-"


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "-"


def nav() -> str:
    return (
        f'<nav class="nav">'
        f'<a href="{BASE_URL}/">Corq</a>'
        f'<a href="{BASE_URL}/all/">All</a>'
        f'<a href="{BASE_URL}/results/">Results</a>'
        f'<a href="{BASE_URL}/tennis.xml">RSS</a>'
        f'</nav>'
    )


def thinq_box(prediction: Dict[str, Any]) -> str:
    thinq = prediction.get("thinq") or {}
    edges = thinq.get("edges") or prediction.get("thinq_edges") or {}
    h2h = thinq.get("h2h") or {}
    h2h_status = h2h.get("status") or prediction.get("thinq_h2h_status")
    h2h_edge = h2h.get("edge") if h2h else prediction.get("thinq_h2h_edge")
    if h2h_status in (None, "NO_DATA", "ERROR_NON_BLOCKING"):
        h2h_display = "N/A"
    else:
        h2h_display = pct(h2h_edge)
    return (
        '<div class="panel thinq-card">'
        '<div class="panel-title">THINQ</div>'
        f'<div><span>Conf</span><b>{pct(thinq.get("confidence") or prediction.get("thinq_confidence"))}</b></div>'
        f'<div><span>ELO PICK</span><b>{pct(edges.get("elo_edge"))}</b></div>'
        f'<div><span>H2H</span><b>{safe(h2h_display)}</b></div>'
        f'<div><span>ADJ</span><b>{pct(prediction.get("thinq_total_adjustment"))}</b></div>'
        '</div>'
    )


def intelligence(prediction: Dict[str, Any]) -> str:
    return (
        '<div class="intel-grid">'
        '<div class="panel"><div class="panel-title">DATA AI</div>'
        f'<div><span>Corq</span><b>{pct(prediction.get("corq_probability") or prediction.get("probability"))}</b></div>'
        '</div>'
        '<div class="panel"><div class="panel-title">MARQ</div><div>Market later</div></div>'
        '<div class="panel"><div class="panel-title">SETS / GAMES</div>'
        f'<div><span>Sets</span><b>{safe(prediction.get("expected_sets"))}</b></div>'
        f'<div><span>Games</span><b>{safe(prediction.get("expected_games"))}</b></div>'
        '</div>'
        f'{thinq_box(prediction)}'
        '</div>'
    )


def row(prediction: Dict[str, Any], index: int) -> str:
    pick_odds = prediction.get("pick_odds") or prediction.get("odds")
    opp_odds = prediction.get("opponent_odds")
    return (
        '<tr>'
        f'<td class="rank">#{index}</td>'
        f'<td><div class="pick-name">{safe(prediction.get("pick"))}</div>'
        f'<div class="pick-odds">Pick @{num(pick_odds)}</div>'
        '<div class="to-win">TO WIN</div>'
        f'<div class="meta">{safe(prediction.get("tournament"))} - {safe(prediction.get("surface"))} - BO{safe(prediction.get("best_of"))}</div></td>'
        f'<td><div class="opp-name">{safe(prediction.get("opponent"))}</div><div class="opp-odds">Opp @{num(opp_odds)}</div></td>'
        f'<td>{pct(prediction.get("corq_probability") or prediction.get("probability"))}</td>'
        f'<td>{num(prediction.get("corq_adjusted_score"), 3)}</td>'
        f'<td class="intel">{intelligence(prediction)}</td>'
        '</tr>'
    )


CSS = """
body{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,Helvetica,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px}.nav a{color:#e5e7eb;margin-right:16px;text-decoration:none;font-weight:800}
table{width:100%;border-collapse:collapse;background:#111827;border:1px solid #334155}td,th{padding:12px;border-bottom:1px solid #334155;vertical-align:top}th{color:#94a3b8;text-align:left}
.rank{color:#38bdf8;font-weight:900}.pick-name{font-weight:900;font-size:18px}.pick-odds{color:#22c55e;font-weight:900;margin-top:5px}.opp-odds{color:#94a3b8;font-weight:900;margin-top:5px}.to-win{color:#22c55e;font-size:12px;font-weight:900;margin-top:4px}.meta{color:#38bdf8;font-size:12px;margin-top:7px}
.intel-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px}.panel{border:1px solid #334155;background:rgba(100,116,139,.12);border-radius:10px;padding:8px;font-size:12px}.panel-title{font-weight:900;color:#fff;margin-bottom:6px}.panel div:not(.panel-title){display:flex;justify-content:space-between;gap:8px;margin:3px 0}.thinq-card{border-color:#38bdf8}@media(max-width:900px){.intel-grid{grid-template-columns:1fr}}
"""


def render_page(predictions: List[Dict[str, Any]], title: str) -> str:
    rows = "\n".join(row(prediction, index) for index, prediction in enumerate(predictions, 1))
    if not rows:
        rows = '<tr><td colspan="6">No picks available</td></tr>'
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{safe(title)}</title><style>{CSS}</style></head><body>'
        f'<div class="wrap"><h1>{safe(title)}</h1>{nav()}<p>Updated {updated}</p>'
        f'<table><thead><tr><th>#</th><th>Pick</th><th>Opponent</th><th>Win %</th><th>Score</th><th>Match Intelligence</th></tr></thead><tbody>{rows}</tbody></table>'
        '</div></body></html>'
    )


def write(path: Path, html_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def render_all_pages(all_predictions: List[Dict[str, Any]], corq_predictions: List[Dict[str, Any]], top7: List[Dict[str, Any]]) -> None:
    write(PUBLIC_DIR / "index.html", render_page(top7, "Corq TOP7"))
    write(PUBLIC_DIR / "all" / "index.html", render_page(all_predictions, "All Predictions"))
