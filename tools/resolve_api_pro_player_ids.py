from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_REGISTRY = Path('thinq/data/players/player_registry.json')
DEFAULT_OUTPUT = Path('thinq/data/players/api_pro_player_identities.json')
DEFAULT_ROOTS = ('outputs', 'runtime', 'data', 'thinq/data/cache', 'thinq/data/h2h')
EXCLUDED_NAMES = {
    'player_registry.json',
    'elo_player_universe.json',
    'tennis_name_alias_database.json',
    'api_pro_player_rankings.json',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or '').strip().lower())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '', text)


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, '', 0, '0'):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_name(value: Any) -> str:
    return ' '.join(str(value or '').replace('_', ' ').split())


def country_code(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get('alpha3') or value.get('alpha2') or value.get('code') or value.get('name')
    text = str(value or '').strip().upper()
    return text or None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def player_name(row: Dict[str, Any]) -> str:
    for key in ('display_name', 'canonical_name', 'name', 'player', 'player_name', 'fullName', 'shortName'):
        name = clean_name(row.get(key))
        if name:
            return name
    return ''


def player_id(row: Dict[str, Any]) -> Optional[int]:
    for key in ('api_team_id', 'rapidapi_id', 'player_id', 'team_id', 'teamId', 'playerId', 'id'):
        pid = as_int(row.get(key))
        if pid is not None:
            return pid
    return None


def extract_country(row: Dict[str, Any]) -> Optional[str]:
    for key in ('country_code', 'country_alpha3', 'country_alpha2', 'country', 'nationality'):
        value = country_code(row.get(key))
        if value:
            return value
    return None


def iter_registry_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get('players')
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(rows, dict):
        return [row for row in rows.values() if isinstance(row, dict)]
    return []


def iter_candidate_objects(value: Any, context: str = '') -> Iterable[Tuple[Dict[str, Any], str]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_candidate_objects(item, context)
        return
    if not isinstance(value, dict):
        return

    for key, item in value.items():
        lowered = str(key).lower()
        next_context = lowered or context
        if isinstance(item, dict) and lowered in {
            'hometeam', 'awayteam', 'home', 'away', 'player', 'team',
            'player1', 'player2', 'pick_player', 'opponent_player',
        }:
            yield item, next_context
        yield from iter_candidate_objects(item, next_context)

    # Explicit flattened match-side contracts used by CorQ/ThinQ outputs.
    flattened = (
        ('pick', ('pick_player_id', 'thinq_pick_player_id', 'pick_api_team_id'), ('pick', 'top7_pick', 'cloq_pick')),
        ('opponent', ('opponent_player_id', 'thinq_opponent_player_id', 'opponent_api_team_id'), ('opponent', 'opp')),
        ('home', ('home_id', 'home_player_id'), ('home_name',)),
        ('away', ('away_id', 'away_player_id'), ('away_name',)),
        ('player1', ('player1_id',), ('player1',)),
        ('player2', ('player2_id',), ('player2',)),
    )
    for side, id_keys, name_keys in flattened:
        pid = next((as_int(value.get(key)) for key in id_keys if as_int(value.get(key)) is not None), None)
        name = next((clean_name(value.get(key)) for key in name_keys if clean_name(value.get(key))), '')
        if pid is not None and name:
            yield {'id': pid, 'name': name, 'country': value.get(f'{side}_country')}, side


def source_files(roots: Iterable[str]) -> Iterable[Path]:
    seen = set()
    for root_text in roots:
        root = Path(root_text)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob('*.json')
        for path in paths:
            if path.name in EXCLUDED_NAMES or path in seen or not path.is_file():
                continue
            seen.add(path)
            yield path


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description='Resolve API PRO player IDs from real repository payloads')
    parser.add_argument('--registry', default=str(DEFAULT_REGISTRY))
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--roots', default=','.join(DEFAULT_ROOTS))
    args = parser.parse_args()

    registry_rows = iter_registry_rows(load_json(Path(args.registry)))
    universe = {normalize_name(player_name(row)): row for row in registry_rows if normalize_name(player_name(row))}

    candidates: Dict[str, Dict[int, Dict[str, Any]]] = {}
    files_scanned = objects_scanned = 0
    for path in source_files([part.strip() for part in args.roots.split(',') if part.strip()]):
        payload = load_json(path)
        if payload is None:
            continue
        files_scanned += 1
        for obj, context in iter_candidate_objects(payload):
            objects_scanned += 1
            pid = player_id(obj)
            name = player_name(obj)
            key = normalize_name(name)
            if pid is None or not key or key not in universe:
                continue
            country = extract_country(obj)
            entry = candidates.setdefault(key, {}).setdefault(pid, {
                'player_id': pid,
                'name': name,
                'country_code': country,
                'sources': [],
                'occurrences': 0,
            })
            entry['occurrences'] += 1
            if country and not entry.get('country_code'):
                entry['country_code'] = country
            if str(path) not in entry['sources']:
                entry['sources'].append(str(path))

    resolved: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    for key, row in sorted(universe.items()):
        existing = player_id(row)
        name = player_name(row)
        if existing is not None:
            resolved.append({
                'player_id': existing,
                'name': name,
                'country_code': extract_country(row),
                'status': 'EXISTING_ID',
                'sources': ['player_registry'],
            })
            continue
        options = candidates.get(key, {})
        if len(options) == 1:
            item = dict(next(iter(options.values())))
            item['name'] = name
            item['status'] = 'EXACT_NORMALIZED_NAME'
            resolved.append(item)
        elif len(options) > 1:
            ambiguous.append({
                'name': name,
                'status': 'AMBIGUOUS',
                'candidates': sorted(options.values(), key=lambda item: (-item['occurrences'], item['player_id'])),
            })
        else:
            unresolved.append({'name': name, 'status': 'NOT_FOUND'})

    payload = {
        'version': 'API_PRO_PLAYER_IDENTITIES_V1',
        'generated_at': now_iso(),
        'policy': 'real_payload_ids_exact_normalized_name_only_no_guesses',
        'stats': {
            'registry_players': len(universe),
            'files_scanned': files_scanned,
            'objects_scanned': objects_scanned,
            'resolved': len(resolved),
            'ambiguous': len(ambiguous),
            'unresolved': len(unresolved),
        },
        'players': resolved,
        'ambiguous': ambiguous,
        'unresolved': unresolved,
    }
    write_atomic(Path(args.output), payload)
    print(json.dumps(payload['stats'], indent=2))
    print(f'Identity cache written: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
