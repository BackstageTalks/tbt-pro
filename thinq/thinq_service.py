"""
THINQ Intelligence Layer

THINQ is the brain/intelligence layer for CORQ.
THINQ does not create final match probability.
THINQ returns feature, edge, flag and confidence signals.
CORQ remains the CORE model for final probability, ranking and TOP outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .loaders.thinq_loader import ThinqLoader
except Exception:
    try:
        from thinq.loaders.thinq_loader import ThinqLoader
    except Exception as exc:
        ThinqLoader = None
        THINQ_LOADER_IMPORT_ERROR = str(exc)

try:
    from .features import (
        build_data_quality,
        build_fatigue_context,
        build_level_context,
        build_match_dynamics,
        build_status_risk,
        build_surface_transition_context,
    )
except Exception:
    try:
        from thinq.features import (
            build_data_quality,
            build_fatigue_context,
            build_level_context,
            build_match_dynamics,
            build_status_risk,
            build_surface_transition_context,
        )
    except Exception as exc:
        FEATURE_IMPORT_ERROR = str(exc)

        def build_data_quality(raw, edges):
            return {"data_quality_score": 0.0, "flags": ["FEATURE_IMPORT_FAILED", "DATA_QUALITY_UNAVAILABLE"], "reason": FEATURE_IMPORT_ERROR}

        def build_fatigue_context(raw, as_of_date=None):
            return {"fatigue_edge": None, "flags": ["FATIGUE_UNAVAILABLE"]}

        def build_level_context(raw, level=None):
            return {"level_context_edge": None, "flags": ["LEVEL_CONTEXT_UNAVAILABLE"]}

        def build_match_dynamics(raw, edges, surface=None, best_of=3):
            return {"confidence": 0.0, "sets_edge": None, "games_edge": None, "tiebreak_edge": None, "decider_edge": None, "flags": ["MATCH_DYNAMICS_UNAVAILABLE"]}

        def build_status_risk(raw):
            return {"status_risk_edge": None, "flags": ["STATUS_RISK_UNAVAILABLE"]}

        def build_surface_transition_context(raw, surface=None):
            return {"surface_transition_edge": None, "flags": ["SURFACE_TRANSITION_UNAVAILABLE"]}



class ThinqService:
    """
    Public THINQ entry point for CORQ.

    Recommended CORQ usage:
        thinq = ThinqService()
        features = thinq.build_match_features(...)
        corq consumes features["edges"], features["contexts"], confidence and flags.
    """

    def __init__(self, loader: Optional[ThinqLoader] = None, output_dir: Optional[str] = None) -> None:
        self.loader = loader or ThinqLoader()
        self.output_dir = Path(output_dir) if output_dir else Path("thinq/outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_player_data(
        self,
        player_name: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        tournament_url: Optional[str] = None,
        as_of_date: Optional[str] = None,
        tour_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.loader.load_player(player_name, surface, level, tournament_url, as_of_date, tour_type)

    def build_match_features(
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
        best_of: int = 3,
        save_snapshot: bool = False,
    ) -> Dict[str, Any]:
        raw = self.loader.load_match(
            player1=player1,
            player2=player2,
            surface=surface,
            level=level,
            tournament_url=tournament_url,
            tour_type=tour_type,
            as_of_date=as_of_date,
            event_id=event_id,
            player1_id=player1_id,
            player2_id=player2_id,
            tournament_id=tournament_id,
        )

        edges = self._calculate_base_edges(raw)

        fatigue = build_fatigue_context(raw, as_of_date=as_of_date)
        transition = build_surface_transition_context(raw, surface=surface)
        level_ctx = build_level_context(raw, level=level)
        status = build_status_risk(raw)
        match_dynamics = build_match_dynamics(raw, edges, surface=surface, best_of=best_of)

        edges.update({
            "fatigue_edge": fatigue.get("fatigue_edge"),
            "surface_transition_edge": transition.get("surface_transition_edge"),
            "level_context_edge": level_ctx.get("level_context_edge"),
            "status_risk_edge": status.get("status_risk_edge"),
            "sets_edge": match_dynamics.get("sets_edge"),
            "games_edge": match_dynamics.get("games_edge"),
            "tiebreak_edge": match_dynamics.get("tiebreak_edge"),
            "decider_edge": match_dynamics.get("decider_edge"),
        })

        data_quality = build_data_quality(raw, edges)
        confidence = self._calculate_total_confidence(raw, edges, data_quality, match_dynamics)
        flags = self._build_flags(raw, edges, confidence)
        flags.extend(data_quality.get("flags", []))
        flags.extend(fatigue.get("flags", []))
        flags.extend(transition.get("flags", []))
        flags.extend(level_ctx.get("flags", []))
        flags.extend(status.get("flags", []))
        flags.extend(match_dynamics.get("flags", []))
        flags = sorted(set(flags))

        output = {
            "player1": player1,
            "player2": player2,
            "surface": surface,
            "level": level,
            "best_of": best_of,
            "thinq_role": "intelligence_layer",
            "thinq_version": "full_integration_v1",
            "edges": edges,
            "confidence": confidence,
            "data_quality": data_quality,
            "contexts": {
                "fatigue": fatigue,
                "surface_transition": transition,
                "level_context": level_ctx,
                "status_risk": status,
                "match_dynamics": match_dynamics,
            },
            "flags": flags,
            "raw": raw,
        }

        if save_snapshot:
            self.save_match_snapshot(output)
        return output

    def save_match_snapshot(self, output: Dict[str, Any]) -> Path:
        player1 = self._safe_name(output.get("player1"))
        player2 = self._safe_name(output.get("player2"))
        surface = self._safe_name(output.get("surface") or "all")
        path = self.output_dir / f"thinq_{player1}_vs_{player2}_{surface}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _calculate_base_edges(self, raw: Dict[str, Any]) -> Dict[str, Optional[float]]:
        p1 = raw.get("player1", {}) if isinstance(raw.get("player1"), dict) else {}
        p2 = raw.get("player2", {}) if isinstance(raw.get("player2"), dict) else {}
        p1_history = p1.get("history", {})
        p2_history = p2.get("history", {})
        p1_elo = p1.get("elo", {})
        p2_elo = p2.get("elo", {})
        p1_ta = p1.get("ta", {})
        p2_ta = p2.get("ta", {})
        h2h = raw.get("h2h", {}) if isinstance(raw.get("h2h"), dict) else {}

        return {
            "surface_form_edge": self._edge_from_percent_diff(p1_history.get("surface_win_pct_52w"), p2_history.get("surface_win_pct_52w"), cap=0.12),
            "recent_form_edge": self._edge_from_percent_diff(p1_history.get("last10_win_pct"), p2_history.get("last10_win_pct"), cap=0.10),
            "level_form_edge": self._edge_from_percent_diff(p1_history.get("level_win_pct"), p2_history.get("level_win_pct"), cap=0.08),
            "elo_edge": self._edge_from_elo(p1_elo, p2_elo, raw.get("surface")),
            "opponent_quality_edge": None,
            "ta_edge": self._edge_from_ta(p1_ta, p2_ta),
            "h2h_edge": self._to_float_or_none(h2h.get("h2h_edge")),
        }

    @staticmethod
    def _edge_from_percent_diff(p1_value: Any, p2_value: Any, cap: float) -> Optional[float]:
        p1_float = ThinqService._to_float_or_none(p1_value)
        p2_float = ThinqService._to_float_or_none(p2_value)
        if p1_float is None or p2_float is None:
            return None
        return round(max(min(p1_float - p2_float, cap), -cap), 4)

    @staticmethod
    def _edge_from_elo(p1_elo: Dict[str, Any], p2_elo: Dict[str, Any], surface: Optional[str]) -> Optional[float]:
        surface_key = ThinqService._surface_elo_key(surface)
        p1_value = p2_value = None
        if surface_key:
            p1_value = ThinqService._to_float_or_none(p1_elo.get(surface_key))
            p2_value = ThinqService._to_float_or_none(p2_elo.get(surface_key))
        if p1_value is None or p2_value is None:
            p1_value = ThinqService._to_float_or_none(p1_elo.get("elo"))
            p2_value = ThinqService._to_float_or_none(p2_elo.get("elo"))
        if p1_value is None or p2_value is None:
            return None
        return round(max(min((p1_value - p2_value) / 2000, 0.10), -0.10), 4)

    @staticmethod
    def _edge_from_ta(p1_ta: Dict[str, Any], p2_ta: Dict[str, Any]) -> Optional[float]:
        p1_forecast = ThinqService._to_float_or_none(p1_ta.get("ta_forecast"))
        p2_forecast = ThinqService._to_float_or_none(p2_ta.get("ta_forecast"))
        if p1_forecast is None or p2_forecast is None:
            return None
        if p1_forecast > 1:
            p1_forecast /= 100
        if p2_forecast > 1:
            p2_forecast /= 100
        return round(max(min(p1_forecast - p2_forecast, 0.08), -0.08), 4)

    def _calculate_total_confidence(
        self,
        raw: Dict[str, Any],
        edges: Dict[str, Optional[float]],
        data_quality: Dict[str, Any],
        match_dynamics: Dict[str, Any],
    ) -> float:
        h2h = raw.get("h2h", {}) if isinstance(raw.get("h2h"), dict) else {}
        h2h_conf = self._to_float_or_none(h2h.get("h2h_confidence")) or 0.0
        quality_score = self._to_float_or_none(data_quality.get("data_quality_score")) or 0.0
        dynamics_conf = self._to_float_or_none(match_dynamics.get("confidence")) or 0.0
        edge_coverage = self._edge_coverage(edges)
        confidence = (0.45 * quality_score) + (0.15 * h2h_conf) + (0.25 * edge_coverage) + (0.15 * dynamics_conf)
        return round(max(min(confidence, 1.0), 0.0), 4)

    @staticmethod
    def _build_flags(raw: Dict[str, Any], edges: Dict[str, Optional[float]], confidence: float) -> List[str]:
        flags: List[str] = []
        edge_flag_rules = [
            ("h2h_edge", 0.04, "H2H_STRONG_PLAYER1", "H2H_STRONG_PLAYER2"),
            ("surface_form_edge", 0.08, "SURFACE_FORM_STRONG_PLAYER1", "SURFACE_FORM_STRONG_PLAYER2"),
            ("recent_form_edge", 0.07, "RECENT_FORM_STRONG_PLAYER1", "RECENT_FORM_STRONG_PLAYER2"),
            ("elo_edge", 0.06, "ELO_STRONG_PLAYER1", "ELO_STRONG_PLAYER2"),
        ]
        for key, threshold, p1_flag, p2_flag in edge_flag_rules:
            value = edges.get(key)
            if value is None:
                continue
            if value >= threshold:
                flags.append(p1_flag)
            elif value <= -threshold:
                flags.append(p2_flag)

        if confidence < 0.35:
            flags.append("THINQ_LOW_CONFIDENCE")
        return flags

    @staticmethod
    def _to_float_or_none(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _edge_coverage(edges: Dict[str, Optional[float]]) -> float:
        if not edges:
            return 0.0
        return round(sum(1 for value in edges.values() if value is not None) / len(edges), 4)

    @staticmethod
    def _surface_elo_key(surface: Optional[str]) -> Optional[str]:
        if not surface:
            return None
        mapping = {
            "hard": "hard_elo",
            "clay": "clay_elo",
            "grass": "grass_elo",
            "indoor": "indoor_elo",
            "indoor hard": "indoor_elo",
            "i.hard": "indoor_elo",
        }
        return mapping.get(str(surface).strip().lower())

    @staticmethod
    def _safe_name(value: Any) -> str:
        text = str(value or "unknown").strip().lower()
        keep = []
        for char in text:
            if char.isalnum():
                keep.append(char)
            elif char in [" ", "-", "_"]:
                keep.append("_")
        text = "".join(keep)
        while "__" in text:
            text = text.replace("__", "_")
        return text.strip("_") or "unknown"
