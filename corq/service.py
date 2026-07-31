"""CORQ compatibility wrapper for the ThinQ service.

The production prediction engine imports `ThinqService` from `thinq.service`.
This file is intentionally kept as a thin wrapper so old imports from
`corq.service` do not drift away from the real implementation.
"""
from __future__ import annotations

try:
    from thinq.service import ThinqService, build_match_features  # type: ignore
except Exception as exc:  # pragma: no cover - import-time safety for isolated contexts
    _IMPORT_ERROR = exc

    class ThinqService:  # type: ignore[no-redef]
        """Safe fallback that reports the import failure instead of crashing imports."""

        def __init__(self, *args, **kwargs) -> None:
            pass

        def build_match_features(self, *args, **kwargs):
            return {
                "available": False,
                "error": f"corq.service wrapper could not import thinq.service: {_IMPORT_ERROR}",
                "thinq_available": False,
                "thinq_flags": ["THINQ_SERVICE_IMPORT_FAILED"],
            }

    def build_match_features(*args, **kwargs):  # type: ignore[no-redef]
        return ThinqService().build_match_features(*args, **kwargs)

__all__ = ["ThinqService", "build_match_features"]
