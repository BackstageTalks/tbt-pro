"""Compatibility wrapper for the single ThinQ service implementation.

Keep this module thin on purpose. Runtime logic lives in thinq/service.py.
This prevents corq.service and thinq.service from drifting again.
"""

from thinq.service import ThinqService, build_match_features  # noqa: F401

__all__ = ["ThinqService", "build_match_features"]
