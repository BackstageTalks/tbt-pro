"""Public/obfuscated web paths for TBT PRO pages.

These paths intentionally stay stable and are reused by all renderers, links,
RSS files and GitHub Pages output.

Domain/base can be set by env:
- TBTPRO_BASE_URL, for example https://<user>.github.io/tbtpro
- TBTPRO_SITE_PREFIX, optional path prefix if needed
"""

from __future__ import annotations

import os
from urllib.parse import urljoin

# Stable random paths reused from the old project style.
CORQ_PATH = "h4v34n1c3d4y180"
CLOQ_PATH = "h4v34n1c3d4y181"
ALL_PATH = "h4v34n1c3d4y182"
RESULTS_PATH = "h4v34n1c3d4y183"
CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"

# Planned future paths. Kept here so navigation can be stable from day one.
THINQ_PATH = "h4v34n1c3d4y186"
THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"
MARQ_PATH = "h4v34n1c3d4y188"
SETS_GAMES_PATH = "h4v34n1c3d4y189"

DEFAULT_SITE_PREFIX = ""


def site_prefix() -> str:
    value = os.getenv("TBTPRO_SITE_PREFIX", DEFAULT_SITE_PREFIX).strip()
    return value.strip("/")


def base_url() -> str:
    # Example: https://username.github.io/tbtpro/
    value = os.getenv("TBTPRO_BASE_URL", "").strip()
    if value and not value.endswith("/"):
        value += "/"
    return value


def prefixed_path(path: str) -> str:
    prefix = site_prefix()
    clean = path.lstrip("/")
    if prefix:
        return f"{prefix}/{clean}"
    return clean


def page_file(path: str) -> str:
    # For extensionless pages rendered as folders with index.html.
    if path.endswith(".xml"):
        return path
    return f"{path}/index.html"


def page_url(path: str) -> str:
    local = prefixed_path(path)
    root = base_url()
    if root:
        return urljoin(root, local)
    return f"/{local}"


NAV_ITEMS = [
    {"key": "corq", "label": "Corq", "path": CORQ_PATH},
    {"key": "thinq", "label": "Thinq", "path": THINQ_PATH},
    {"key": "cloq", "label": "Cloq", "path": CLOQ_PATH},
    {"key": "all", "label": "All", "path": ALL_PATH},
    {"key": "results", "label": "Results", "path": RESULTS_PATH},
    {"key": "corq_rss", "label": "Corq RSS", "path": CORQ_RSS_PATH},
    {"key": "thinq_rss", "label": "Thinq RSS", "path": THINQ_RSS_PATH},
    {"key": "cloq_rss", "label": "Cloq RSS", "path": CLOQ_RSS_PATH},
]


def nav_urls() -> list[dict[str, str]]:
    return [{**item, "url": page_url(item["path"])} for item in NAV_ITEMS]
