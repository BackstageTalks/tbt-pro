"""Standalone CloQ HTML renderer."""
from __future__ import annotations
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _safe(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    text = str(value)
    if not text or text.lower() in {'none', 'nan', 'null'}:
        return default
    return html.escape(text)


def _pct(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    try:
        number = float(value)
    except Exception:
        return default
    if number <= 1.0:
        number *= 100.0
    return f'{number:.1f}%'


def _pp(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    try:
        number = float(value)
    except Exception:
        return default
    sign = '+' if number > 0 else ''
    return f'{sign}{number:.1f}pp'


def _odds(value: Any, default: str = '-') -> str:
    try:
        return f'{float(value):.2f}'
    except Exception:
        return default


def _row_values(row: Dict[str, Any]) -> Dict[str, Any]:
    values = row.get('cloq_values')
    return values if isinstance(values, dict) else {}


def render_cloq_cards(rows: Iterable[Dict[str, Any]]) -> str:
    cards: List[str] = []
    for row in rows:
        values = _row_values(row)
        tags = row.get('cloq_tags') or []
        warnings = row.get('cloq_warnings') or []
        title = _safe(row.get('pick')) + ' vs ' + _safe(row.get('opponent'))
        tags_html = ''.join('<span class="chip">' + _safe(tag) + '</span>' for tag in tags[:6])
        warn_html = ''.join('<span class="chip warn">' + _safe(w) + '</span>' for w in warnings[:3])
        card = '''<article class="cloq-card">
  <div class="cloq-card-head">
    <div>
      <div class="cloq-title">{title}</div>
      <div class="cloq-sub">{tournament} | {surface} | {level}</div>
    </div>
    <div class="cloq-score">{score}</div>
  </div>
  <div class="cloq-grid">
    <div><b>Odds</b><span>{odds}</span></div>
    <div><b>Gap</b><span>{gap}</span></div>
    <div><b>CorQ</b><span>{corq}</span></div>
    <div><b>ThinQ</b><span>{thinq}</span></div>
    <div><b>MarQ</b><span>{marq}</span></div>
    <div><b>CLV</b><span>{clv}</span></div>
  </div>
  <div class="cloq-tags">{tags}{warnings}</div>
</article>'''.format(
            title=title,
            tournament=_safe(row.get('tournament')),
            surface=_safe(row.get('surface')),
            level=_safe(row.get('level') or row.get('category')),
            score=_safe(row.get('cloq_score')),
            odds=_odds(values.get('odds') or row.get('pick_odds') or row.get('odds')),
            gap=_pct(values.get('odd_gap_pct')),
            corq=_pct(values.get('corq_probability')),
            thinq=_pct(values.get('thinq_probability')),
            marq=_pct(values.get('marq_probability')),
            clv=_pp(values.get('clv_pp')),
            tags=tags_html,
            warnings=warn_html,
        )
        cards.append(card)
    return '\n'.join(cards)


def render_cloq_page(payload: Dict[str, Any]) -> str:
    rows = payload.get('rows') if isinstance(payload, dict) else []
    metadata = payload.get('metadata') if isinstance(payload, dict) else {}
    body = render_cloq_cards(rows)
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CloQ</title>
<style>
body{margin:0;background:#071525;color:#eaf6ff;font-family:Inter,Arial,sans-serif}.wrap{max-width:1400px;margin:0 auto;padding:24px}.h1{font-size:24px;font-weight:800;color:#36d7ff;margin-bottom:4px}.meta{color:#a7bfd2;margin-bottom:18px}.cloq-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.cloq-card{border:1px solid #24405d;background:#0b1a2c;border-radius:18px;padding:14px;box-shadow:0 8px 20px rgba(0,0,0,.22)}.cloq-card-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.cloq-title{font-weight:800;font-size:15px}.cloq-sub{font-size:12px;color:#9bb7ce;margin-top:4px}.cloq-score{background:#0e7f5f;color:white;border:1px solid #15c48f;border-radius:999px;padding:6px 10px;font-weight:800}.cloq-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}.cloq-grid div{background:#132741;border:1px solid #274766;border-radius:12px;padding:8px}.cloq-grid b{display:block;font-size:10px;color:#78b7ff;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}.cloq-grid span{font-size:13px;font-weight:800}.chip{display:inline-block;background:#173055;border:1px solid #34638e;color:#dff3ff;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:700;margin:2px}.chip.warn{background:#4c2730;border-color:#8e4656;color:#fff0f3}
</style></head><body><div class="wrap"><div class="h1">CloQ - Close Odds Quality</div><div class="meta">Generated {generated} | selected {selected} of {total} rows</div><section class="cloq-list">{body}</section></div></body></html>'''.format(
        generated=_safe(payload.get('generated_at_utc')),
        selected=_safe(metadata.get('selected_count')),
        total=_safe(metadata.get('row_count')),
        body=body,
    )


def render_file(input_path: Path = Path('outputs/latest_cloq.json'), output_path: Path = Path('corq/site/cloq.html')) -> None:
    if input_path.exists():
        payload = json.loads(input_path.read_text(encoding='utf-8'))
    else:
        payload = {'generated_at_utc': '', 'metadata': {'selected_count': 0, 'row_count': 0}, 'rows': []}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cloq_page(payload), encoding='utf-8')


if __name__ == '__main__':
    render_file()
