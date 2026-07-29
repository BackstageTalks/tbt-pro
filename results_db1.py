from __future__ import annotations

# Compatibility wrapper for old workflows still calling:
#   python -m corq.results_db
# Real implementation lives in:
#   corq/results_engine/results_db.py

from corq.results_engine.results_db import build_results_database, main

__all__ = ["build_results_database", "main"]


if __name__ == "__main__":
    main()
