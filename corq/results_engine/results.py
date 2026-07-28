from __future__ import annotations

# Results entrypoint moved from corq/results.py into corq/results_engine/.
# Preferred command:
#   python -m corq.results_engine.results --output-root outputs

from .builder import build_results, build_results_database, main

__all__ = ["build_results", "build_results_database", "main"]


if __name__ == "__main__":
    main()
