"""CLI helper for generating the BackstageTalks Telegram TOP7 feed.

Usage:
    python -m corq.telegram_feed --input outputs/latest_top7.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List

from corq.presentation import build_telegram_top7


def load_json_list(path: str) -> List[Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Telegram TOP7 feed text")
    parser.add_argument("--input", default="outputs/latest_top7.json", help="Path to latest_top7.json")
    parser.add_argument("--date", default=None, help="Optional run date YYYY-MM-DD or DD.MM.YYYY")
    parser.add_argument("--output", default=None, help="Optional output TXT file")
    args = parser.parse_args()

    text = build_telegram_top7(load_json_list(args.input), run_date=args.date)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
