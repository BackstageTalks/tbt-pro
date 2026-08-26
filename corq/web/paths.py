"""Stable TBT PRO web paths."""
from __future__ import annotations

import os
from urllib.parse import urljoin

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
BLINQ_PATH = "blinq-portal-k7m3q9"
LUCQ_PATH = "h4v34n1c3d4y188"
LUCQ_RSS_PATH = "h4v34n1c3d4y189.xml"
LUCQ_RESULTS_PATH = "h4v34n1c3d4y190"

NAV_ITEMS = [
    {"key": "top7", "label": "CorQ", "path": TOP7_PATH},
    {"key": "all", "label": "Audit", "path": ALL_PATH},
    {"key": "results", "label": "Results", "path": RESULTS_PATH},
    {"key": "thinq", "label": "ThinQ", "path": THINQ_PATH},
    {"key": "blinq", "label": "BlinQ", "path": BLINQ_PATH},
    {"key": "cloq", "label": "CloQ", "path": CLOQ_PATH},
    {"key": "lucq", "label": "LucQ", "path": LUCQ_PATH},
    {"key": "lucq_results", "label": "LucQ Results", "path": LUCQ_RESULTS_PATH},
    {"key": "tg_rss", "label": "TG", "path": TG_RSS_PATH},
]


def base_url() -> str:
    value = os.getenv(
        "TBTPRO_BASE_URL",
        "https://backstagetalks.github.io/tbt-pro/",
    ).strip()
    if value and not value.endswith("/"):
        value += "/"
    return value


def page_file(path: str) -> str:
    return path if path.endswith(".xml") else f"{path}/index.html"


def page_url(path: str) -> str:
    return urljoin(base_url(), page_file(path)) if base_url() else ""


def site_url(path: str = "") -> str:
    if not path:
        return base_url()
    return (
        urljoin(base_url(), str(path).lstrip("/"))
        if str(path).endswith("/")
        else page_url(path)
    )
