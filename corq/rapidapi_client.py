"""Compatibility wrapper for legacy corq.rapidapi_client imports.

The canonical API PRO implementation lives in corq.corq_rapidapi_client.
Keep this file intentionally thin so old imports do not create a second
RapidAPI/TennisAPI code path.
"""
from __future__ import annotations

from .corq_rapidapi_client import *  # noqa: F401,F403
