from __future__ import annotations
"""Compatibility wrapper for the Results engine.

The canonical implementation lives in ``builder.py``. This file remains in the
repo so older workflow imports or manual commands that reference
``corq.results_engine.results`` continue to work without maintaining a second
copy of the settlement logic.
"""

from .builder import (  # noqa: F401
    build_results,
    build_results_database,
    evaluate_row,
    main,
    summary,
)

if __name__ == "__main__":
    main()
