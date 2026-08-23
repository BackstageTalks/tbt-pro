"""BlinQ service backed by the existing ThinQ TA ELO cache."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from blinq.model import symmetry_audit
from thinq.loaders.elo_loader import find_player, load_elo_index


class BlinqService:
    def players(self) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for row in load_elo_index().values():
            name = str(row.get("player") or "").strip()
            if name:
                unique.setdefault(str(row.get("compact_key") or name.casefold()), row)
        return sorted(unique.values(), key=lambda row: str(row.get("player") or "").casefold())

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
