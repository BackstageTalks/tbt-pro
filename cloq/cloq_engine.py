"""CloQ engine: builds outputs/latest_cloq.json from enriched CorQ rows."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from cloq.filters import CloQConfig, apply_cloq
except Exception:
    from filters import CloQConfig, apply_cloq


def _load_json(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _as_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ('rows', 'picks', 'data', 'items'):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def build_cloq(input_path: Path = Path('outputs/latest_all.json'), output_path: Path = Path('outputs/latest_cloq.json'), diagnostics_path: Path = Path('outputs/latest_cloq_diagnostics.json'), config: CloQConfig = CloQConfig()) -> Dict[str, Any]:
    rows = _as_rows(_load_json(input_path))
    enriched = apply_cloq(rows, config=config)
    selected = [r for r in enriched if r.get('cloq_passed')][:config.max_rows]
    reject_counts: Dict[str, int] = {}
    warning_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    for row in enriched:
        for reason in row.get('cloq_reject_reasons') or []:
            reject_counts[reason] = reject_counts.get(reason, 0) + 1
        for warning in row.get('cloq_warnings') or []:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
        for tag in row.get('cloq_tags') or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    generated_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        'generated_at_utc': generated_at,
        'source_file': str(input_path),
        'row_count': len(rows),
        'enriched_count': len(enriched),
        'selected_count': len(selected),
        'config': config.to_dict(),
        'reject_counts': dict(sorted(reject_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        'warning_counts': dict(sorted(warning_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        'tag_counts': dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    payload = {
        'generated_at_utc': generated_at,
        'model': 'CloQ',
        'description': 'Close Odds Quality candidates built from enriched CorQ rows.',
        'metadata': metadata,
        'rows': selected,
    }
    _write_json(output_path, payload)
    _write_json(diagnostics_path, {'metadata': metadata, 'rows': enriched})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description='Build CloQ close-odds candidates')
    parser.add_argument('--input', default='outputs/latest_all.json')
    parser.add_argument('--output', default='outputs/latest_cloq.json')
    parser.add_argument('--diagnostics', default='outputs/latest_cloq_diagnostics.json')
    parser.add_argument('--min-odds', type=float, default=1.70)
    parser.add_argument('--max-odds', type=float, default=2.60)
    parser.add_argument('--min-gap', type=float, default=0.10)
    parser.add_argument('--max-gap', type=float, default=0.25)
    parser.add_argument('--min-corq', type=float, default=0.55)
    parser.add_argument('--min-thinq', type=float, default=0.55)
    parser.add_argument('--min-marq', type=float, default=0.50)
    parser.add_argument('--min-form-depth', type=float, default=0.60)
    parser.add_argument('--min-stats-depth', type=float, default=0.40)
    parser.add_argument('--max-mm-gap-pp', type=float, default=18.0)
    parser.add_argument('--max-rows', type=int, default=20)
    args = parser.parse_args()
    cfg = CloQConfig(
        min_odds=args.min_odds,
        max_odds=args.max_odds,
        min_odd_gap_pct=args.min_gap,
        max_odd_gap_pct=args.max_gap,
        min_corq_probability=args.min_corq,
        min_thinq_probability=args.min_thinq,
        min_marq_probability=args.min_marq,
        min_form_depth=args.min_form_depth,
        min_stats_depth=args.min_stats_depth,
        max_model_market_gap_pp=args.max_mm_gap_pp,
        max_rows=args.max_rows,
    )
    payload = build_cloq(Path(args.input), Path(args.output), Path(args.diagnostics), cfg)
    print(json.dumps(payload.get('metadata', {}), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
