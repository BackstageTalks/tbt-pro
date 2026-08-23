"""BlinQ service using the central player registry and ThinQ ELO model."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from blinq.model import symmetry_audit
from thinq.loaders.elo_loader import find_player

REGISTRY_PATH = Path("thinq/data/players/player_registry.json")


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def _integer(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        result = int(float(value))
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> Optional[float]:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _registry_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    players = payload.get("players")
    if isinstance(players, list):
        return [dict(row) for row in players if isinstance(row, dict)]
    if isinstance(players, dict):
        return [dict(row) for row in players.values() if isinstance(row, dict)]
    return []


@lru_cache(maxsize=1)
def _registry_index() -> Dict[str, Dict[str, Any]]:
    if not REGISTRY_PATH.is_file():
        return {}
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    index: Dict[str, Dict[str, Any]] = {}
    for row in _registry_rows(payload):
        name = str(row.get("display_name") or row.get("canonical_name") or row.get("name") or "").strip()
        if not name:
            continue
        row["player"] = name
        for candidate in [name, row.get("normalized_name"), *(row.get("aliases") or [])]:
            key = _compact(candidate)
            if key:
                index.setdefault(key, row)
    return index


def _public_player(row: Dict[str, Any]) -> Dict[str, Any]:
    country = str(row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2") or "").upper().strip()
    return {
        "player": row.get("player"),
        "player_id": row.get("api_team_id") or row.get("rapidapi_id") or row.get("player_id"),
        "tour": row.get("tour"),
        "country_code": country or None,
        "country_name": row.get("country_name") or row.get("country"),
        "rank": _integer(row.get("rank") or row.get("api_rank")),
        "rank_points": _integer(row.get("rank_points") or row.get("api_points")),
        "elo": _number(row.get("elo")),
        "hard_elo": _number(row.get("hard_elo")),
        "clay_elo": _number(row.get("clay_elo")),
        "grass_elo": _number(row.get("grass_elo")),
    }


class BlinqService:
    def players(self) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for row in _registry_index().values():
            public = _public_player(row)
            name = str(public.get("player") or "").strip()
            if name and public.get("elo") is not None:
                unique.setdefault(_compact(name), public)
        return sorted(unique.values(), key=lambda row: str(row.get("player") or "").casefold())

    def predict(self, player1: str, player2: str, surface: Optional[str] = None) -> Dict[str, Any]:
        key1, key2 = _compact(player1), _compact(player2)
        if not key1 or not key2:
            return {"status": "INVALID_INPUT", "reason": "Both players are required."}
        if key1 == key2:
            return {"status": "INVALID_INPUT", "reason": "Select two different players."}

        registry1 = _registry_index().get(key1)
        registry2 = _registry_index().get(key2)
        elo1 = find_player(str((registry1 or {}).get("player") or player1))
        elo2 = find_player(str((registry2 or {}).get("player") or player2))
        if elo1 is None or elo2 is None:
            missing = ([player1] if elo1 is None else []) + ([player2] if elo2 is None else [])
            return {"status": "NO_DATA", "reason": "ELO record not found.", "missing_players": missing}

        audit = symmetry_audit(elo1, elo2, surface)
        result = dict(audit["forward"])
        result["symmetry_ok"] = audit["ok"]
        result["symmetry_error"] = audit["error"]
        result["player1_profile"] = _public_player(registry1 or {"player": player1})
        result["player2_profile"] = _public_player(registry2 or {"player": player2})
        if audit["ok"] is False:
            result.update({"status": "NO_PREDICTION", "winner": None, "winner_side": None})
            result["flags"] = sorted(set(result.get("flags", []) + ["SYMMETRY_AUDIT_FAILED"]))
        return result
