# THINQ service - clean intelligence layer for CORQ runtime
from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _norm_name(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return ' '.join(text.split())


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except Exception:
        return None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _surface_bucket(surface: Any) -> Tuple[str, str, list]:
    raw = str(surface or '').strip()
    text = raw.lower()
    flags = []
    if 'clay' in text:
        return 'Clay', 'clay_elo', flags
    if 'grass' in text:
        return 'Grass', 'grass_elo', flags
    if 'carpet' in text:
        flags.append('CARPET_AS_HARD_FALLBACK')
        return 'Carpet', 'hard_elo', flags
    if 'hard' in text:
        return 'Hard', 'hard_elo', flags
    return 'Unknown', 'elo', ['UNKNOWN_SURFACE']


class ThinqService:
    """THINQ = intelligence layer.

    The service is intentionally fail-safe. It must return a usable object even
    when H2H/API/history are unavailable. CORQ can then decide eligibility.
    """

    def __init__(self, elo_cache_path: str = 'thinq/data/elo/elo_cache.json') -> None:
        self.elo_cache_path = Path(elo_cache_path)
        self._elo_cache = None
        self._elo_loader = None
        self._h2h_loader = None
        self._surface_loader = None

    # ---------- public API ----------
    def build(self, match: Dict[str, Any], pick: Optional[str] = None) -> Dict[str, Any]:
        player1 = match.get('player1') or match.get('home') or match.get('homeTeam')
        player2 = match.get('player2') or match.get('away') or match.get('awayTeam')
        pick = pick or match.get('pick') or player1
        opponent = player2 if self._same_player(pick, player1) else player1

        result: Dict[str, Any] = {
            'available': True,
            'error': None,
            'confidence': 0.0,
            'surface': {},
            'elo': {},
            'h2h': {},
            'edges': {},
            'flags': [],
        }

        # Surface. Prefer already normalized match surface. Optional loader may enrich it.
        surface_info = self._resolve_surface(match)
        result['surface'] = surface_info
        selected_elo_type = surface_info.get('selected_elo_type') or 'elo'
        result['flags'].extend(surface_info.get('flags') or [])

        # ELO / yELO.
        elo_info = self._build_elo(player1, player2, pick, selected_elo_type)
        result['elo'] = elo_info
        if elo_info.get('status') != 'OK':
            result['flags'].append('MISSING_ELO')

        # H2H.
        h2h_info = self._build_h2h(match, player1, player2, pick, surface_info.get('surface'))
        result['h2h'] = h2h_info
        if h2h_info.get('status') != 'AVAILABLE':
            result['flags'].append('NO_H2H_DATA')

        edges = {
            'elo_edge': _as_float(elo_info.get('elo_edge')) or 0.0,
            'h2h_edge': _as_float(h2h_info.get('edge')) or 0.0,
        }
        result['edges'] = edges

        confidence = 0.15
        if elo_info.get('status') == 'OK':
            confidence += 0.45
        if surface_info.get('surface') and surface_info.get('surface') != 'Unknown':
            confidence += 0.15
        if h2h_info.get('status') == 'AVAILABLE':
            confidence += min(0.20, float(h2h_info.get('confidence') or 0.0) * 0.20)
        if 'CARPET_AS_HARD_FALLBACK' in result['flags']:
            confidence -= 0.05
        if 'UNKNOWN_SURFACE' in result['flags']:
            confidence -= 0.10
        result['confidence'] = round(_clamp(confidence, 0.0, 1.0), 4)

        # Flatten common fields for web/CORQ convenience.
        result.update({
            'thinq_available': True,
            'thinq_confidence': result['confidence'],
            'thinq_selected_elo_type': selected_elo_type,
            'thinq_elo_pick': elo_info.get('pick_elo'),
            'thinq_elo_opponent': elo_info.get('opponent_elo'),
            'thinq_yelo_pick': elo_info.get('pick_yelo'),
            'thinq_yelo_opponent': elo_info.get('opponent_yelo'),
            'thinq_elo_edge': edges['elo_edge'],
            'thinq_h2h_status': h2h_info.get('status'),
            'thinq_h2h_source': h2h_info.get('source'),
            'thinq_h2h_total_matches': h2h_info.get('total_matches'),
            'thinq_h2h_edge': edges['h2h_edge'],
            'thinq_h2h_confidence': h2h_info.get('confidence'),
            'thinq_flags': result['flags'],
        })
        return result

    # Compatibility aliases used by older glue code.
    def build_match_features(self, **kwargs: Any) -> Dict[str, Any]:
        match = dict(kwargs)
        return self.build(match=match, pick=kwargs.get('pick'))

    # ---------- internals ----------
    def _resolve_surface(self, match: Dict[str, Any]) -> Dict[str, Any]:
        surface_raw = match.get('surface_raw') or match.get('surface') or match.get('court') or match.get('surfaceType')
        source = match.get('surface_source') or 'match_payload'

        # If a surface loader exists and has tournament_id, try it but never fail.
        tournament_id = match.get('tournament_id') or match.get('tournamentId') or match.get('uniqueTournamentId')
        if tournament_id:
            try:
                if self._surface_loader is None:
                    from thinq.loaders.surface_loader import SurfaceLoader  # type: ignore
                    self._surface_loader = SurfaceLoader()
                info = self._surface_loader.resolve_surface(match)
                if info and info.get('surface') and info.get('surface') != 'Unknown':
                    return {
                        'surface': info.get('surface'),
                        'surface_raw': info.get('surface_raw') or surface_raw,
                        'surface_environment': info.get('surface_environment'),
                        'surface_model_bucket': info.get('surface_model_bucket') or info.get('surface'),
                        'surface_source': info.get('surface_source') or 'tennisapi_tournament_info',
                        'surface_confidence': info.get('surface_confidence') or 'HIGH',
                        'selected_elo_type': info.get('thinq_selected_elo_type') or info.get('selected_elo_type'),
                        'flags': info.get('surface_flags') or info.get('flags') or [],
                    }
            except Exception:
                pass

        surface, elo_type, flags = _surface_bucket(surface_raw)
        return {
            'surface': surface,
            'surface_raw': surface_raw,
            'surface_environment': match.get('surface_environment'),
            'surface_model_bucket': 'Hard' if surface == 'Carpet' else surface,
            'surface_source': source,
            'surface_confidence': 'LOW' if surface == 'Unknown' else 'MEDIUM',
            'selected_elo_type': elo_type,
            'flags': flags,
        }

    def _load_elo_cache(self) -> Dict[str, Any]:
        if self._elo_cache is not None:
            return self._elo_cache
        if self.elo_cache_path.exists():
            try:
                data = json.loads(self.elo_cache_path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    # Common formats: {"players": {...}} or flat map.
                    self._elo_cache = data.get('players') if isinstance(data.get('players'), dict) else data
                    return self._elo_cache or {}
            except Exception:
                pass
        self._elo_cache = {}
        return self._elo_cache

    def _lookup_elo(self, name: Any) -> Dict[str, Any]:
        n = _norm_name(name)
        cache = self._load_elo_cache()
        if n in cache and isinstance(cache[n], dict):
            return cache[n]
        for key, value in cache.items():
            if _norm_name(key) == n and isinstance(value, dict):
                return value
        # Try existing loader APIs if available.
        try:
            if self._elo_loader is None:
                from thinq.loaders.elo_loader import EloLoader  # type: ignore
                self._elo_loader = EloLoader()
            loader = self._elo_loader
            for method_name in ('get_player_elo', 'load_player_elo', 'lookup_player', 'get_player', 'load_elo'):
                method = getattr(loader, method_name, None)
                if callable(method):
                    try:
                        res = method(name)
                        if isinstance(res, dict):
                            return res
                    except TypeError:
                        try:
                            res = method(player=name)
                            if isinstance(res, dict):
                                return res
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pass
        return {}

    def _build_elo(self, player1: Any, player2: Any, pick: Any, selected_elo_type: str) -> Dict[str, Any]:
        p1 = self._lookup_elo(player1)
        p2 = self._lookup_elo(player2)
        pick_is_p1 = self._same_player(pick, player1)
        pick_data = p1 if pick_is_p1 else p2
        opp_data = p2 if pick_is_p1 else p1

        def get_elo(d: Dict[str, Any], key: str) -> Optional[float]:
            aliases = {
                'elo': ('elo', 'overall_elo', 'rating'),
                'hard_elo': ('hard_elo', 'hElo', 'h_elo'),
                'clay_elo': ('clay_elo', 'cElo', 'c_elo'),
                'grass_elo': ('grass_elo', 'gElo', 'g_elo'),
            }
            for k in aliases.get(key, (key,)):
                val = _as_float(d.get(k))
                if val is not None:
                    return val
            return None

        pick_elo = get_elo(pick_data, selected_elo_type) or get_elo(pick_data, 'elo')
        opp_elo = get_elo(opp_data, selected_elo_type) or get_elo(opp_data, 'elo')
        pick_yelo = _as_float(pick_data.get('season_yelo') or pick_data.get('yelo') or pick_data.get('Yelo'))
        opp_yelo = _as_float(opp_data.get('season_yelo') or opp_data.get('yelo') or opp_data.get('Yelo'))

        if pick_elo is None or opp_elo is None:
            return {'status': 'NO_DATA', 'selected_elo_type': selected_elo_type, 'elo_edge': 0.0}

        diff = pick_elo - opp_elo
        # Convert Elo diff into conservative probability edge. 400 Elo = 0.25 cap area, then capped.
        edge = _clamp(diff / 1600.0, -0.08, 0.08)
        # Small yELO trend bonus if both available.
        if pick_yelo is not None and opp_yelo is not None:
            edge += _clamp((pick_yelo - opp_yelo) / 4000.0, -0.015, 0.015)
        edge = _clamp(edge, -0.09, 0.09)
        return {
            'status': 'OK',
            'selected_elo_type': selected_elo_type,
            'pick_elo': round(pick_elo, 2),
            'opponent_elo': round(opp_elo, 2),
            'pick_yelo': round(pick_yelo, 2) if pick_yelo is not None else None,
            'opponent_yelo': round(opp_yelo, 2) if opp_yelo is not None else None,
            'elo_diff': round(diff, 2),
            'elo_edge': round(edge, 4),
            'source': 'tennisabstract_cache',
        }

    def _build_h2h(self, match: Dict[str, Any], player1: Any, player2: Any, pick: Any, surface: Any) -> Dict[str, Any]:
        try:
            if self._h2h_loader is None:
                from thinq.loaders.h2h_loader import H2HLoader  # type: ignore
                self._h2h_loader = H2HLoader()
            loader = self._h2h_loader
            result = loader.load_h2h(
                player1=player1,
                player2=player2,
                pick=pick,
                surface=surface,
                event_id=match.get('event_id') or match.get('eventId'),
                player1_id=match.get('player1_id'),
                player2_id=match.get('player2_id'),
                tournament_id=match.get('tournament_id') or match.get('tournamentId'),
            )
            if isinstance(result, dict):
                status = result.get('status') or result.get('h2h_status') or ('AVAILABLE' if (result.get('total_matches') or result.get('h2h_total_matches')) else 'NO_DATA')
                edge = _as_float(result.get('edge') or result.get('h2h_edge') or result.get('thinq_h2h_pct')) or 0.0
                if abs(edge) > 1:
                    edge = edge / 100.0
                return {
                    'status': status,
                    'source': result.get('source') or result.get('h2h_source') or 'unknown',
                    'total_matches': int(result.get('total_matches') or result.get('h2h_total_matches') or 0),
                    'pick_wins': int(result.get('pick_wins') or result.get('h2h_pick_wins') or 0),
                    'opponent_wins': int(result.get('opponent_wins') or result.get('h2h_opponent_wins') or 0),
                    'edge': round(_clamp(edge, -0.04, 0.04), 4),
                    'confidence': _clamp(float(result.get('confidence') or result.get('h2h_confidence') or 0.0), 0.0, 1.0),
                    'reason': result.get('reason') or result.get('h2h_reason') or '',
                }
        except Exception as exc:
            return {'status': 'ERROR_NON_BLOCKING', 'source': 'thinq_h2h_loader', 'total_matches': 0, 'edge': 0.0, 'confidence': 0.0, 'reason': str(exc)}
        return {'status': 'NO_DATA', 'source': 'none', 'total_matches': 0, 'edge': 0.0, 'confidence': 0.0, 'reason': 'No H2H data'}

    def _same_player(self, a: Any, b: Any) -> bool:
        na, nb = _norm_name(a), _norm_name(b)
        return bool(na and nb and (na == nb or na in nb or nb in na))
