"""CloQ value-first model package.

CloQ is intentionally separate from CorQ:
- CorQ ranks likely winners and final model probability.
- CloQ ranks betting value, using CorQ/ThinQ outputs as inputs.

The public entrypoint is::

    python -m cloq.engine --input outputs/latest_all.json --output-root outputs

It writes:
- outputs/cloq/latest_cloq.json
- outputs/latest_cloq.json
- outputs/cloq/latest_cloq_manifest.json
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "2026-08-04-value-first-v3-high-value"
