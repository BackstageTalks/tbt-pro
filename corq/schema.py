"""CORQ output schema helpers.

This module intentionally avoids corq_probability and AI Match for the clean
runtime. CORQ now produces a ranking score, edge, adjusted score and flags.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CorqPrediction:
    event_id: Optional[str]
    player1: str
    player2: str
    pick: str
    opponent: str
    surface: Optional[str] = None
    level: Optional[str] = None
    tournament: Optional[str] = None
    start_time: Optional[str] = None
    odds: Optional[float] = None
    opponent_odds: Optional[float] = None
    implied_probability: Optional[float] = None
    thinq_confidence: float = 0.0
    thinq_available: bool = False
    thinq_edges: Dict[str, Optional[float]] = field(default_factory=dict)
    thinq_flags: List[str] = field(default_factory=list)
    corq_score: float = 0.0
    corq_edge: float = 0.0
    corq_edge_bonus: float = 0.0
    corq_risk_penalty: float = 0.0
    corq_adjusted_score: float = 0.0
    corq_risk_flags: List[str] = field(default_factory=list)
    eligible_for_corq: bool = False
    corq_reject_reasons: List[str] = field(default_factory=list)
    corq_rank: Optional[int] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
