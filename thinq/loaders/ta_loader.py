"""
Tennis Abstract Loader

Purpose:
- Load Tennis Abstract reference data.
- Include TA ELO, TA surface ELO, ranking and forecast fields.
- Provide TAQ data for THINQ.

Important:
- This file intentionally does not scrape yet.
- Scraping/parsing will be added once exact target pages and naming rules are finalized.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class TAQPlayerData:
    player: str

    ta_rank: Optional[int] = None
    ta_elo: Optional[float] = None
    ta_hard_elo: Optional[float] = None
    ta_clay_elo: Optional[float] = None
    ta_grass_elo: Optional[float] = None
    ta_indoor_elo: Optional[float] = None

    ta_forecast: Optional[float] = None
    ta_tournament_forecast: Optional[float] = None

    career_surface_win_pct: Optional[float] = None
    last52w_surface_win_pct: Optional[float] = None

    source: str = "tennisabstract"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TALoader:
    """
    Loader for Tennis Abstract data.

    Current version returns a stable schema with None values.
    Next step: add page fetch/cache/parser logic for tournament/player pages.
    """

    def __init__(self, data_dir: Optional[str] = None, cache_dir: Optional[str] = None) -> None:
        self.data_dir = data_dir
        self.cache_dir = cache_dir

    def load_player(
        self,
        player_name: str,
        tournament_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = TAQPlayerData(player=player_name)
        return data.to_dict()
