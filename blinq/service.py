"""BlinQ service backed by the existing ThinQ TA ELO cache."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from blinq.model import symmetry_audit
import json
from pathlib import Path
from thinq.loaders.elo_loader import find_player


REGISTRY_PATH = Path("thinq/data/players/player_registry.json")

def _registry_players() -> List[Dict[str, Any]]:
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        rows = data.get("players", []) if isinstance(data, dict) else []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        return []

class BlinqService:
    def players(self) -> List[Dict[str, Any]]:
        out = []
        for row in _registry_players():
            name = str(row.get("display_name") or row.get("canonical_name") or row.get("name") or "").strip()
            if not name or row.get("elo") is None:
                continue
            country = row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2")
            out.append({
                "player": name,
                "country_code": str(country).upper() if country else None,
                "country_name": row.get("country_name") or row.get("country"),
                "rank": row.get("rank") or row.get("api_rank"),
                "rank_points": row.get("rank_points") or row.get("api_points"),
                "elo": row.get("elo"),
                "hard_elo": row.get("hard_elo"),
                "clay_elo": row.get("clay_elo"),
                "grass_elo": row.get("grass_elo"),
            })
        return sorted(out, key=lambda row: str(row.get("player") or "").casefold())

    def predict(self, player1: str, player2: str, surface: Optional[str] = None) -> Dict[str, Any]:
        if not str(player1 or "").strip() or not str(player2 or "").strip():
            return {"status": "INVALID_INPUT", "reason": "Both players are required."}
        if str(player1).strip().casefold() == str(player2).strip().casefold():
            return {"status": "INVALID_INPUT", "reason": "Select two different players."}
        row1, row2 = find_player(player1), find_player(player2)
        if row1 is None or row2 is None:
            missing = ([player1] if row1 is None else []) + ([player2] if row2 is None else [])
            return {"status": "NO_DATA", "reason": "ELO record not found.", "missing_players": missing}
        audit = symmetry_audit(row1, row2, surface)
        result = dict(audit["forward"])
        result["symmetry_ok"] = audit["ok"]
        result["symmetry_error"] = audit["error"]
        if audit["ok"] is False:
            result.update({"status": "NO_PREDICTION", "winner": None, "winner_side": None})
            result["flags"] = sorted(set(result.get("flags", []) + ["SYMMETRY_AUDIT_FAILED"]))
        return result
