from __future__ import annotations

# Backward-compatible entrypoint.
# Real Results logic lives in corq/results_engine/ so Results can evolve separately.

from corq.results_engine.builder import build_results, build_results_database, main

__all__ = ["build_results", "build_results_database", "main"]


if __name__ == "__main__":
    main()
