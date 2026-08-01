"""CloQ HTML renderer.

Can be imported by the main web renderer later, or run standalone to create
outputs/cloq.html for diagnostics.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    return []


def _fmt(value: Any, suffix: str = "") -> str:
    if value in (None, "", "—", "-"):
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{html.escape(str(value))}{suffix}"


def render_cloq_section(rows: List[Dict[str, Any]], title: str = "CloQ") -> str:
    cards = []
    for row in rows:
        pick = html.escape(str(row.get("pick") or "—"))
        opponent = html.escape(str(row.get("opponent") or "—"))
        tournament = html.escape(str(row.get("tournament") or ""))
        odds = _fmt(row.get("pick_odds") or row.get("odds"))
        score = _fmt(row.get("cloq_score"))
        corq = _fmt(row.get("cloq_corq_probability"), "%")
        thinq = _fmt(row.get("cloq_thinq_probability"), "%")
        marq = _fmt(row.get("cloq_marq_probability"), "%")
        gap = _fmt(row.get("cloq_odd_gap_pct"), "%")
        tags = row.get("cloq_tags") or []
        tag_html = "".join(f'<span class="cloq-tag">{html.escape(str(tag))}</span>' for tag in tags[:6])
        cards.append(f'''
        <article class="cloq-card">
          <div class="cloq-card-head">
            <div><strong>{pick}</strong><span> vs {opponent}</span></div>
            <div class="cloq-score">CloQ {score}</div>
          </div>
          <div class="cloq-meta">{tournament}</div>
          <div class="cloq-grid">
            <div><span>Odds</span><b>{odds}</b></div>
            <div><span>CorQ</span><b>{corq}</b></div>
            <div><span>ThinQ</span><b>{thinq}</b></div>
            <div><span>MarQ</span><b>{marq}</b></div>
            <div><span>Gap</span><b>{gap}</b></div>
          </div>
          <div class="cloq-tags">{tag_html}</div>
        </article>
        ''')
    body = "\n".join(cards) if cards else '<div class="cloq-empty">No CloQ rows available.</div>'
    css = '''
      <style>
        .cloq-section { padding: 18px; border: 1px solid #23405f; border-radius: 18px; background: #081726; color: #eaf6ff; }
        .cloq-section h2 { margin: 0 0 14px; color: #30d5ff; letter-spacing: .08em; text-transform: uppercase; font-size: 16px; }
        .cloq-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
        .cloq-card { border: 1px solid #274967; border-radius: 16px; background: #0d1c2e; padding: 12px; box-shadow: 0 8px 18px rgba(0,0,0,.22); }
        .cloq-card-head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
        .cloq-card-head strong { color: #fff; display: block; }
        .cloq-card-head span { color: #b6d6ef; font-size: 12px; }
        .cloq-score { color: #22e6a8; font-weight: 800; white-space: nowrap; }
        .cloq-meta { font-size: 11px; color: #9db6ca; margin: 6px 0 10px; min-height: 14px; }
        .cloq-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
        .cloq-grid div { background: #122843; border: 1px solid #2b5174; border-radius: 10px; padding: 6px; text-align: center; }
        .cloq-grid span { display: block; font-size: 10px; color: #8fb7d5; text-transform: uppercase; }
        .cloq-grid b { font-size: 12px; color: #fff; }
        .cloq-tags { display: flex; flex-wrap: wrap; margin-top: 10px; gap: 6px; }
        .cloq-tag { border: 1px solid #285c84; border-radius: 999px; padding: 4px 7px; font-size: 10px; background: #102944; color: #c8e8ff; }
        .cloq-empty { color: #aac7db; padding: 10px; }
      </style>
    '''
    return f'<section class="cloq-section">{css}<h2>{html.escape(title)}</h2><div class="cloq-cards">{body}</div></section>'


def main() -> int:
    parser = argparse.ArgumentParser(description="Render CloQ HTML section")
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument("--out", default="outputs/cloq.html")
    args = parser.parse_args()
    outputs_dir = Path(args.outputs_dir)
    rows = _load_rows(outputs_dir / "latest_cloq.json")
    html_text = render_cloq_section(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
