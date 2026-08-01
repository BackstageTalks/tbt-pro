"""CloQ - Close Odds Quality layer for the tennis prediction stack.

CloQ is intentionally lightweight: it reads existing CorQ/ThinQ/MarQ rows,
applies transparent close-odds filters, and writes auditable output. It does not
replace CorQ ranking or filter the main TOP7 flow.
"""

from .filters import CloQConfig, evaluate_cloq_row, score_cloq_row

__all__ = ["CloQConfig", "evaluate_cloq_row", "score_cloq_row"]
