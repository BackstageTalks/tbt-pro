"""Compatibility wrapper for the canonical CorQ TennisAPI PRO client.

The implementation lives in corq.corq_rapidapi_client. This file is kept only
so older imports of corq.rapidapi_client continue to work without maintaining a
second RapidAPI client implementation.
"""

from __future__ import annotations

from corq.corq_rapidapi_client import *  # noqa: F401,F403

API_CLIENT_ALIAS = "corq.rapidapi_client -> corq.corq_rapidapi_client"
