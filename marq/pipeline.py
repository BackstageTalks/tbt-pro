from __future__ import annotations

from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from .provider import fetch_marq_market_data


# ----------------------------------------------------------------------
# MARQ v1 constants
# ----------------------------------------------------------------------

SHARP_SOURCE_KEYWORDS = {
    "betfair",
    "pinnacle",
    "singbet",
}

SHARP_ALIGN_THRESHOLD_PP = 4.0


# ----------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None

        if isinstance(value, str):
            text = value.strip().replace(",", ".")
            if not text:
                return None

            if "/" in text:
                left, right = text.split("/", 1)
                numerator = float(left.strip())
                denominator = float(right.strip())
                if denominator == 0:
                    return None
                number = 1.0 + numerator / denominator
            else:
                number = float(text)
        else:
            number = float(value)

        return number if number > 1.0 else None

    except Exception:
        return None


def _safe_round(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _median_or_none(values: List[float]) -> Optional[float]:
    clean = [float(v) for v in values if _as_float(v) is not None]
    if not clean:
        return None
    return float(median(clean))


def _source_text(quote: Dict[str, Any]) -> str:
    parts: List[str] = []

    for key in (
        "bookmaker",
        "bookmaker_name",
        "provider",
        "provider_name",
        "source",
        "source_name",
        "sourceName",
        "exchange_provider",
    ):
        value = quote.get(key)
        if value:
            parts.append(str(value))

    return " ".join(parts).lower()


def _is_sharp_quote(quote: Dict[str, Any]) -> bool:
    text = _source_text(quote)
    return any(keyword in text for keyword in SHARP_SOURCE_KEYWORDS)


def _opposite_outcome_key(outcome_key: str) -> str:
    return "od2" if outcome_key == "od1" else "od1"


# ----------------------------------------------------------------------
# Quote / side helpers
# ----------------------------------------------------------------------


def _quote_player_side(player_outcome_key: str, match_direction: str) -> str:
    """
    Convert requested player outcome key into quote side.

    outcome key:
        od1 = requested player1
        od2 = requested player2

    match_direction:
        direct   = quote odds_1 belongs to requested player1
        reversed = quote odds_2 belongs to requested player1
    """
    if match_direction == "reversed":
        return "od2" if player_outcome_key == "od1" else "od1"

    return player_outcome_key


def _candidate_keys(side: str, kind: str = "current") -> List[str]:
    """
    Return candidate field names for quote odds.

    side:
        od1 / od2

    kind:
        current / initial
    """
    if side == "od1":
        if kind == "initial":
            return [
                "opening_1",
                "opening_odds_1",
                "initial_1",
                "initial_odds_1",
                "initial_price1",
                "initial_fractional_1",
                "initialFractionalValue1",
                "initialFractionalValue_1",
                "initial_home_odds",
                "home_initial_odds",
            ]

        return [
            "odds_1",
            "od1",
            "price1",
            "home_odds",
            "p1_odds",
            "latest_1",
            "latest_odds_1",
            "current_1",
            "current_odds_1",
            "fractional_1",
            "fractionalValue1",
            "fractionalValue_1",
        ]

    if kind == "initial":
        return [
            "opening_2",
            "opening_odds_2",
            "initial_2",
            "initial_odds_2",
            "initial_price2",
            "initial_fractional_2",
            "initialFractionalValue2",
            "initialFractionalValue_2",
            "initial_away_odds",
            "away_initial_odds",
        ]

    return [
        "odds_2",
        "od2",
        "price2",
        "away_odds",
        "p2_odds",
        "latest_2",
        "latest_odds_2",
        "current_2",
        "current_odds_2",
        "fractional_2",
        "fractionalValue2",
        "fractionalValue_2",
    ]


def _quote_side_odds(
    quote: Dict[str, Any],
    side: str,
    kind: str = "current",
) -> Optional[float]:
    for key in _candidate_keys(side, kind):
        value = _as_float(quote.get(key))
        if value is not None:
            return value

    return None


def _quote_player_odds(
    quote: Dict[str, Any],
    player_outcome_key: str,
    match_direction: str,
    kind: str = "current",
) -> Optional[float]:
    side = _quote_player_side(player_outcome_key, match_direction)
    return _quote_side_odds(quote, side, kind=kind)


def _quote_pick_odds(
    quote: Dict[str, Any],
    outcome_key: str,
    match_direction: str,
    kind: str = "current",
) -> Optional[float]:
    return _quote_player_odds(
        quote=quote,
        player_outcome_key=outcome_key,
        match_direction=match_direction,
        kind=kind,
    )


# ----------------------------------------------------------------------
# Crowd / implied probability helpers
# ----------------------------------------------------------------------


def _no_vig_probabilities(
    odds_1: Optional[float],
    odds_2: Optional[float],
) -> Optional[Tuple[float, float]]:
    odds_1 = _as_float(odds_1)
    odds_2 = _as_float(odds_2)

    if odds_1 is None or odds_2 is None:
        return None

    implied_1 = 1.0 / odds_1
    implied_2 = 1.0 / odds_2
    total = implied_1 + implied_2

    if total <= 0:
        return None

    return implied_1 / total * 100.0, implied_2 / total * 100.0


def _crowd_from_quotes(
    quotes: List[Dict[str, Any]],
    outcome_key: str,
    match_direction: str,
) -> Dict[str, Any]:
    player1_probs: List[float] = []
    player2_probs: List[float] = []
    pick_probs: List[float] = []
    opponent_probs: List[float] = []

    for quote in quotes:
        if not isinstance(quote, dict):
            continue

        player1_odds = _quote_player_odds(
            quote=quote,
            player_outcome_key="od1",
            match_direction=match_direction,
            kind="current",
        )
        player2_odds = _quote_player_odds(
            quote=quote,
            player_outcome_key="od2",
            match_direction=match_direction,
            kind="current",
        )

        pair = _no_vig_probabilities(player1_odds, player2_odds)
        if not pair:
            continue

        p1_pct, p2_pct = pair
        player1_probs.append(p1_pct)
        player2_probs.append(p2_pct)

        if outcome_key == "od1":
            pick_probs.append(p1_pct)
            opponent_probs.append(p2_pct)
        else:
            pick_probs.append(p2_pct)
            opponent_probs.append(p1_pct)

    crowd_p1 = _median_or_none(player1_probs)
    crowd_p2 = _median_or_none(player2_probs)
    crowd_pick = _median_or_none(pick_probs)
    crowd_opp = _median_or_none(opponent_probs)

    return {
        "marq_crowd_player1_pct": _safe_round(crowd_p1, 1),
        "marq_crowd_player2_pct": _safe_round(crowd_p2, 1),
        "marq_crowd_pick_pct": _safe_round(crowd_pick, 1),
        "marq_crowd_opponent_pct": _safe_round(crowd_opp, 1),
    }


# ----------------------------------------------------------------------
# Market move helpers
# ----------------------------------------------------------------------


def _market_move_from_quotes(
    quotes: List[Dict[str, Any]],
    outcome_key: str,
    match_direction: str,
) -> Dict[str, Any]:
    pick_initial_values: List[float] = []
    pick_current_values: List[float] = []
    opponent_initial_values: List[float] = []
    opponent_current_values: List[float] = []

    opponent_key = _opposite_outcome_key(outcome_key)

    for quote in quotes:
        if not isinstance(quote, dict):
            continue

        pick_initial = _quote_pick_odds(
            quote=quote,
            outcome_key=outcome_key,
            match_direction=match_direction,
            kind="initial",
        )
        pick_current = _quote_pick_odds(
            quote=quote,
            outcome_key=outcome_key,
            match_direction=match_direction,
            kind="current",
        )

        opponent_initial = _quote_pick_odds(
            quote=quote,
            outcome_key=opponent_key,
            match_direction=match_direction,
            kind="initial",
        )
        opponent_current = _quote_pick_odds(
            quote=quote,
            outcome_key=opponent_key,
            match_direction=match_direction,
            kind="current",
        )

        if pick_initial is not None and pick_current is not None:
            pick_initial_values.append(pick_initial)
            pick_current_values.append(pick_current)

        if opponent_initial is not None and opponent_current is not None:
            opponent_initial_values.append(opponent_initial)
            opponent_current_values.append(opponent_current)

    pick_initial_median = _median_or_none(pick_initial_values)
    pick_current_median = _median_or_none(pick_current_values)
    opponent_initial_median = _median_or_none(opponent_initial_values)
    opponent_current_median = _median_or_none(opponent_current_values)

    move_signal = "UNKNOWN"
    pick_move_pct = None
    opponent_move_pct = None

    if pick_initial_median and pick_current_median:
        pick_move_pct = (
            (pick_current_median - pick_initial_median)
            / pick_initial_median
            * 100.0
        )

        if abs(pick_move_pct) < 0.75:
            move_signal = "STABLE"
        elif pick_move_pct < 0:
            move_signal = "TOWARD PICK"
        else:
            move_signal = "AGAINST PICK"

    if opponent_initial_median and opponent_current_median:
        opponent_move_pct = (
            (opponent_current_median - opponent_initial_median)
            / opponent_initial_median
            * 100.0
        )

    return {
        "marq_move_signal": move_signal,
        "marq_initial_pick_odds": _safe_round(pick_initial_median, 4),
        "marq_current_pick_odds": _safe_round(pick_current_median, 4),
        "marq_initial_opponent_odds": _safe_round(opponent_initial_median, 4),
        "marq_current_opponent_odds": _safe_round(opponent_current_median, 4),
        "marq_market_move_pct": _safe_round(pick_move_pct, 2),
        "marq_opponent_move_pct": _safe_round(opponent_move_pct, 2),
    }


# ----------------------------------------------------------------------
# Quality helpers
# ----------------------------------------------------------------------


def _market_quality_from_odds(pick_odds_values: List[float]) -> Dict[str, Any]:
    values = [float(value) for value in pick_odds_values if _as_float(value) is not None]
    count = len(values)

    if count == 0:
        return {
            "signal": "NO MARKET DATA",
            "quality_signal": "NO MARKET DATA",
            "score": None,
            "direction": "NO_MARKET_DATA",
            "strength": 0,
            "consistency": 0,
            "provider_count": 0,
            "median_odds": None,
            "spread_pct": None,
            "outlier_count": 0,
        }

    med = float(median(values))
    minimum = min(values)
    maximum = max(values)
    spread_pct = ((maximum - minimum) / med) * 100 if med > 0 else None

    outliers = [
        value
        for value in values
        if med > 0 and abs(value - med) / med >= 0.12
    ]
    outlier_count = len(outliers)

    if count <= 2:
        signal = "THIN MARKET"
        quality_signal = "THIN"
        score = 35
        direction = "LIMITED_MARKET_SAMPLE"
        strength = 25
        consistency = 35

    else:
        non_outliers = [value for value in values if value not in outliers]
        non_outlier_spread = None

        if len(non_outliers) >= 2:
            non_med = float(median(non_outliers))
            non_outlier_spread = (
                (max(non_outliers) - min(non_outliers)) / non_med * 100
                if non_med > 0
                else None
            )

        if (
            outlier_count >= 1
            and len(non_outliers) >= 3
            and non_outlier_spread is not None
            and non_outlier_spread <= 6.0
        ):
            signal = "OUTLIER"
            quality_signal = "OUTLIER"
            score = 60
            direction = "MARKET_HAS_OUTLIER"
            strength = 55
            consistency = 55

        elif spread_pct is not None and spread_pct <= 6.0:
            signal = "CONSENSUS"
            quality_signal = "CONSENSUS"
            score = 80
            direction = "MARKET_CONSENSUS"
            strength = 80
            consistency = 85

        elif spread_pct is not None and spread_pct <= 12.0:
            signal = "CONSENSUS"
            quality_signal = "CONSENSUS"
            score = 70
            direction = "MARKET_SOFT_CONSENSUS"
            strength = 65
            consistency = 70

        else:
            signal = "MIXED MARKET"
            quality_signal = "MIXED"
            score = 45
            direction = "MARKET_DISAGREEMENT"
            strength = 55
            consistency = 40

    return {
        "signal": signal,
        "quality_signal": quality_signal,
        "score": score,
        "direction": direction,
        "strength": strength,
        "consistency": consistency,
        "provider_count": count,
        "median_odds": round(med, 4),
        "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
        "outlier_count": outlier_count,
    }


# ----------------------------------------------------------------------
# Sharp / exchange helpers
# ----------------------------------------------------------------------


def _sharp_probability_from_quotes(
    quotes: List[Dict[str, Any]],
    outcome_key: str,
    match_direction: str,
) -> Optional[float]:
    sharp_pick_probs: List[float] = []

    for quote in quotes:
        if not isinstance(quote, dict):
            continue

        if not _is_sharp_quote(quote):
            continue

        player1_odds = _quote_player_odds(
            quote=quote,
            player_outcome_key="od1",
            match_direction=match_direction,
            kind="current",
        )
        player2_odds = _quote_player_odds(
            quote=quote,
            player_outcome_key="od2",
            match_direction=match_direction,
            kind="current",
        )

        pair = _no_vig_probabilities(player1_odds, player2_odds)
        if not pair:
            continue

        p1_pct, p2_pct = pair
        sharp_pick_probs.append(p1_pct if outcome_key == "od1" else p2_pct)

    return _median_or_none(sharp_pick_probs)


def _sharp_signal(
    crowd_pick_pct: Optional[float],
    sharp_pick_pct: Optional[float],
) -> str:
    if crowd_pick_pct is None or sharp_pick_pct is None:
        return "NO SHARP DATA"

    gap = abs(float(crowd_pick_pct) - float(sharp_pick_pct))

    if gap <= SHARP_ALIGN_THRESHOLD_PP:
        return "ALIGN"

    return "DISAGREE"


def _exchange_fields(market_data: Dict[str, Any]) -> Dict[str, Any]:
    exchange_available = bool(
        market_data.get("exchange_available")
        or market_data.get("exchange_provider")
        or market_data.get("exchange_total_matched")
    )

    return {
        "marq_exchange_available": exchange_available,
        "marq_exchange_provider": market_data.get("exchange_provider"),
        "marq_exchange_market_id": market_data.get("exchange_market_id"),
        "marq_exchange_total_matched": market_data.get("exchange_total_matched"),
        "marq_exchange_total_available": market_data.get("exchange_total_available"),
        "marq_exchange_pick_price": market_data.get("exchange_pick_price"),
        "marq_exchange_opponent_price": market_data.get("exchange_opponent_price"),
    }


# ----------------------------------------------------------------------
# Empty result
# ----------------------------------------------------------------------


def _empty_marq(
    reason: str = "missing_data",
    event_id: Optional[str] = None,
    outcome_key: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "marq_market_view": False,

        "marq_ai_score": None,
        "marq_ai_signal": "NO MARKET DATA",
        "marq_ai_direction": "NO_MARKET_DATA",
        "marq_ai_strength": 0,
        "marq_ai_consistency": 0,
        "marq_ai_reason": reason,

        "marq_event_id": event_id,
        "marq_outcome_key": outcome_key,
        "marq_source": None,
        "marq_market_name": None,

        "marq_provider_count": 0,
        "marq_market_spread_pct": None,
        "marq_market_median_odds": None,
        "marq_outlier_count": 0,

        "marq_crowd_player1_pct": None,
        "marq_crowd_player2_pct": None,
        "marq_crowd_pick_pct": None,
        "marq_crowd_opponent_pct": None,

        "marq_move_signal": "UNKNOWN",
        "marq_initial_pick_odds": None,
        "marq_current_pick_odds": None,
        "marq_initial_opponent_odds": None,
        "marq_current_opponent_odds": None,
        "marq_market_move_pct": None,
        "marq_opponent_move_pct": None,
        "marq_probability_change_pp": None,

        "marq_sharp_signal": "NO SHARP DATA",
        "marq_sharp_pick_pct": None,
        "marq_quality_signal": "NO MARKET DATA",
        "marq_clv_status": "PENDING",

        "marq_exchange_available": False,
        "marq_exchange_provider": None,
        "marq_exchange_market_id": None,
        "marq_exchange_total_matched": None,
        "marq_exchange_total_available": None,
        "marq_exchange_pick_price": None,
        "marq_exchange_opponent_price": None,
    }


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def build_marq_from_match(
    player1: str,
    player2: str,
    date_only: str,
    pick: Optional[str] = None,
    odds_player1: Optional[float] = None,
    odds_player2: Optional[float] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    MARQ = MARKET VIEW.

    v1 output:
    - Crowd: no-vig market implied probability
    - Move: initial vs current market move
    - Sharp: Betfair/Pinnacle/Singbet proxy when available
    - Quality: market quote quality / sample quality
    - CLV: pending placeholder for future snapshot-vs-closing workflow
    """
    try:
        market_data = fetch_marq_market_data(
            player1=player1,
            player2=player2,
            date_only=date_only,
            pick=pick,
            odds_player1=odds_player1,
            odds_player2=odds_player2,
        )

    except Exception as exc:
        print(
            f"MARQ AI ERROR: provider failed {player1} vs {player2} "
            f"{date_only}: {exc}"
        )
        return _empty_marq(reason="provider_error")

    if not market_data:
        print(f"MARQ DEBUG: market_data missing {player1} vs {player2} {date_only}")
        return _empty_marq(reason="market_data_missing")

    outcome_key = market_data.get("pick_outcome_key") or "od1"
    match_direction = market_data.get("match_direction") or "direct"
    quotes = market_data.get("market_quotes") or []

    pick_odds_values: List[float] = []

    for quote in quotes:
        if not isinstance(quote, dict):
            continue

        value = _quote_pick_odds(
            quote=quote,
            outcome_key=outcome_key,
            match_direction=match_direction,
            kind="current",
        )

        if value is not None:
            pick_odds_values.append(value)

    quality = _market_quality_from_odds(pick_odds_values)

    crowd = _crowd_from_quotes(
        quotes=quotes,
        outcome_key=outcome_key,
        match_direction=match_direction,
    )

    move = _market_move_from_quotes(
        quotes=quotes,
        outcome_key=outcome_key,
        match_direction=match_direction,
    )

    exchange = _exchange_fields(market_data)

    sharp_pick_pct = _sharp_probability_from_quotes(
        quotes=quotes,
        outcome_key=outcome_key,
        match_direction=match_direction,
    )

    # If provider later supplies direct exchange prices, use them as sharp proxy.
    if sharp_pick_pct is None:
        exchange_pick_price = _as_float(exchange.get("marq_exchange_pick_price"))
        exchange_opponent_price = _as_float(exchange.get("marq_exchange_opponent_price"))
        pair = _no_vig_probabilities(exchange_pick_price, exchange_opponent_price)
        if pair:
            sharp_pick_pct = pair[0]

    sharp_signal = _sharp_signal(
        crowd_pick_pct=crowd.get("marq_crowd_pick_pct"),
        sharp_pick_pct=sharp_pick_pct,
    )

    quality_signal = quality.get("quality_signal")

    # Exchange available is stronger than a pure one-book thin sample.
    if exchange.get("marq_exchange_available") and quality_signal in ("THIN", "NO MARKET DATA"):
        quality_signal = "EXCHANGE"

    print(
        "MARQ MARKET VIEW: "
        f"source={market_data.get('source')} "
        f"event_id={market_data.get('event_id')} "
        f"pick={pick} "
        f"crowd={crowd.get('marq_crowd_pick_pct')}/"
        f"{crowd.get('marq_crowd_opponent_pct')} "
        f"move={move.get('marq_move_signal')} "
        f"sharp={sharp_signal} "
        f"quality={quality_signal} "
        f"providers={quality.get('provider_count')} "
        f"median_odds={quality.get('median_odds')} "
        f"spread_pct={quality.get('spread_pct')} "
        f"exchange={exchange.get('marq_exchange_available')}"
    )

    if quality.get("signal") == "NO MARKET DATA" and crowd.get("marq_crowd_pick_pct") is None:
        return _empty_marq(
            reason="market_view_unavailable",
            event_id=market_data.get("event_id"),
            outcome_key=outcome_key,
        )

    current_pick_odds = move.get("marq_current_pick_odds")
    if current_pick_odds is None and pick_odds_values:
        current_pick_odds = _safe_round(_median_or_none(pick_odds_values), 4)

    return {
        "marq_market_view": True,

        # Backward-compatible old fields.
        "marq_ai_score": quality.get("score"),
        "marq_ai_signal": quality.get("signal"),
        "marq_ai_direction": quality.get("direction"),
        "marq_ai_strength": quality.get("strength"),
        "marq_ai_consistency": quality.get("consistency"),
        "marq_ai_reason": "ok",

        "marq_event_id": market_data.get("event_id"),
        "marq_outcome_key": outcome_key,
        "marq_source": market_data.get("source"),
        "marq_market_name": market_data.get("market_name") or "Full time",

        "marq_provider_count": quality.get("provider_count"),
        "marq_market_spread_pct": quality.get("spread_pct"),
        "marq_market_median_odds": quality.get("median_odds"),
        "marq_outlier_count": quality.get("outlier_count"),

        # New MARKET VIEW fields.
        "marq_crowd_player1_pct": crowd.get("marq_crowd_player1_pct"),
        "marq_crowd_player2_pct": crowd.get("marq_crowd_player2_pct"),
        "marq_crowd_pick_pct": crowd.get("marq_crowd_pick_pct"),
        "marq_crowd_opponent_pct": crowd.get("marq_crowd_opponent_pct"),

        "marq_move_signal": move.get("marq_move_signal"),
        "marq_initial_pick_odds": move.get("marq_initial_pick_odds"),
        "marq_current_pick_odds": current_pick_odds,
        "marq_initial_opponent_odds": move.get("marq_initial_opponent_odds"),
        "marq_current_opponent_odds": move.get("marq_current_opponent_odds"),
        "marq_market_move_pct": move.get("marq_market_move_pct"),
        "marq_opponent_move_pct": move.get("marq_opponent_move_pct"),
        "marq_probability_change_pp": None,

        "marq_sharp_signal": sharp_signal,
        "marq_sharp_pick_pct": _safe_round(sharp_pick_pct, 1),
        "marq_quality_signal": quality_signal,
        "marq_clv_status": "PENDING",

        "marq_exchange_available": exchange.get("marq_exchange_available"),
        "marq_exchange_provider": exchange.get("marq_exchange_provider"),
        "marq_exchange_market_id": exchange.get("marq_exchange_market_id"),
        "marq_exchange_total_matched": exchange.get("marq_exchange_total_matched"),
        "marq_exchange_total_available": exchange.get("marq_exchange_total_available"),
        "marq_exchange_pick_price": exchange.get("marq_exchange_pick_price"),
        "marq_exchange_opponent_price": exchange.get("marq_exchange_opponent_price"),

        # Backward-compatible render/debug fields.
        "marq_opening": move.get("marq_initial_pick_odds") or quality.get("median_odds"),
        "marq_latest": current_pick_odds or quality.get("median_odds"),
    }
