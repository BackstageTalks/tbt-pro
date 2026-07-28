from __future__ import annotations

# Backward-compatible entrypoint.
# Kept so existing workflows calling `python -m corq.results_db` keep working.

from pathlib import Path
from typing import Any, Dict, Optional

from corq.results_engine.builder import RESULTS_DIR, build_results_database as _build_results_database, main


def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR) -> Dict[str, Any]:
    return _build_results_database(run_date=run_date, output_root=Path(output_root), fetch_api=False)


if __name__ == "__main__":
    main()
