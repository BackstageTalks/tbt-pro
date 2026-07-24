
# Stable TBT PRO web paths.
from __future__ import annotations

import os
from urllib.parse import urljoin

CORQ_PATH = "h4v34n1c3d4y180"
CLOQ_PATH = "h4v34n1c3d4y181"
ALL_PATH = "h4v34n1c3d4y182"
RESULTS_PATH = "h4v34n1c3d4y183"
CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"
THINQ_PATH = "h4v34n1c3d4y186"
THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"

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

def base_url() -> str:
    value = os.getenv("TBTPRO_BASE_URL", "").strip()
    if value and not value.endswith("/"):
        value += "/"
    return value

def page_file(path: str) -> str:
    return path if path.endswith(".xml") else f"{path}/index.html"

def page_url(path: str) -> str:
    root = base_url()
    if root:
        return urljoin(root, path)
    return f"../{path}" if path.endswith(".xml") else f"../{path}/"
