"""Fetch complete ATP/WTA singles rankings from TennisAPI PRO.

The script uses the canonical CorQ API PRO client and its provider-safe
pagination: pageSize=200, pageNo=1,2,3... . No values are fabricated.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from corq.corq_rapidapi_client import RapidApiClient

OUTPUTS = {
    "ATP": Path("thinq/data/rankings/api_rankings_atp.json"),
    "WTA": Path("thinq/data/rankings/api_rankings_wta.json"),
}
ENDPOINTS = {
    "ATP": "/api/tennis/rankings",
    "WTA": "/api/tennis/rankings/wta",
}
ITEM_KEYS = ("rankings", "data", "items", "results", "players")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def fetch_tour(client: RapidApiClient, tour: str, max_pages: int) -> Dict[str, Any]:
    path = ENDPOINTS[tour]
    response = client.paginated_get(
        path,
        items_keys=ITEM_KEYS,
        max_pages=max_pages,
    )
    items: List[Dict[str, Any]] = [
        row for row in (response.get("items") or []) if isinstance(row, dict)
    ]
    status = str(response.get("status") or "UNKNOWN")
    if not items:
        raise RuntimeError(f"{tour} ranking fetch produced zero rows: status={status} path={path}")

    payload = {
        "version": "API_PRO_CURRENT_RANKINGS_V1",
        "generated_at": now_iso(),
        "source": "TENNISAPI_PRO",
        "tour": tour,
        "endpoint": path,
        "page_size": response.get("pageSize"),
        "page_count": response.get("page_count"),
        "item_count": len(items),
        "status": status,
        "pages": response.get("pages") or [],
        "rankings": items,
    }
    write_json(OUTPUTS[tour], payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Update API PRO ATP/WTA rankings")
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    if args.max_pages < 1:
        raise SystemExit("--max-pages must be at least 1")

    client = RapidApiClient()
    report: Dict[str, Any] = {
        "version": "API_PRO_RANKING_UPDATE_REPORT_V1",
        "generated_at": now_iso(),
        "source": "TENNISAPI_PRO",
        "tours": {},
    }
    for tour in ("ATP", "WTA"):
        payload = fetch_tour(client, tour, args.max_pages)
        report["tours"][tour] = {
            "status": payload["status"],
            "item_count": payload["item_count"],
            "page_count": payload["page_count"],
            "output": str(OUTPUTS[tour]),
        }
        print(
            f"[ranking] tour={tour} rows={payload['item_count']} "
            f"pages={payload['page_count']} output={OUTPUTS[tour]}"
        )

    write_json(Path("runtime/players/api_pro_ranking_update_report.json"), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
