"""
THINQ Feature Modules

Feature modules calculate intelligence edges and risk/context flags.
They do not create final probabilities. CORQ remains the CORE output model.
"""

from .data_quality import build_data_quality
from .schedule_fatigue import build_fatigue_context
from .surface_transition import build_surface_transition_context
from .level_context import build_level_context
from .status_risk import build_status_risk
from .match_dynamics import build_match_dynamics

__all__ = [
    "build_data_quality",
    "build_fatigue_context",
    "build_surface_transition_context",
    "build_level_context",
    "build_status_risk",
    "build_match_dynamics",
]
