# Stable TBT PRO web paths.
from __future__ import annotations

import os
from urllib.parse import urljoin

# Existing public paths are preserved.
TOP7_PATH = "h4v34n1c3d4y180"
CORQ_PATH = TOP7_PATH
CLOQ_PATH = "h4v34n1c3d4y181"
ALL_PATH = "h4v34n1c3d4y182"
RESULTS_PATH = "h4v34n1c3d4y183"
CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
TG_RSS_PATH = CORQ_RSS_PATH
CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"
THINQ_PATH = "h4v34n1c3d4y186"
THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"

NAV_ITEMS = [
    {"key": "top7", "label": "TOP7", "path": TOP7_PATH},
    {"key": "all", "label": "ALL", "path": ALL_PATH},
    {"key": "results", "label": "Results", "path": RESULTS_PATH},
    {"key": "thinq", "label": "THINQ", "path": THINQ_PATH},
    {"key": "cloq", "label": "CLOQ", "path": CLOQ_PATH},
    {"key": "tg_rss", "label": "TG RSS", "path": TG_RSS_PATH},
]

def base_url() -> str:
    value = os.getenv("TBTPRO_BASE_URL", "https://backstagetalks.github.io/tennis-backstage-talks/").strip()
    if value and not value.endswith("/"):
        value += "/"
    return value

def page_file(path: str) -> str:
    return path if path.endswith(".xml") else f"{path}/index.html"

def page_url(path: str) -> str:
    root = base_url()
    if not root:
        return ""
    return urljoin(root, page_file(path))
