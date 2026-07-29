from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from marq.enrich import enrich_json_file


DEFAULT_FILES = [
    "latest_top7.json",
    "latest_all.json",
    "latest_audit.json",
    "latest_cloq.json",
    "snapshots/latest_corq_top7_snapshot.json",
    "snapshots/latest_all_audit_snapshot.json",
    "snapshots/latest_cloq_snapshot.json",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich CorQ/Audit/CloQ rows with MarQ market data")
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit per file for smoke tests")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--files", default=",".join(DEFAULT_FILES), help="Comma-separated files relative to outputs dir")
    args = parser.parse_args()
    outputs_dir = Path(args.outputs_dir)
    files: List[str] = [x.strip() for x in str(args.files).split(",") if x.strip()]
    total = 0
    for rel in files:
        path = outputs_dir / rel
        if not path.exists():
            print(f"[marq] skip missing {path}")
            continue
        total += enrich_json_file(path, limit=args.limit, force_refresh=args.force_refresh)
    print(f"[marq] done total_rows={total}")


if __name__ == "__main__":
    main()
