"""ThinQ compatibility wrapper for the canonical CorQ TennisAPI PRO client.

ThinQ previously carried a separate rapidapi_client.py copy that duplicated the
CorQ API client and could drift into a different source/host. This wrapper keeps
legacy ThinQ imports working while routing all calls through the single PRO
client in corq.corq_rapidapi_client.
"""

from __future__ import annotations

from corq.corq_rapidapi_client import *  # noqa: F401,F403

API_CLIENT_ALIAS = "thinq.loaders.rapidapi_client -> corq.corq_rapidapi_client"
