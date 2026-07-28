from __future__ import annotations

# Results DB entrypoint moved from corq/results_db.py into corq/results_engine/.
# Preferred command:
#   python -m corq.results_engine.results_db --output-root outputs/results

from pathlib import Path
from typing import Any, Dict, Optional

from .builder import RESULTS_DIR, build_results_database as _build_results_database, main


def build_results_database(run_date: Optional[str] = None, output_root: Path = RESULTS_DIR) -> Dict[str, Any]:
    return _build_results_database(run_date=run_date, output_root=Path(output_root), fetch_api=False)


if __name__ == "__main__":
    main()
