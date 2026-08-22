"""
THINQ Data Aggregator - robust/fail-safe version.

Rules:
- CORQ must never call data sources directly.
- H2H is only a THINQ layer.
- Any THINQ sub-layer failure is non-blocking and becomes a status/flag in the output.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional, Tuple


def _import_class(module_names, class_name: str) -> Tuple[Any, Optional[str]]:
    errors = []
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name), None
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")
    return None, " | ".join(errors)


SackmannLoader, SACKMANN_IMPORT_ERROR = _import_class(
    ["thinq.loaders.sackmann_loader", ".sackmann_loader"], "SackmannLoader"
)
EloLoader, ELO_IMPORT_ERROR = _import_class(
    ["thinq.loaders.elo_loader", ".elo_loader"], "EloLoader"
)
TALoader, TA_IMPORT_ERROR = _import_class(
    ["thinq.loaders.ta_loader", ".ta_loader"], "TALoader"
)
H2HLoader, H2H_IMPORT_ERROR = _import_class(
    ["thinq.loaders.h2h_loader", ".h2h_loader"], "H2HLoader"
)
PlayerResolver, PLAYER_RESOLVER_IMPORT_ERROR = _import_class(
    ["thinq.loaders.player_resolver", ".player_resolver"], "PlayerResolver"
)


class _NullResolver:
    def resolve(self, player_name: str, tour: Optional[str] = None) -> Dict[str, Any]:
        return {
            "canonical_name": player_name,
            "input_name": player_name,
            "tour": tour,
            "resolver_status": "FALLBACK_IDENTITY",
        }


class _NullLayer:
    def __init__(self, layer_name: str, import_error: Optional[str] = None) -> None:
        self.layer_name = layer_name
        self.import_error = import_error

    def load_player(self, **kwargs) -> Dict[str, Any]:
        return {
            "status": "NO_DATA",
            "layer": self.layer_name,
            "reason": self.import_error or "Layer unavailable",
            "flags": [f"{self.layer_name.upper()}_UNAVAILABLE"],
        }

    def load_h2h(self, player1: str, player2: str, surface: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        return build_empty_h2h(player1, player2, surface, self.import_error or "H2H layer unavailable")


def build_empty_h2h(player1: Any, player2: Any, surface: Optional[str], reason: str) -> Dict[str, Any]:
    return {
        "player1": player1,
        "player2": player2,
        "surface": surface,
        "h2h_status": "NO_DATA",
        "h2h_source": "none",
        "source": "none",
        "h2h_total_matches": 0,
        "h2h_player1_wins": 0,
        "h2h_player2_wins": 0,
        "h2h_surface_matches": 0,
        "h2h_surface_player1_wins": 0,
        "h2h_surface_player2_wins": 0,
        "h2h_edge": 0.0,
        "h2h_confidence": 0.0,
        "h2h_reason": reason,
        "flags": ["H2H_NO_DATA"],
    }


class ThinqLoader:
    """Aggregates THINQ source layers without allowing one broken layer to kill THINQ."""

    def __init__(
        self,
        sackmann_loader: Optional[Any] = None,
        elo_loader: Optional[Any] = None,
        ta_loader: Optional[Any] = None,
        h2h_loader: Optional[Any] = None,
        player_resolver: Optional[Any] = None,
    ) -> None:
        self.import_errors: Dict[str, Optional[str]] = {
            "history": SACKMANN_IMPORT_ERROR,
            "elo": ELO_IMPORT_ERROR,
            "ta": TA_IMPORT_ERROR,
            "h2h": H2H_IMPORT_ERROR,
            "player_resolver": PLAYER_RESOLVER_IMPORT_ERROR,
        }
        self.resolver = player_resolver or self._safe_construct(PlayerResolver, _NullResolver(), "player_resolver")
        self.sackmann = sackmann_loader or self._safe_construct(SackmannLoader, _NullLayer("history", SACKMANN_IMPORT_ERROR), "history")
        self.elo = elo_loader or self._safe_construct(EloLoader, _NullLayer("elo", ELO_IMPORT_ERROR), "elo")
        self.ta = ta_loader or self._safe_construct(TALoader, _NullLayer("ta", TA_IMPORT_ERROR), "ta")
        self.h2h = h2h_loader or self._safe_construct(H2HLoader, _NullLayer("h2h", H2H_IMPORT_ERROR), "h2h")

    def _safe_construct(self, cls: Any, fallback: Any, layer: str) -> Any:
        if cls is None:
            return fallback
        try:
            return cls()
        except Exception as exc:
            self.import_errors[layer] = str(exc)
            return fallback

    def _safe_call(self, layer: str, func, fallback: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        try:
            result = func(**kwargs)
            if isinstance(result, dict):
                return result
            fallback["reason"] = f"{layer} returned non-dict"
            return fallback
        except Exception as exc:
            fallback["status"] = "ERROR_NON_BLOCKING"
            fallback["reason"] = str(exc)
            fallback.setdefault("flags", []).append(f"{layer.upper()}_ERROR_NON_BLOCKING")
            return fallback

    def load_player(
        self,
        player_name: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        tournament_url: Optional[str] = None,
        as_of_date: Optional[str] = None,
        tour_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        identity_fallback = {
            "canonical_name": player_name,
            "input_name": player_name,
            "tour": tour_type,
            "resolver_status": "FALLBACK_IDENTITY",
        }
        identity = self._safe_call(
            "player_resolver",
            self.resolver.resolve,
            identity_fallback,
            player_name=player_name,
            tour=tour_type,
        )
        canonical_name = identity.get("canonical_name") or player_name

        history = self._safe_call(
            "history",
            self.sackmann.load_player,
            {"status": "NO_DATA", "layer": "history", "flags": ["HISTORY_NO_DATA"]},
            player_name=canonical_name,
            surface=surface,
            level=level,
            as_of_date=as_of_date,
        )
        elo = self._safe_call(
            "elo",
            self.elo.load_player,
            {"status": "NO_DATA", "layer": "elo", "flags": ["ELO_NO_DATA"]},
            player_name=canonical_name,
            tour=tour_type,
        )
        ta = self._safe_call(
            "ta",
            self.ta.load_player,
            {"status": "NO_DATA", "layer": "ta", "flags": ["TA_NO_DATA"]},
            player_name=canonical_name,
            tournament_url=tournament_url,
        )
        return {
            "player": canonical_name,
            "input_player": player_name,
            "identity": identity,
            "surface": surface,
            "level": level,
            "history": history,
            "elo": elo,
            "ta": ta,
        }

    def load_match(
        self,
        player1: str,
        player2: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        tournament_url: Optional[str] = None,
        tour_type: Optional[str] = None,
        as_of_date: Optional[str] = None,
        event_id: Optional[Any] = None,
        player1_id: Optional[Any] = None,
        player2_id: Optional[Any] = None,
        tournament_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        player1_data = self.load_player(player1, surface, level, tournament_url, as_of_date, tour_type)
        player2_data = self.load_player(player2, surface, level, tournament_url, as_of_date, tour_type)
        p1_id = player1_id or player1_data.get("identity", {}).get("rapidapi_id")
        p2_id = player2_id or player2_data.get("identity", {}).get("rapidapi_id")
        h2h = self._safe_call(
            "h2h",
            self.h2h.load_h2h,
            build_empty_h2h(player1, player2, surface, self.import_errors.get("h2h") or "No H2H data"),
            player1=player1_data.get("player") or player1,
            player2=player2_data.get("player") or player2,
            surface=surface,
            tour_type=tour_type,
            event_id=event_id,
            player1_id=p1_id,
            player2_id=p2_id,
            tournament_id=tournament_id,
        )
        if not isinstance(h2h, dict) or not h2h:
            h2h = build_empty_h2h(player1, player2, surface, "H2H returned empty")
        h2h.setdefault("h2h_status", "AVAILABLE" if h2h.get("h2h_total_matches") else "NO_DATA")
        h2h.setdefault("h2h_confidence", 0.0)
        h2h.setdefault("h2h_edge", 0.0)

        return {
            "player1": player1_data,
            "player2": player2_data,
            "surface": surface,
            "level": level,
            "h2h": h2h,
            "loader_import_errors": {k: v for k, v in self.import_errors.items() if v},
        }
