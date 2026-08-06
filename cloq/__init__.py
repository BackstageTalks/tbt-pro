"""CloQ value-first model package.

CloQ is intentionally separate from CorQ:
- CorQ ranks likely winners and final model probability.
- CloQ ranks clean betting value, using CorQ/ThinQ/MarQ outputs as inputs.

It writes:
- outputs/cloq/latest_cloq.json
- outputs/latest_cloq.json
- outputs/cloq/latest_cloq_audit.json
- outputs/cloq/latest_cloq_manifest.json
"""
from __future__ import annotations

__all__ = ["__version__"]
__version__ = "2026-08-06-value-first-v4-clean-value"
