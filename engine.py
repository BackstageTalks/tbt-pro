"""Top-level compatibility entrypoint for the tennis prediction pipeline.

The real CorQ daily engine lives in corq.engine.  Keep this root file tiny so
accidentally editing it cannot change model behaviour.
"""

from __future__ import annotations

from corq.engine import main


if __name__ == "__main__":
    raise SystemExit(main())
