"""Compatibility entry point for GitHub Actions: python -m blinq.run."""
from __future__ import annotations

import argparse
from pathlib import Path

from blinq.web.render import render


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the BlinQ static website")
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    output = Path(args.output)
    render(output)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"BlinQ output was not created: {output}")
    print(f"BlinQ website created: {output}")


if __name__ == "__main__":
    main()
