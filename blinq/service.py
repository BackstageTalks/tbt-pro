"""BlinQ orchestration over the canonical ThinQ model.

BlinQ does not implement a second prediction formula. It runs ThinQ in both
orientations and accepts a prediction only when the real A/B model runs are
complementary. Exact 50:50 always means NO_PREDICTION.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from thinq.service import ThinqService

REGISTRY_PATH = Path("thinq/data/players/player_registry.json")
TOLERANCE = 0.0001


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(row: Dict[str, Any]) -> str:
    return str(
        row.get("display_name")
        or row.get("canonical_name")
        or row.get("name")
        or row.get("player")
        or ""
    ).strip()


@lru_cache(maxsize=1)
def _registry() -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("players") if isinstance(payload, dict) else []
    if isinstance(rows, dict):
        rows = list(rows.values())
    index: Dict[str, Dict[str, Any]] = {}
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        name = _name(raw)
        if not name:
            continue
        row = dict(raw)
        row["player"] = name
        keys = [name, row.get("normalized_name"), row.get("compact_key")]
        keys.extend(row.get("aliases") if isinstance(row.get("aliases"), list) else [])
        for value in keys:
            key = _compact(value)
            if key:
                index.setdefault(key, row)
    return index


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    country = row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2")
    return {
        "player": row.get("player") or _name(row),
        "player_id": _int(row.get("api_team_id") or row.get("rapidapi_id") or row.get("player_id")),
        "country_code": str(country).upper() if country else None,
        "country_name": row.get("country_name") or row.get("country"),
        "rank": _int(row.get("rank") or row.get("api_rank")),
        "rank_points": _int(row.get("rank_points") or row.get("api_points")),
        "elo": _float(row.get("elo")),
        "hard_elo": _float(row.get("hard_elo")),
        "clay_elo": _float(row.get("clay_elo")),
        "grass_elo": _float(row.get("grass_elo")),
    }


def _layer(result: Dict[str, Any]) -> Dict[str, Any]:
    value = result.get("thinq_probability_layer") or result.get("probability_layer")
    return value if isinstance(value, dict) else {}



def _pair_index(value1: Any, value2: Any, *, samples1: int = 1, samples2: int = 1) -> Dict[str, Any]:
    """Return a real-data pair index. Missing samples stay unavailable, never 50:50."""
    first = _float(value1)
    second = _float(value2)
    if first is None or second is None or samples1 <= 0 or samples2 <= 0:
        return {"available": False, "p1": None, "p2": None}
    total = first + second
    if total <= 0:
        return {"available": False, "p1": None, "p2": None}
    p1 = round(first / total * 100.0, 1)
    return {"available": True, "p1": p1, "p2": round(100.0 - p1, 1)}


def _elo_index(elo: Dict[str, Any]) -> Dict[str, Any]:
    first = _float(elo.get("pick_elo"))
    second = _float(elo.get("opponent_elo"))
    if first is None or second is None:
        return {"available": False, "p1": None, "p2": None, "label": "S-index"}
    # Same neutral ELO scale as the model, exposed only as a 0-100 strength index.
    probability = 1.0 / (1.0 + 10.0 ** (-(first - second) / 400.0))
    p1 = round(probability * 100.0, 1)
    return {"available": True, "p1": p1, "p2": round(100.0 - p1, 1), "label": "S-index"}


def _window(form: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    player = form.get(side) if isinstance(form.get(side), dict) else {}
    value = player.get(key) if isinstance(player.get(key), dict) else {}
    return value


def _form_index(form: Dict[str, Any], key: str, prefix: str) -> Dict[str, Any]:
    first = _window(form, "pick", key)
    second = _window(form, "opponent", key)
    count1 = _int(first.get("count")) or 0
    count2 = _int(second.get("count")) or 0
    sample = min(count1, count2)
    index = _pair_index(first.get("win_pct"), second.get("win_pct"), samples1=count1, samples2=count2)
    index.update({"label": f"{prefix}{sample}-index" if sample > 0 else f"{prefix}-index", "sample": sample})
    return index


def _h2h_index(h2h: Dict[str, Any]) -> Dict[str, Any]:
    total = _int(h2h.get("total_matches")) or 0
    first = _int(h2h.get("pick_wins"))
    second = _int(h2h.get("opponent_wins"))
    index = _pair_index(first, second, samples1=total, samples2=total)
    index.update({"label": f"H{total}-index" if total > 0 else "H-index", "sample": total})
    return index


def _market_index(result: Dict[str, Any]) -> Dict[str, Any]:
    """Use market information only when an exact-event movement payload exists."""
    candidates = [result.get("marq"), result.get("market"), (result.get("contexts") or {}).get("marq")]
    for market in candidates:
        if not isinstance(market, dict):
            continue
        exact = market.get("exact_event") is True or str(market.get("match_status") or "").upper() == "EXACT"
        first = _float(market.get("player1_index") or market.get("pick_index"))
        second = _float(market.get("player2_index") or market.get("opponent_index"))
        if exact and first is not None and second is not None:
            index = _pair_index(first, second)
            index.update({"label": "M-index", "source": market.get("source")})
            return index
    return {"available": False, "p1": None, "p2": None, "label": "M-index"}


def _data_index(public: Dict[str, Any], elo: Dict[str, Any], form_window: Dict[str, Any], surface_window: Dict[str, Any], h2h_total: int) -> float:
    checks = [
        public.get("player_id") is not None,
        public.get("elo") is not None,
        elo.get("pick_elo") is not None,
        (_int(form_window.get("count")) or 0) >= 5,
        (_int(surface_window.get("count")) or 0) >= 3,
        h2h_total > 0,
        public.get("rank") is not None,
        bool(public.get("country_code")),
    ]
    return round(sum(1 for item in checks if item) / len(checks) * 100.0, 1)


def _build_indices(forward: Dict[str, Any], player1: Dict[str, Any], player2: Dict[str, Any]) -> Dict[str, Any]:
    elo = forward.get("elo") if isinstance(forward.get("elo"), dict) else {}
    form = forward.get("recent_form") if isinstance(forward.get("recent_form"), dict) else {}
    h2h = forward.get("h2h") if isinstance(forward.get("h2h"), dict) else {}
    p1_last10 = _window(form, "pick", "last10")
    p2_last10 = _window(form, "opponent", "last10")
    p1_surface = _window(form, "pick", "surface_last10")
    p2_surface = _window(form, "opponent", "surface_last10")
    h2h_total = _int(h2h.get("total_matches")) or 0
    return {
        "strength": _elo_index(elo),
        "form": _form_index(form, "last10", "F"),
        "court_form": _form_index(form, "surface_last10", "CF"),
        "h2h": _h2h_index(h2h),
        "market": _market_index(forward),
        "data": {
            "available": True,
            "p1": _data_index(player1, elo, p1_last10, p1_surface, h2h_total),
            "p2": _data_index(player2, {"pick_elo": elo.get("opponent_elo")}, p2_last10, p2_surface, h2h_total),
            "label": "D-index",
        },
    }

def _no_prediction(reason: str, flags: List[str], **extra: Any) -> Dict[str, Any]:
    return {
        "model": "BlinQ",
        "model_version": "BLINQ_THINQ_ORCHESTRATOR_V1",
        "status": "NO_PREDICTION",
        "prediction_status": "NO_PREDICTION",
        "winner": None,
        "winner_side": None,
        "winner_probability": 0.5,
        "player1_probability": 0.5,
        "player2_probability": 0.5,
        "reason": reason,
        "flags": sorted(set(flags)),
        **extra,
    }


class BlinqService:
    def __init__(self) -> None:
        self.thinq = ThinqService()

    def players(self) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for row in _registry().values():
            public = _public(row)
            if public["player"] and public["elo"] is not None:
                unique.setdefault(_compact(public["player"]), public)
        return sorted(unique.values(), key=lambda row: str(row["player"]).casefold())

    def _resolve(self, value: str) -> Optional[Dict[str, Any]]:
        return _registry().get(_compact(value))

    def _run(self, pick: Dict[str, Any], opponent: Dict[str, Any], surface: str) -> Dict[str, Any]:
        pick_public, opponent_public = _public(pick), _public(opponent)
        return self.thinq.build_match_features(
            player1=pick_public["player"],
            player2=opponent_public["player"],
            pick=pick_public["player"],
            opponent=opponent_public["player"],
            pick_side="HOME",
            opponent_side="AWAY",
            player1_id=pick_public["player_id"],
            player2_id=opponent_public["player_id"],
            surface=surface,
            level=None,
            best_of=3,
            save_snapshot=False,
        )

    def predict(self, player1: str, player2: str, surface: Optional[str] = None) -> Dict[str, Any]:
        if not str(player1 or "").strip() or not str(player2 or "").strip():
            return _no_prediction("Both players are required.", ["INVALID_INPUT"])
        if _compact(player1) == _compact(player2):
            return _no_prediction("Select two different players.", ["SAME_PLAYER"])

        row1, row2 = self._resolve(player1), self._resolve(player2)
        if row1 is None or row2 is None:
            missing = ([player1] if row1 is None else []) + ([player2] if row2 is None else [])
            return _no_prediction("Player not found in central registry.", ["PLAYER_NOT_FOUND"], missing_players=missing)

        surface_name = str(surface or "Overall")
        forward = self._run(row1, row2, surface_name)
        reverse = self._run(row2, row1, surface_name)
        layer_ab, layer_ba = _layer(forward), _layer(reverse)
        p_ab = _float(layer_ab.get("pick_probability"))
        p_ba = _float(layer_ba.get("pick_probability"))
        edge_ab = _float(layer_ab.get("edge"))
        edge_ba = _float(layer_ba.get("edge"))

        probability_ok = p_ab is not None and p_ba is not None and abs((p_ab + p_ba) - 1.0) <= TOLERANCE
        edge_ok = edge_ab is not None and edge_ba is not None and abs(edge_ab + edge_ba) <= TOLERANCE
        tie_ok = not (
            p_ab == 0.5
            and (layer_ab.get("prediction_status") != "NO_PREDICTION" or layer_ab.get("winner") is not None)
        )
        symmetry_ok = bool(probability_ok and edge_ok and tie_ok)

        audit = {
            "status": "PASS" if symmetry_ok else "FAIL",
            "probability_complement_ok": probability_ok,
            "edge_antisymmetry_ok": edge_ok,
            "tie_guard_ok": tie_ok,
            "probability_sum": round((p_ab or 0.0) + (p_ba or 0.0), 8),
            "edge_sum": round((edge_ab or 0.0) + (edge_ba or 0.0), 8),
            "tolerance": TOLERANCE,
        }

        indices = _build_indices(forward, _public(row1), _public(row2))
        blocked = (
            not symmetry_ok
            or p_ab is None
            or p_ba is None
            or layer_ab.get("prediction_status") == "NO_PREDICTION"
            or p_ab == 0.5
        )
        if blocked:
            flags = list(layer_ab.get("flags") or [])
            if not symmetry_ok:
                flags.append("BLINQ_REAL_AB_SYMMETRY_FAILED")
            return _no_prediction(
                "ThinQ data is insufficient, tied, or failed the real A/B audit.",
                flags,
                player1=_public(row1),
                player2=_public(row2),
                surface=surface_name,
                symmetry_audit=audit,
                thinq_forward=forward,
                thinq_reverse=reverse,
                indices=indices,
            )

        winner_is_p1 = p_ab > 0.5
        return {
            "model": "BlinQ",
            "model_version": "BLINQ_THINQ_ORCHESTRATOR_V1",
            "status": "PREDICTION",
            "prediction_status": "PREDICTION",
            "surface": surface_name,
            "player1": _public(row1),
            "player2": _public(row2),
            "player1_probability": round(p_ab, 4),
            "player2_probability": round(1.0 - p_ab, 4),
            "winner": _public(row1)["player"] if winner_is_p1 else _public(row2)["player"],
            "winner_side": "PLAYER1" if winner_is_p1 else "PLAYER2",
            "winner_probability": round(max(p_ab, 1.0 - p_ab), 4),
            "confidence": layer_ab.get("confidence"),
            "edge": edge_ab,
            "components": layer_ab.get("components") or {},
            "h2h": forward.get("h2h") or {},
            "recent_form": forward.get("recent_form") or {},
            "elo": forward.get("elo") or {},
            "flags": sorted(set(layer_ab.get("flags") or [])),
            "symmetry_audit": audit,
            "indices": indices,
        }
