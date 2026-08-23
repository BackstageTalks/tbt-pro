from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone
import html
BASE_URL = 'https://backstagetalks.github.io/tennis-backstage-talks'
PUBLIC_DIR = Path('public')

def safe(value, default='-'):
    if value in (None, ''): return default
    return html.escape(str(value))

def pct(value):
    try:
        number = float(value)
        if number <= 1.0: number *= 100
        return f'{number:.1f}%'
    except Exception: return '-'

def num(value, digits=2):
    try: return f'{float(value):.{digits}f}'
    except Exception: return '-'

def nav():
    return '<nav class="nav"><a href="%s/">Corq</a><a href="%s/all/">All</a><a href="%s/results/">Results</a><a href="%s/tennis.xml">RSS</a></nav>' % (BASE_URL, BASE_URL, BASE_URL, BASE_URL)

def thinq_box(p):
    thinq = p.get('thinq') or {}
    h2h = thinq.get('h2h') or {}
    edges = thinq.get('edges') or {}
    h2h_display = 'N/A' if h2h.get('status') in (None, 'NO_DATA', 'ERROR_NON_BLOCKING') else pct(h2h.get('edge'))
    return '<div class="panel thinq-card"><div class="panel-title">THINQ</div><div><span>Conf</span><b>%s</b></div><div><span>ELO PICK</span><b>%s</b></div><div><span>H2H</span><b>%s</b></div><div><span>ADJ</span><b>%s</b></div></div>' % (pct(thinq.get('confidence') or p.get('thinq_confidence')), pct(edges.get('elo_edge')), safe(h2h_display), pct(p.get('thinq_total_adjustment')))

def row(p, idx):
    intel = '<div class="grid"><div class="panel"><div class="panel-title">DATA AI</div><div>Corq <b>%s</b></div></div><div class="panel"><div class="panel-title">MARQ</div><div>Market later</div></div><div class="panel"><div class="panel-title">SETS / GAMES</div><div>Sets <b>%s</b></div></div>%s</div>' % (pct(p.get('corq_probability') or p.get('probability')), safe(p.get('expected_sets')), thinq_box(p))
    return '<tr><td>#%s</td><td><b>%s</b><br><span class="odds">Pick @%s</span><br><span class="towin">TO WIN</span><br><small>%s - %s - BO%s</small></td><td>%s<br><span class="opp">Opp @%s</span></td><td>%s</td><td>%s</td><td class="intel">%s</td></tr>' % (idx, safe(p.get('pick')), num(p.get('pick_odds') or p.get('odds')), safe(p.get('tournament')), safe(p.get('surface')), safe(p.get('best_of')), safe(p.get('opponent')), num(p.get('opponent_odds')), pct(p.get('corq_probability') or p.get('probability')), num(p.get('corq_adjusted_score'), 3), intel)

def render_page(predictions: List[Dict[str, Any]], title: str) -> str:
    rows = '\n'.join(row(p, i) for i, p in enumerate(predictions, 1)) or '<tr><td colspan="6">No picks</td></tr>'
    updated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    css = 'body{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,Helvetica,sans-serif}.wrap{max-width:1500px;margin:0 auto;padding:28px}.nav a{color:#e5e7eb;margin-right:16px;text-decoration:none;font-weight:800}table{width:100%;border-collapse:collapse;background:#111827;border:1px solid #334155}td,th{padding:12px;border-bottom:1px solid #334155;vertical-align:top}th{color:#94a3b8;text-align:left}.odds{color:#22c55e;font-weight:800}.opp{color:#94a3b8;font-weight:800}.towin{color:#22c55e;font-size:12px;font-weight:900}.grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px}.panel{border:1px solid #334155;background:rgba(100,116,139,.12);border-radius:10px;padding:8px;font-size:12px}.panel-title{font-weight:900;color:#fff;margin-bottom:6px}.panel div:not(.panel-title){display:flex;justify-content:space-between;gap:8px;margin:3px 0}.thinq-card{border-color:#38bdf8}small{color:#38bdf8}@media(max-width:900px){.grid{grid-template-columns:1fr}}'
    return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style></head><body><div class="wrap"><h1>%s</h1>%s<p>Updated %s</p><table><thead><tr><th>#</th><th>Pick</th><th>Opponent</th><th>Win %%</th><th>Score</th><th>Match Intelligence</th></tr></thead><tbody>%s</tbody></table></div></body></html>' % (safe(title), css, safe(title), nav(), updated, rows)

def write(path: Path, html_text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding='utf-8')

def render_all_pages(all_predictions, corq_predictions, top7):
    write(PUBLIC_DIR / 'index.html', render_page(top7, 'Corq TOP7'))
    write(PUBLIC_DIR / 'all' / 'index.html', render_page(all_predictions, 'All Predictions'))
