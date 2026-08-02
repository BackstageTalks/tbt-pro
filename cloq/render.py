"""CloQ HTML renderer.

Standalone diagnostics renderer for the CloQ layer.

Default layout after this patch:
  input:  outputs/cloq/latest_cloq.json
  output: outputs/cloq/index.html

Fallback input is kept for compatibility with older runs:
  outputs/latest_cloq.json
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, List, Optional


WEB_DISPLAY_TIMEZONE = ZoneInfo("Europe/Bratislava")

def _format_dt_part(value: Any, fmt: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if text.isdigit() and len(text) in (10, 13):
            dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.astimezone(WEB_DISPLAY_TIMEZONE).strftime(fmt)
    except Exception:
        return ""

def _date_time_pill(value: Any) -> str:
    d = _format_dt_part(value, "%d.%m.%y")
    t = _format_dt_part(value, "%H:%M")
    if not d and not t:
        return ""
    return f'<span class="cloq-date-time"><span class="cloq-date">{_esc(d)}</span><span class="cloq-clock">{_esc(t)}</span></span>'

def _load_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "cloq", "items", "data", "picks"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _first(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _pct(value: Any, digits: int = 1) -> str:
    num = _as_float(value)
    if num is None:
        return "-"
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.{digits}f}%"


def _num(value: Any, digits: int = 2) -> str:
    num = _as_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _chips(items: Iterable[Any], cls: str = "chip") -> str:
    out: List[str] = []
    for item in list(items or [])[:10]:
        text = str(item or "").strip()
        if text:
            out.append(f'<span class="{cls}">{_esc(text)}</span>')
    return "".join(out)


def render_cloq_section(rows: List[Dict[str, Any]], title: str = "CloQ Close Odds") -> str:
    cards: List[str] = []
    for rank, row in enumerate(rows, 1):
        pick = _first(row, "pick", "cloq_pick", "player", "player1", "home") or "-"
        opponent = _first(row, "opponent", "opp", "player2", "away") or "-"
        tournament = _first(row, "tournament", "event_name", "competition") or ""
        start = _first(row, "start_time", "match_start", "match_time", "commence_time") or ""
        odds = _first(row, "pick_odds", "odds", "selected_odds")
        score = _first(row, "cloq_score")
        corq = _first(row, "cloq_corq_probability", "corq_probability", "corq_calibrated_probability")
        thinq = _first(row, "cloq_thinq_probability", "thinq_pick_probability", "thinq_probability")
        marq = _first(row, "cloq_marq_probability", "marq_crowd_pick_pct", "corq_market_probability")
        gap = _first(row, "cloq_odd_gap_pct", "odds_gap_pct")
        tags = row.get("cloq_tags") or []
        warnings = row.get("cloq_warnings") or []

        cards.append(f"""
        <article class="cloq-card">
          <div class="cloq-top"><span class="rank">#{rank}</span><span class="score">CloQ {_num(score, 1)}</span></div>
          <h2>{_esc(pick)} <span>vs</span> {_esc(opponent)}</h2>
          <div class="meta">{_date_time_pill(start)}<span class="cloq-meta">{_esc(tournament)}</span></div>
          <div class="metrics">
            <div><label>Odds</label><b>{_num(odds, 2)}</b></div>
            <div><label>Gap</label><b>{_pct(gap, 1)}</b></div>
            <div><label>CorQ</label><b>{_pct(corq, 1)}</b></div>
            <div><label>ThinQ</label><b>{_pct(thinq, 1)}</b></div>
            <div><label>MarQ</label><b>{_pct(marq, 1)}</b></div>
          </div>
          <div class="chips">{_chips(tags, 'chip tag')}{_chips(warnings, 'chip warn')}</div>
        </article>
        """)

    body = "\n".join(cards) if cards else '<div class="empty">No CloQ picks passed the current strict close-odds filter.</div>'
    return f"""
    <section class="cloq-section">
      <h1>{_esc(title)}</h1>
      <p class="subtitle">Separate Close Odds Quality shortlist. Uses CorQ/ThinQ/MarQ values as read-only inputs and does not affect CorQ ranking.</p>
      <div class="cloq-grid">{body}</div>
    </section>
    """


def page_shell(section_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CloQ</title>
  <style>
    :root{{--bg:#08111f;--panel:#111d2f;--line:#24344d;--text:#e5eefc;--muted:#8ea5c2;--cyan:#38d5ff;--green:#34d399;--orange:#fb923c;}}
    body{{margin:0;background:radial-gradient(circle at top left,#10233d 0,#08111f 42%,#050b14 100%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif;}}
    .wrap{{max-width:1440px;margin:0 auto;padding:18px;}}
    h1{{margin:0 0 4px;font-size:24px;color:#e0f2fe;}}
    .subtitle{{margin:0 0 18px;color:var(--muted);}}
    .cloq-grid{{display:grid;gap:14px;}}
    .cloq-card{{background:linear-gradient(180deg,#111f35,#0b1627);border:1px solid #2b405d;border-radius:20px;padding:14px;box-shadow:0 14px 30px rgba(0,0,0,.22);}}
    .cloq-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;}}
    .rank{{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:28px;border-radius:999px;background:#0b2740;border:1px solid #1f75aa;color:var(--cyan);font-weight:900;}}
    .score{{font-weight:900;color:var(--green);}}
    h2{{margin:0;font-size:18px;line-height:1.25;}}
    h2 span{{color:#67e8f9;font-size:11px;text-transform:uppercase;letter-spacing:.12em;margin:0 6px;}}
    .meta{{margin-top:6px;color:var(--muted);font-size:12px;}}
    .metrics{{display:grid;grid-template-columns:repeat(5,minmax(90px,1fr));gap:8px;margin-top:12px;}}
    .metrics div{{background:#0d1727;border:1px solid #24344d;border-radius:14px;padding:9px;}}
    .metrics label{{display:block;color:#8ea5c2;font-size:10px;text-transform:uppercase;font-weight:900;letter-spacing:.1em;}}
    .metrics b{{display:block;margin-top:3px;font-size:15px;color:#f8fafc;}}
    .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;}}
    .chip{{border-radius:999px;padding:4px 8px;font-size:11px;font-weight:850;border:1px solid #344a68;background:#16243a;color:#bcd1ea;}}
    .tag{{border-color:rgba(52,211,153,.55);background:rgba(6,50,34,.48);color:#bbf7d0;}}
    .warn{{border-color:rgba(251,146,60,.55);background:rgba(92,45,12,.48);color:#fed7aa;}}
    .empty{{padding:28px;text-align:center;color:#9fb5d1;border:1px dashed #334155;border-radius:18px;background:#0d1727;}}
    @media(max-width:760px){{.metrics{{grid-template-columns:1fr 1fr;}}}}
  .cloq-date-time{display:inline-flex;flex-direction:column;gap:1px;margin-right:8px;padding:3px 7px;border:1px solid #244766;border-radius:10px;background:#0f2036;color:#e0f2fe;font-weight:900;line-height:1.05}.cloq-date-time .cloq-date{font-size:10.5px;color:#bae6fd}.cloq-date-time .cloq-clock{font-size:13.5px;color:#f8fafc}.cloq-meta{color:#9fb5d1}</style>
</head><body><div class="wrap">{section_html}</div></body></html>"""


def _default_input(outputs_dir: Path) -> Path:
    primary = outputs_dir / "cloq" / "latest_cloq.json"
    if primary.exists():
        return primary
    return outputs_dir / "latest_cloq.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render CloQ HTML diagnostics page")
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument("--input", default=None, help="Optional explicit CloQ JSON input path")
    parser.add_argument("--out", default="outputs/cloq/index.html")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    input_path = Path(args.input) if args.input else _default_input(outputs_dir)
    rows = _load_rows(input_path)
    html_text = page_shell(render_cloq_section(rows))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
