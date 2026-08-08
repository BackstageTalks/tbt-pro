"""CloQ high-confidence price model package.

CloQ is intentionally separate from CorQ:
- CorQ ranks overall prediction quality and final model probability.
- CloQ searches for higher-price candidates that still have enough ThinQ/MarQ/data support.

No synthetic odds, probabilities or evidence values are generated. Missing data is surfaced as reject/audit reasons.
"""
from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2026-08-08-high-confidence-price-v3"
