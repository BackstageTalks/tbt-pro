"""Market lines provider for Sets/Games value signals.

This module is intentionally separate from MARQ:
- MARQ remains a market view for match winner odds.
- market_lines.py uses the same Bet365 event/markets idea to collect betting
  lines needed by Sets/Games: total sets, total games, tie-break and aces.

It does not calculate sport probabilities by itself. It only:
1. fetches/parses market lines and odds,
2. computes market implied/no-vig helper values,
3. compares existing model probabilities with market prices if those model
   probabilities are already present on a match row.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from corq.name_match import compact_name, name_match_score, normalize_name
except Exception:  # pragma: no cover - import fallback for standalone diagnostics
    def normalize_name(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    def compact_name(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", normalize_name(value))

    def name_match_score(a: Any, b: Any) -> float:
        return 1.0 if normalize_name(a) == normalize_name(b) else 0.0


BET365_HOST = "bet365-api-inplay.p.rapidapi.com"
BET365_EVENTS_PATH = "/bet365/get_prematch_sport_events/tennis"
BET365_MARKETS_PATH = "/bet365/get_prematch_event_with_markets/{event_id}"
DEFAULT_TIMEOUT_SECONDS = 25
MIN_VALID_ODDS = 1.03
MAX_VALID_ODDS = 50.0


@dataclass
class TwoWayLine:
    market: str
    line: Optional[float] = None
    over_odds: Optional[float] = None
    under_odds: Optional[float] = None
    yes_odds: Optional[float] = None
    no_odds: Optional[float] = None
    source: str = "Bet365PrematchAPI"
    raw_group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AcesLines:
    pick_line: Optional[float] = None
    pick_side: Optional[str] = None
    pick_over_odds: Optional[float] = None
    pick_under_odds: Optional[float] = None
    opponent_line: Optional[float] = None
    opponent_side: Optional[str] = None
    opponent_over_odds: Optional[float] = None
    opponent_under_odds: Optional[float] = None
    total_line: Optional[float] = None
    total_side: Optional[str] = None
    total_over_odds: Optional[float] = None
    total_under_odds: Optional[float] = None
    source: str = "Bet365PrematchAPI"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-"):
            return default
        text = str(value).replace(",", ".")
        num = float(text)
        return num
    except Exception:
        return default


def valid_odds(value: Any) -> Optional[float]:
    num = as_float(value)
    if num is None:
        return None
    if MIN_VALID_ODDS <= num <= MAX_VALID_ODDS:
        return num
    return None


def implied_probability(decimal_odds: Any) -> Optional[float]:
    odds = valid_odds(decimal_odds)
    if odds is None:
        return None
    return 1.0 / odds


def no_vig_two_way(over_odds: Any, under_odds: Any) -> Tuple[Optional[float], Optional[float]]:
    raw_over = implied_probability(over_odds)
    raw_under = implied_probability(under_odds)
    if raw_over is None or raw_under is None:
        return None, None
    total = raw_over + raw_under
    if total <= 0:
        return None, None
    return raw_over / total, raw_under / total


def pct(value: Any) -> Optional[float]:
    num = as_float(value)
    if num is None:
        return None
    return num / 100.0 if num > 1.0 else num


def _extract_line(text: Any) -> Optional[float]:
    raw = str(text or "").replace(",", ".")
    # Prefer common half-game/set lines.
    matches = re.findall(r"(?:^|\D)(\d{1,2}(?:\.5|\.0)?)(?:\D|$)", raw)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except Exception:
        return None


def _side_from_text(text: Any) -> Optional[str]:
    low = str(text or "").lower()
    if re.search(r"\b(over|ov|o)\b", low):
        return "Over"
    if re.search(r"\b(under|un|u)\b", low):
        return "Under"
    if re.search(r"\b(yes|y)\b", low):
        return "Yes"
    if re.search(r"\b(no|n)\b", low):
        return "No"
    return None


def _walk_dicts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _name_from_event(event: Dict[str, Any], side: int) -> str:
    keys = (
        ("team1", "home", "homeTeam", "player1", "name1")
        if side == 1
        else ("team2", "away", "awayTeam", "player2", "name2")
    )
    for key in keys:
        val = event.get(key)
        if isinstance(val, dict):
            for inner in ("name", "shortName", "fullName", "teamName"):
                if val.get(inner):
                    return str(val.get(inner))
        elif val:
            return str(val)
    return ""


def _event_start_date(event: Dict[str, Any]) -> str:
    for key in ("startTime", "start_time", "time", "date", "eventTime"):
        val = event.get(key)
        if not val:
            continue
        text = str(val)
        if text.isdigit() and len(text) >= 10:
            try:
                return datetime.fromtimestamp(int(text[:10]), tz=timezone.utc).date().isoformat()
            except Exception:
                pass
        if len(text) >= 10:
            return text[:10]
    return ""


def event_match_score(event: Dict[str, Any], player1: str, player2: str, date: Optional[str] = None) -> float:
    e1 = _name_from_event(event, 1)
    e2 = _name_from_event(event, 2)
    if not (e1 and e2 and player1 and player2):
        return 0.0
    direct = (name_match_score(player1, e1) + name_match_score(player2, e2)) / 2.0
    reverse = (name_match_score(player1, e2) + name_match_score(player2, e1)) / 2.0
    score = max(direct, reverse)
    if date:
        event_date = _event_start_date(event)
        if event_date and event_date[:10] != str(date)[:10]:
            score -= 0.12
    return max(0.0, min(1.0, score))


class Bet365MarketLinesClient:
    def __init__(self, rapidapi_key: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.rapidapi_key = rapidapi_key or os.getenv("RAPIDAPI_KEY")
        self.timeout = timeout
        self.last_debug: List[str] = []

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self.rapidapi_key:
            raise RuntimeError("Missing RAPIDAPI_KEY")
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        url = f"https://{BET365_HOST}{path}{query}"
        req = urllib.request.Request(
            url,
            headers={
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": BET365_HOST,
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return body

    def get_tennis_events(self) -> List[Dict[str, Any]]:
        data = self._request(BET365_EVENTS_PATH)
        rows = _coerce_rows(data)
        self.last_debug.append(f"Bet365 prematch tennis events count={len(rows)}")
        return rows

    def find_event(self, player1: str, player2: str, date: Optional[str] = None, min_score: float = 0.78) -> Optional[Dict[str, Any]]:
        best: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)
        for event in self.get_tennis_events():
            score = event_match_score(event, player1, player2, date=date)
            if score > best[0]:
                best = (score, event)
        if best[1] is not None and best[0] >= min_score:
            self.last_debug.append(f"Bet365 event matched score={best[0]:.3f}")
            return best[1]
        self.last_debug.append(f"Bet365 event missing best_score={best[0]:.3f}")
        return None

    def get_event_markets(self, event_id: Any) -> Any:
        path = BET365_MARKETS_PATH.format(event_id=event_id)
        return self._request(path)

    def fetch_match_market_lines(self, match: Dict[str, Any]) -> Dict[str, Any]:
        player1 = str(match.get("player1") or match.get("home") or "")
        player2 = str(match.get("player2") or match.get("away") or "")
        date = str(match.get("date") or match.get("snapshot_date") or match.get("match_date") or "")[:10] or None
        event_id = match.get("bet365_event_id")

        event = None
        if not event_id:
            event = self.find_event(player1, player2, date=date)
            event_id = _first_present(
                event.get("eventId") if isinstance(event, dict) else None,
                event.get("id") if isinstance(event, dict) else None,
                event.get("event_id") if isinstance(event, dict) else None,
            )
        if not event_id:
            return {
                "market_lines_available": False,
                "market_lines_status": "BET365_EVENT_NOT_FOUND",
                "market_lines_debug": list(self.last_debug),
            }

        markets = self.get_event_markets(event_id)
        parsed = parse_bet365_market_lines(markets, match=match)
        parsed.update({
            "market_lines_available": True,
            "market_lines_source": "Bet365PrematchAPI",
            "bet365_event_id": str(event_id),
            "market_lines_debug": list(self.last_debug),
        })
        return parsed


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _coerce_rows(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("results", "events", "data", "rows", "items", "list"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _market_group_text(node: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("group", "groupName", "market", "marketName", "name", "title", "type", "label"):
        val = node.get(key)
        if isinstance(val, str):
            parts.append(val)
    return " ".join(parts).lower()


def _outcome_name(node: Dict[str, Any]) -> str:
    for key in ("name", "label", "header", "displayName", "selection", "participant", "team"):
        val = node.get(key)
        if isinstance(val, dict):
            if val.get("name"):
                return str(val.get("name"))
        elif val:
            return str(val)
    return ""


def _outcome_price(node: Dict[str, Any]) -> Optional[float]:
    for key in ("coef", "odds", "price", "decimal", "decimalOdds", "od"):
        odds = valid_odds(node.get(key))
        if odds is not None:
            return odds
    return None


def _market_kind(group_text: str) -> Optional[str]:
    g = group_text.lower()
    if "total" in g and "set" in g:
        return "sets_total"
    if "total" in g and "game" in g:
        return "total_games"
    if "tie" in g and ("break" in g or "breaker" in g):
        return "tie_break"
    if "tiebreak" in g:
        return "tie_break"
    if "ace" in g and "total" in g:
        return "total_aces"
    if "ace" in g:
        return "player_aces"
    return None


def _collect_outcomes(market_node: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for node in _walk_dicts(market_node):
        price = _outcome_price(node)
        if price is None:
            continue
        name = _outcome_name(node)
        side = _side_from_text(name or node.get("na") or node.get("type"))
        line = _extract_line(name) or _extract_line(node.get("handicap")) or _extract_line(node.get("line"))
        rows.append({"name": name, "side": side, "line": line, "odds": price, "raw": node})
    return rows


def _best_two_way_line(market: str, market_nodes: List[Dict[str, Any]]) -> Optional[TwoWayLine]:
    candidates: List[TwoWayLine] = []
    for node in market_nodes:
        group = _market_group_text(node)
        outcomes = _collect_outcomes(node)
        by_line: Dict[Optional[float], Dict[str, float]] = {}
        for outcome in outcomes:
            side = outcome.get("side")
            if side not in {"Over", "Under", "Yes", "No"}:
                continue
            line = outcome.get("line")
            by_line.setdefault(line, {})[side] = outcome["odds"]
        for line, sides in by_line.items():
            if market == "tie_break":
                if "Yes" in sides and "No" in sides:
                    candidates.append(TwoWayLine(market=market, line=line, yes_odds=sides.get("Yes"), no_odds=sides.get("No"), raw_group=group))
            elif "Over" in sides and "Under" in sides:
                candidates.append(TwoWayLine(market=market, line=line, over_odds=sides.get("Over"), under_odds=sides.get("Under"), raw_group=group))
    if not candidates:
        return None
    # Prefer common lines and lowest overround proxy.
    def sort_key(line: TwoWayLine) -> Tuple[int, float]:
        has_half = 0 if line.line is not None and abs(line.line % 1 - 0.5) < 0.01 else 1
        raw = 0.0
        if line.over_odds and line.under_odds:
            raw = abs((1 / line.over_odds + 1 / line.under_odds) - 1.0)
        elif line.yes_odds and line.no_odds:
            raw = abs((1 / line.yes_odds + 1 / line.no_odds) - 1.0)
        return has_half, raw
    return sorted(candidates, key=sort_key)[0]


def _parse_aces(markets: Dict[str, List[Dict[str, Any]]], match: Dict[str, Any]) -> AcesLines:
    aces = AcesLines()
    pick = str(match.get("pick") or match.get("player") or match.get("player1") or "")
    opponent = str(match.get("opponent") or match.get("opp") or match.get("player2") or "")

    total = _best_two_way_line("total_aces", markets.get("total_aces", []))
    if total:
        aces.total_line = total.line
        aces.total_over_odds = total.over_odds
        aces.total_under_odds = total.under_odds
        aces.total_side = _model_side_from_projection(match.get("total_aces_projection"), total.line)

    for node in markets.get("player_aces", []):
        group = _market_group_text(node)
        target = "pick" if name_match_score(group, pick) >= name_match_score(group, opponent) else "opponent"
        line = _best_two_way_line("player_aces", [node])
        if not line:
            continue
        side = _model_side_from_projection(
            match.get("pick_aces_projection") if target == "pick" else match.get("opponent_aces_projection"),
            line.line,
        )
        if target == "pick":
            aces.pick_line = line.line
            aces.pick_over_odds = line.over_odds
            aces.pick_under_odds = line.under_odds
            aces.pick_side = side
        else:
            aces.opponent_line = line.line
            aces.opponent_over_odds = line.over_odds
            aces.opponent_under_odds = line.under_odds
            aces.opponent_side = side
    return aces


def _model_side_from_projection(projection: Any, line: Optional[float]) -> Optional[str]:
    proj = as_float(projection)
    if proj is None or line is None:
        return None
    return "Over" if proj >= line else "Under"


def parse_bet365_market_lines(markets_payload: Any, match: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    match = match or {}
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "sets_total": [],
        "total_games": [],
        "tie_break": [],
        "total_aces": [],
        "player_aces": [],
    }
    for node in _walk_dicts(markets_payload):
        group = _market_group_text(node)
        kind = _market_kind(group)
        if kind:
            grouped.setdefault(kind, []).append(node)

    sets_total = _best_two_way_line("sets_total", grouped.get("sets_total", []))
    total_games = _best_two_way_line("total_games", grouped.get("total_games", []))
    tie_break = _best_two_way_line("tie_break", grouped.get("tie_break", []))
    aces = _parse_aces(grouped, match)

    output: Dict[str, Any] = {
        "sets_total_market": sets_total.to_dict() if sets_total else None,
        "total_games_market": total_games.to_dict() if total_games else None,
        "tie_break_market": tie_break.to_dict() if tie_break else None,
        "aces_markets": aces.to_dict(),
        "market_lines_parsed_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if sets_total:
        output.update({
            "sets_o25_line": sets_total.line,
            "sets_o25_over_odds": sets_total.over_odds,
            "sets_o25_under_odds": sets_total.under_odds,
        })
    if total_games:
        output.update({
            "total_games_line": total_games.line,
            "total_games_over_odds": total_games.over_odds,
            "total_games_under_odds": total_games.under_odds,
        })
    if tie_break:
        output.update({
            "tb_yes_odds": tie_break.yes_odds,
            "tb_no_odds": tie_break.no_odds,
        })
    output.update(aces.to_dict())
    return output


def edge_from_probability(model_probability: Any, odds: Any, paired_odds: Any = None) -> Optional[float]:
    model_p = pct(model_probability)
    if model_p is None:
        return None
    if paired_odds is not None:
        no_vig_p, _ = no_vig_two_way(odds, paired_odds)
        market_p = no_vig_p
    else:
        market_p = implied_probability(odds)
    if market_p is None:
        return None
    return model_p - market_p


def _format_selection(side: Optional[str], line: Optional[float], label: str) -> Optional[str]:
    if not side or line is None:
        return None
    short = "O" if side == "Over" else "U" if side == "Under" else side
    return f"{label} {short}{line:g}"


def build_sets_games_value_candidates(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return real value candidates only when market odds are available.

    Model-only projections belong to Best Bet, not Value Bet. This function
    deliberately skips candidates with missing odds or missing edge.
    """
    candidates: List[Dict[str, Any]] = []

    def add_candidate(item: Dict[str, Any]) -> None:
        if item.get("market_odds") is None:
            return
        if item.get("edge") is None:
            return
        candidates.append(item)

    sets_line = as_float(row.get("sets_o25_line")) or 2.5
    sets_prob = row.get("sets_o25_probability") or row.get("sets_over_25_probability")
    sets_edge = edge_from_probability(sets_prob, row.get("sets_o25_over_odds"), row.get("sets_o25_under_odds"))
    add_candidate({
        "market": "sets_total",
        "selection": f"Over {sets_line:g} sets",
        "model_probability": pct(sets_prob),
        "market_odds": as_float(row.get("sets_o25_over_odds")),
        "edge": sets_edge,
    })

    games_line = as_float(row.get("total_games_line"))
    games_proj = as_float(row.get("projected_total_games"))
    games_side = _model_side_from_projection(games_proj, games_line)
    if games_side and games_line is not None:
        odds_key = "total_games_over_odds" if games_side == "Over" else "total_games_under_odds"
        opp_key = "total_games_under_odds" if games_side == "Over" else "total_games_over_odds"
        prob_key = "total_games_over_probability" if games_side == "Over" else "total_games_under_probability"
        prob = row.get(prob_key)
        edge = edge_from_probability(prob, row.get(odds_key), row.get(opp_key))
        add_candidate({
            "market": "total_games",
            "selection": f"{games_side} {games_line:g} games",
            "model_probability": pct(prob),
            "market_odds": as_float(row.get(odds_key)),
            "edge": edge,
        })

    tb_prob = row.get("tb_probability") or row.get("tie_break_probability")
    tb_edge = edge_from_probability(tb_prob, row.get("tb_yes_odds"), row.get("tb_no_odds"))
    add_candidate({
        "market": "tie_break",
        "selection": "Tie-break Yes",
        "model_probability": pct(tb_prob),
        "market_odds": as_float(row.get("tb_yes_odds")),
        "edge": tb_edge,
    })

    for prefix, label in (("pick", "Pick aces"), ("opponent", "Opponent aces"), ("total", "Total aces")):
        line = as_float(row.get(f"{prefix}_aces_line"))
        side = row.get(f"{prefix}_aces_side")
        selection = _format_selection(side, line, label)
        if not selection:
            continue
        odds_key = f"{prefix}_aces_over_odds" if side == "Over" else f"{prefix}_aces_under_odds"
        opp_key = f"{prefix}_aces_under_odds" if side == "Over" else f"{prefix}_aces_over_odds"
        prob_key = f"{prefix}_aces_over_probability" if side == "Over" else f"{prefix}_aces_under_probability"
        prob = row.get(prob_key)
        edge = edge_from_probability(prob, row.get(odds_key), row.get(opp_key))
        add_candidate({
            "market": f"{prefix}_aces",
            "selection": selection,
            "model_probability": pct(prob),
            "market_odds": as_float(row.get(odds_key)),
            "edge": edge,
        })

    def sort_key(item: Dict[str, Any]) -> Tuple[float, float]:
        edge = item.get("edge")
        prob = item.get("model_probability")
        return (float(edge) if edge is not None else -999.0, float(prob) if prob is not None else -999.0)

    return sorted(candidates, key=sort_key, reverse=True)

def enrich_match_with_market_lines(match: Dict[str, Any], client: Optional[Bet365MarketLinesClient] = None) -> Dict[str, Any]:
    client = client or Bet365MarketLinesClient()
    enriched = dict(match)
    try:
        market_lines = client.fetch_match_market_lines(match)
        enriched.update(market_lines)
    except Exception as exc:
        enriched.update({
            "market_lines_available": False,
            "market_lines_status": "ERROR",
            "market_lines_error": str(exc),
        })

    value_candidates = build_sets_games_value_candidates(enriched)
    enriched["sets_games_value_candidates"] = value_candidates
    if value_candidates and value_candidates[0].get("selection"):
        enriched["sets_games_best_value"] = value_candidates[0]["selection"]
        enriched["sets_games_best_value_edge"] = value_candidates[0].get("edge")
    else:
        enriched["sets_games_best_value"] = "Pending lines"
    return enriched

# ---------------------------------------------------------------------------
# Adapted Sets/Games model helpers from the legacy project
# ---------------------------------------------------------------------------
# These helpers are kept in marq/market_lines.py because the current project has
# a top-level marq package with market_lines.py and we avoid creating legacy
# filenames.  They are pure helpers: they do not fake missing market/model data.

_SET_MARKET_CACHE: Dict[int, Dict[str, Any]] = {}
AVG_POINTS_PER_SERVICE_GAME = 6.2


def clamp_value(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_probability_value(value: Any) -> Optional[float]:
    number = as_float(value)
    if number is None:
        return None
    return number / 100.0 if number > 1.0 else number


def normalize_pair_probability(p1_odds: Optional[float], p2_odds: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    p1_raw = implied_probability(p1_odds)
    p2_raw = implied_probability(p2_odds)
    if p1_raw is None or p2_raw is None:
        return None, None
    total = p1_raw + p2_raw
    if total <= 0:
        return None, None
    return p1_raw / total, p2_raw / total


def _choice_decimal(choice: Dict[str, Any]) -> Optional[float]:
    if not isinstance(choice, dict):
        return None
    for key in ("fractionalValue", "initialFractionalValue"):
        value = choice.get(key)
        if value:
            decimal = _fractional_to_decimal_local(value)
            if decimal and decimal > 1.0:
                return decimal
    for key in ("decimalValue", "value", "price", "odds", "coef"):
        decimal = valid_odds(choice.get(key))
        if decimal is not None:
            return decimal
    return None


def _choice_initial_decimal(choice: Dict[str, Any]) -> Optional[float]:
    if not isinstance(choice, dict):
        return None
    for key in ("initialFractionalValue", "openingFractionalValue"):
        value = choice.get(key)
        if value:
            decimal = _fractional_to_decimal_local(value)
            if decimal and decimal > 1.0:
                return decimal
    for key in ("initialDecimalValue", "openingDecimalValue"):
        decimal = valid_odds(choice.get(key))
        if decimal is not None:
            return decimal
    return None


def _fractional_to_decimal_local(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 1 else None
    text = str(value).strip().replace(",", ".")
    if "/" in text:
        try:
            left, right = text.split("/", 1)
            denominator = float(right.strip())
            if denominator == 0:
                return None
            return round(1.0 + float(left.strip()) / denominator, 5)
        except Exception:
            return None
    return valid_odds(text)


def _choice_change(choice: Dict[str, Any]) -> Optional[float]:
    return as_float(choice.get("change")) if isinstance(choice, dict) else None


def _market_choices_pair_details(market: Dict[str, Any]) -> Dict[str, Any]:
    choices = market.get("choices") or market.get("outcomes")
    output: Dict[str, Any] = {
        "p1_odds": None,
        "p2_odds": None,
        "p1_initial_odds": None,
        "p2_initial_odds": None,
        "p1_change": None,
        "p2_change": None,
    }
    if not isinstance(choices, list) or len(choices) < 2:
        return output
    first = choices[0] if isinstance(choices[0], dict) else {}
    second = choices[1] if isinstance(choices[1], dict) else {}
    output["p1_odds"] = _choice_decimal(first)
    output["p2_odds"] = _choice_decimal(second)
    output["p1_initial_odds"] = _choice_initial_decimal(first)
    output["p2_initial_odds"] = _choice_initial_decimal(second)
    output["p1_change"] = _choice_change(first)
    output["p2_change"] = _choice_change(second)
    return output


def _find_over_under_details(market: Dict[str, Any]) -> Dict[str, Any]:
    choices = market.get("choices") or market.get("outcomes")
    output: Dict[str, Any] = {
        "over_odds": None,
        "under_odds": None,
        "over_initial_odds": None,
        "under_initial_odds": None,
        "over_change": None,
        "under_change": None,
    }
    if not isinstance(choices, list) or len(choices) < 2:
        return output
    for idx, choice in enumerate(choices):
        if not isinstance(choice, dict):
            continue
        name = str(choice.get("name") or choice.get("choiceName") or choice.get("label") or "").lower()
        if "over" in name or (idx == 0 and output["over_odds"] is None):
            key = "over"
        elif "under" in name or idx == 1:
            key = "under"
        else:
            continue
        output[f"{key}_odds"] = _choice_decimal(choice)
        output[f"{key}_initial_odds"] = _choice_initial_decimal(choice)
        output[f"{key}_change"] = _choice_change(choice)
    return output


def _normalize_tennisapi_markets_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    def looks_like_market(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if value.get("choices") or value.get("outcomes"):
            return True
        return any(k in value for k in ("marketName", "marketId", "marketGroup", "marketPeriod"))

    direct_keys = (
        "markets",
        "odds",
        "featuredOdds",
        "featured_odds",
        "matchOdds",
        "bettingOdds",
        "winningOdds",
        "items",
        "results",
    )
    found: List[Dict[str, Any]] = []

    def visit(value: Any, depth: int = 0) -> None:
        if depth > 5 or value is None:
            return
        if isinstance(value, list):
            market_like = [item for item in value if looks_like_market(item)]
            if market_like:
                found.extend(market_like)
                return
            for item in value:
                visit(item, depth + 1)
            return
        if not isinstance(value, dict):
            return
        if looks_like_market(value):
            found.append(value)
            return
        for key in direct_keys:
            child = value.get(key)
            if child is not None:
                visit(child, depth + 1)
        featured = value.get("featured")
        if isinstance(featured, dict):
            for child in featured.values():
                visit(child, depth + 1)
        data = value.get("data")
        if data is not None:
            visit(data, depth + 1)

    visit(payload)
    unique: List[Dict[str, Any]] = []
    seen = set()
    for market in found:
        sig = (
            str(market.get("marketId") or ""),
            str(market.get("marketName") or market.get("name") or ""),
            str(market.get("marketGroup") or market.get("group") or ""),
            str(market.get("marketPeriod") or ""),
            str(market.get("sourceId") or ""),
        )
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(market)
    return unique


def parse_tennisapi_set_markets(payload: Dict[str, Any], event_id: Optional[int] = None) -> Dict[str, Any]:
    """Parse TennisApi market ids used by the legacy Sets/Games model.

    Known legacy mapping:
    - marketId 1: match winner
    - marketId 11: first set winner
    - marketId 12: total games
    - marketId 13: tie break
    """
    markets = _normalize_tennisapi_markets_payload(payload)
    output: Dict[str, Any] = {
        "event_id": event_id or payload.get("eventId") if isinstance(payload, dict) else event_id,
        "match_winner": None,
        "first_set_winner": None,
        "total_games": None,
        "total_sets": None,
        "tie_break": None,
        "raw_market_count": len(markets),
    }
    for market in markets:
        if not isinstance(market, dict):
            continue
        market_id = market.get("marketId")
        market_name = str(market.get("marketName") or market.get("name") or "").lower()
        market_period = str(market.get("marketPeriod") or "").lower()
        market_group = str(market.get("marketGroup") or market.get("group") or "")
        if market_id == 1 or ("full time" in market_name and "match" in market_period):
            details = _market_choices_pair_details(market)
            p1, p2 = details.get("p1_odds"), details.get("p2_odds")
            p1_prob, p2_prob = normalize_pair_probability(p1, p2)
            if p1 and p2:
                output["match_winner"] = {**details, "p1_probability": p1_prob, "p2_probability": p2_prob, "market_id": market_id, "market_name": market_name, "market_group": market_group, "market_period": market_period}
        elif market_id == 11 or "first set winner" in market_name:
            details = _market_choices_pair_details(market)
            p1, p2 = details.get("p1_odds"), details.get("p2_odds")
            p1_prob, p2_prob = normalize_pair_probability(p1, p2)
            if p1 and p2:
                output["first_set_winner"] = {**details, "p1_probability": p1_prob, "p2_probability": p2_prob, "market_id": market_id, "market_name": market_name, "market_group": market_group, "market_period": market_period}
        elif market_id == 12 or "total games" in market_name:
            line = as_float(market.get("choiceGroup") or market.get("line") or market.get("handicap"))
            details = _find_over_under_details(market)
            over_odds, under_odds = details.get("over_odds"), details.get("under_odds")
            over_prob, under_prob = normalize_pair_probability(over_odds, under_odds)
            if line is not None and over_odds and under_odds:
                output["total_games"] = {**details, "line": line, "over_probability": over_prob, "under_probability": under_prob, "market_id": market_id, "market_name": market_name, "market_group": market_group, "market_period": market_period}
        elif "total sets" in market_name or "sets total" in market_name:
            line = as_float(market.get("choiceGroup") or market.get("line") or market.get("handicap"))
            details = _find_over_under_details(market)
            over_odds, under_odds = details.get("over_odds"), details.get("under_odds")
            over_prob, under_prob = normalize_pair_probability(over_odds, under_odds)
            if line is not None and over_odds and under_odds:
                output["total_sets"] = {**details, "line": line, "over_probability": over_prob, "under_probability": under_prob, "market_id": market_id, "market_name": market_name, "market_group": market_group, "market_period": market_period}
        elif market_id == 13 or "tie break" in market_name or "tiebreak" in market_name:
            details = _market_choices_pair_details(market)
            yes_odds, no_odds = details.get("p1_odds"), details.get("p2_odds")
            yes_prob, no_prob = normalize_pair_probability(yes_odds, no_odds)
            if yes_odds and no_odds:
                output["tie_break"] = {"yes_odds": yes_odds, "no_odds": no_odds, "yes_initial_odds": details.get("p1_initial_odds"), "no_initial_odds": details.get("p2_initial_odds"), "yes_change": details.get("p1_change"), "no_change": details.get("p2_change"), "yes_probability": yes_prob, "no_probability": no_prob, "market_id": market_id, "market_name": market_name, "market_group": market_group, "market_period": market_period}
    return output


def get_tennisapi_set_markets(event_id: Optional[int], force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch and parse TennisAPI PRO markets for Sets/Games.

    Primary source is marq.provider.fetch_provider_odds(), which now probes
    getAllOddsForEvent plus PRO fallback endpoints. Legacy TennisApiClient
    remains as a fallback for older repo branches.
    """
    if not event_id:
        return {}
    event_id_int = int(event_id)
    if not force_refresh and event_id_int in _SET_MARKET_CACHE:
        return _SET_MARKET_CACHE[event_id_int]

    payload: Dict[str, Any] = {}
    try:
        from marq import provider as provider_mod  # type: ignore
        for provider_id in getattr(provider_mod, "DEFAULT_PROVIDER_IDS", [1]):
            fetched = provider_mod.fetch_provider_odds(str(event_id_int), int(provider_id), force_refresh=force_refresh)
            parsed = parse_tennisapi_set_markets(fetched or {}, event_id=event_id_int)
            if parsed.get("raw_market_count"):
                _SET_MARKET_CACHE[event_id_int] = parsed
                return parsed
    except Exception:
        pass

    try:
        try:
            from thinq.loaders.rapidapi_client import TennisApiClient  # type: ignore
        except Exception:
            from tennisapi_client import TennisApiClient  # type: ignore
        client = TennisApiClient()
        payload = client.get_all_odds_for_event(event_id_int) or {}
        parsed = parse_tennisapi_set_markets(payload, event_id=event_id_int)
        _SET_MARKET_CACHE[event_id_int] = parsed
        return parsed
    except Exception:
        return {}


def _infer_bo(match: Dict[str, Any]) -> int:
    try:
        best_of = int(match.get("best_of") or 3)
        return 5 if best_of == 5 else 3
    except Exception:
        return 3


def _infer_is_doubles(match: Dict[str, Any]) -> bool:
    text = " ".join(str(match.get(k) or "") for k in ("match", "tournament", "category")).lower()
    return "doubles" in text


def _market_set_pressure(best_of: int, total_games: Optional[Dict[str, Any]], tie_break: Optional[Dict[str, Any]]) -> float:
    pressure = 0.50
    if isinstance(total_games, dict):
        line = as_float(total_games.get("line"))
        over_prob = normalize_probability_value(total_games.get("over_probability"))
        if best_of == 5:
            if line is not None:
                pressure += (line - 38.5) / 18.0
        else:
            if line is not None:
                pressure += (line - 22.0) / 10.0
        if over_prob is not None:
            pressure += (over_prob - 0.50) * 0.60
    if isinstance(tie_break, dict):
        tie_prob = normalize_probability_value(tie_break.get("yes_probability"))
        if tie_prob is not None:
            pressure += (tie_prob - 0.35) * 0.35
    return clamp_value(pressure, 0.05, 0.95)


def _dominance_score(match_probability: Optional[float], first_set_probability: Optional[float]) -> float:
    p_match = match_probability if match_probability is not None else 0.5
    p_first = first_set_probability if first_set_probability is not None else p_match
    return clamp_value(((p_match - 0.50) * 1.3) + ((p_first - 0.50) * 0.7), -0.45, 0.45)


def _normalize_dist(dist: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(v, 0.0) for v in dist.values())
    if total <= 0:
        return dist
    return {k: round(max(v, 0.0) / total, 4) for k, v in dist.items()}


def _bo3_distribution(winner_side: str, match_prob: float, first_set_prob: Optional[float], pressure: float) -> Dict[str, float]:
    dom = _dominance_score(match_prob, first_set_prob)
    three_sets = clamp_value(0.30 + pressure * 0.34 - max(dom, 0) * 0.20, 0.18, 0.62)
    fav_win = clamp_value(match_prob, 0.35, 0.85)
    fav_straight = clamp_value((1 - three_sets) * (0.55 + max(dom, 0) * 0.70), 0.20, 0.70)
    fav_deciding = clamp_value(three_sets * fav_win, 0.08, 0.45)
    dog_deciding = clamp_value(three_sets * (1 - fav_win), 0.05, 0.35)
    dog_straight = max(0.02, 1.0 - fav_straight - fav_deciding - dog_deciding)
    if winner_side == "p1":
        dist = {"2-0": fav_straight, "2-1": fav_deciding, "1-2": dog_deciding, "0-2": dog_straight}
    else:
        dist = {"0-2": fav_straight, "1-2": fav_deciding, "2-1": dog_deciding, "2-0": dog_straight}
    return _normalize_dist(dist)


def _bo5_distribution(winner_side: str, match_prob: float, first_set_prob: Optional[float], pressure: float) -> Dict[str, float]:
    dom = _dominance_score(match_prob, first_set_prob)
    five_sets = clamp_value(0.16 + pressure * 0.28 - max(dom, 0) * 0.10, 0.08, 0.42)
    four_sets = clamp_value(0.30 + pressure * 0.10 - abs(dom) * 0.05, 0.20, 0.45)
    three_sets = clamp_value(1.0 - five_sets - four_sets, 0.20, 0.58)
    fav_win = clamp_value(match_prob, 0.35, 0.88)
    fav_three = three_sets * (0.62 + max(dom, 0) * 0.60)
    dog_three = max(0.01, three_sets - fav_three)
    fav_four = four_sets * fav_win
    dog_four = four_sets * (1 - fav_win)
    fav_five = five_sets * fav_win
    dog_five = five_sets * (1 - fav_win)
    if winner_side == "p1":
        dist = {"3-0": fav_three, "3-1": fav_four, "3-2": fav_five, "2-3": dog_five, "1-3": dog_four, "0-3": dog_three}
    else:
        dist = {"0-3": fav_three, "1-3": fav_four, "2-3": fav_five, "3-2": dog_five, "3-1": dog_four, "3-0": dog_three}
    return _normalize_dist(dist)


def _expected_sets_from_dist(dist: Dict[str, float]) -> float:
    total = 0.0
    for score, prob in dist.items():
        try:
            a, b = score.split("-")
            total += (int(a) + int(b)) * float(prob)
        except Exception:
            pass
    return round(total, 2)


def _probability_of_max_sets(dist: Dict[str, float], best_of: int) -> float:
    max_sets = 5 if best_of == 5 else 3
    total = 0.0
    for score, prob in dist.items():
        try:
            a, b = score.split("-")
            if int(a) + int(b) == max_sets:
                total += float(prob)
        except Exception:
            pass
    return round(total, 4)


def _most_likely_score(dist: Dict[str, float]) -> str:
    if not dist:
        return "-"
    return max(dist.items(), key=lambda item: item[1])[0]


def _pct_points(value: Any) -> Optional[float]:
    num = as_float(value)
    if num is None:
        return None
    return num * 100.0 if 0 < num <= 1.0 else num


def _prob_from_pct(value: Any) -> Optional[float]:
    num = _pct_points(value)
    if num is None:
        return None
    return clamp_value(num / 100.0, 0.0, 1.0)


def _average_present(values: Iterable[Any]) -> Optional[float]:
    clean = [_pct_points(v) for v in values]
    clean = [v for v in clean if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _standard_half_line(projection: float, low: float, high: float) -> float:
    value = max(low, min(high, projection))
    return round(value * 2.0) / 2.0


def _over_probability_from_projection(projection: float, line: float, scale: float) -> float:
    # Smooth deterministic model probability. The input projection must come
    # from real TA/model data; this function only converts projection to line P.
    import math
    z = (projection - line) / max(scale, 0.01)
    return round(clamp_value(1.0 / (1.0 + math.exp(-z)), 0.05, 0.95), 4)


def _wl_probability(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if "-" not in text:
        return None
    try:
        left, right = text.split("-", 1)
        wins = float(left.strip())
        losses = float(right.strip())
        total = wins + losses
        if total <= 0:
            return None
        return wins / total
    except Exception:
        return None


def _ta_model_available(match: Dict[str, Any]) -> bool:
    required = (
        "ta_pick_hold_pct", "ta_opp_hold_pct", "ta_pick_break_pct", "ta_opp_break_pct",
        "ta_pick_game_pct", "ta_opp_game_pct",
    )
    return sum(1 for key in required if _pct_points(match.get(key)) is not None) >= 4


def _ta_set_pressure(match: Dict[str, Any], best_of: int) -> float:
    pressure = 0.50
    p_game = _pct_points(match.get("ta_pick_game_pct"))
    o_game = _pct_points(match.get("ta_opp_game_pct"))
    p_set = _pct_points(match.get("ta_pick_set_pct"))
    o_set = _pct_points(match.get("ta_opp_set_pct"))
    p_hold = _pct_points(match.get("ta_pick_hold_pct"))
    o_hold = _pct_points(match.get("ta_opp_hold_pct"))
    p_break = _pct_points(match.get("ta_pick_break_pct"))
    o_break = _pct_points(match.get("ta_opp_break_pct"))

    if p_game is not None and o_game is not None:
        pressure += (8.0 - abs(p_game - o_game)) / 35.0
    if p_set is not None and o_set is not None:
        pressure += (10.0 - abs(p_set - o_set)) / 45.0
    avg_hold = _average_present((p_hold, o_hold))
    avg_break = _average_present((p_break, o_break))
    if avg_hold is not None:
        pressure += (avg_hold - 60.0) / 38.0
    if avg_break is not None:
        pressure -= (avg_break - 38.0) / 55.0
    if best_of == 5:
        pressure = 0.50 + (pressure - 0.50) * 0.75
    return clamp_value(pressure, 0.05, 0.95)



def _fallback_total_games_projection(best_of: int, expected_sets: float, match_probability: Optional[float] = None) -> float:
    """Fallback total-games projection when TA hold/break detail is missing.

    This uses already available set distribution and favorite strength. It is
    intentionally labelled as fallback by the caller and should not be treated
    as a market value signal.
    """
    favorite_strength = abs((match_probability if match_probability is not None else 0.5) - 0.5)
    if best_of == 5:
        games_per_set = 9.75 - favorite_strength * 1.10
        return round(clamp_value(games_per_set * expected_sets, 27.0, 53.5), 1)
    games_per_set = 9.35 - favorite_strength * 0.90
    return round(clamp_value(games_per_set * expected_sets, 17.0, 29.5), 1)

def _ta_total_games_projection(match: Dict[str, Any], best_of: int, expected_sets: float) -> Optional[float]:
    if not _ta_model_available(match):
        return None
    p_game = _pct_points(match.get("ta_pick_game_pct"))
    o_game = _pct_points(match.get("ta_opp_game_pct"))
    p_hold = _pct_points(match.get("ta_pick_hold_pct"))
    o_hold = _pct_points(match.get("ta_opp_hold_pct"))
    p_break = _pct_points(match.get("ta_pick_break_pct"))
    o_break = _pct_points(match.get("ta_opp_break_pct"))
    p_tpw = _pct_points(match.get("ta_pick_tpw_pct"))
    o_tpw = _pct_points(match.get("ta_opp_tpw_pct"))

    avg_hold = _average_present((p_hold, o_hold)) or 60.0
    avg_break = _average_present((p_break, o_break)) or 38.0
    game_gap = abs((p_game or 50.0) - (o_game or 50.0))
    strength_gap = abs((p_tpw or 50.0) - (o_tpw or 50.0))

    games_per_set = 9.45
    games_per_set += (avg_hold - 60.0) * 0.045
    games_per_set -= (avg_break - 38.0) * 0.030
    games_per_set -= min(game_gap + strength_gap, 18.0) * 0.035
    games_per_set = clamp_value(games_per_set, 8.4, 11.2)

    projection = games_per_set * expected_sets
    if best_of == 5:
        projection = clamp_value(projection, 27.0, 54.0)
    else:
        projection = clamp_value(projection, 17.0, 29.5)
    return round(projection, 1)


def _ta_tiebreak_probability(match: Dict[str, Any], best_of: int) -> Optional[float]:
    p_hold = _pct_points(match.get("ta_pick_hold_pct"))
    o_hold = _pct_points(match.get("ta_opp_hold_pct"))
    p_break = _pct_points(match.get("ta_pick_break_pct"))
    o_break = _pct_points(match.get("ta_opp_break_pct"))
    p_ace = _pct_points(match.get("ta_pick_ace_pct"))
    o_ace = _pct_points(match.get("ta_opp_ace_pct"))
    if p_hold is None or o_hold is None:
        return None
    avg_hold = (p_hold + o_hold) / 2.0
    avg_break = _average_present((p_break, o_break)) or 38.0
    avg_ace = _average_present((p_ace, o_ace)) or 3.0
    tb = 0.18 + (avg_hold - 58.0) * 0.010 - (avg_break - 38.0) * 0.004 + (avg_ace - 3.0) * 0.012
    for split_key in ("ta_pick_tb_split", "ta_opp_tb_split"):
        split_prob = _wl_probability(match.get(split_key))
        if split_prob is not None:
            # Use TB history as a small availability signal, not as direct H2H truth.
            tb += (split_prob - 0.50) * 0.03
    if best_of == 5:
        tb += 0.10
    return round(clamp_value(tb, 0.08, 0.62), 4)


def _prop_model_line(projection: Optional[float], low: float, high: float, scale: float, label: str) -> Dict[str, Any]:
    if projection is None:
        return {}
    line = _standard_half_line(float(projection), low, high)
    if projection >= line:
        side = "Over"
        probability = _over_probability_from_projection(float(projection), line, scale)
    else:
        side = "Under"
        probability = round(1.0 - _over_probability_from_projection(float(projection), line, scale), 4)
    short = "O" if side == "Over" else "U"
    return {
        "line": line,
        "side": side,
        "selection": f"{short}{line:g}",
        "probability": probability,
        "projection": round(float(projection), 1),
        "label": label,
    }


def _ace_pct_from_value(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", ".")
        number = float(value)
        if 0 < number <= 1:
            number *= 100.0
        # Ace% outside this broad range is usually a malformed value.
        if 0 <= number <= 60:
            return number
    except Exception:
        return None
    return None


def _recursive_find_ace_pct(obj: Any, surface: Optional[str] = None) -> Optional[float]:
    if not isinstance(obj, (dict, list)):
        return None
    preferred_keys = {
        "a%", "ace%", "ace_pct", "ace_percent", "ace_percentage", "ace_rate",
        "aces_pct", "aces_percent", "aces_percentage", "ta_ace_pct", "ta_ace_percent",
        "acePct", "acePercent", "acesPct", "acesPercent",
    }
    if isinstance(obj, dict):
        if surface:
            surf = str(surface).strip().lower()
            for key, value in obj.items():
                if str(key).strip().lower() == surf and isinstance(value, dict):
                    pct_value = _recursive_find_ace_pct(value, surface=None)
                    if pct_value is not None:
                        return pct_value
        for key, value in obj.items():
            key_text = str(key).strip()
            if key_text in preferred_keys or key_text.lower() in preferred_keys:
                pct_value = _ace_pct_from_value(value)
                if pct_value is not None:
                    return pct_value
        for key in ("surface", "surfaces", "splits", "totals", "last52", "last_52", "recent", "current_year", "yearly", "career"):
            pct_value = _recursive_find_ace_pct(obj.get(key), surface=surface)
            if pct_value is not None:
                return pct_value
        for value in obj.values():
            pct_value = _recursive_find_ace_pct(value, surface=surface)
            if pct_value is not None:
                return pct_value
    if isinstance(obj, list):
        for value in obj:
            pct_value = _recursive_find_ace_pct(value, surface=surface)
            if pct_value is not None:
                return pct_value
    return None


def _first_ace_pct(row: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    for key in keys:
        pct_value = _ace_pct_from_value(row.get(key))
        if pct_value is not None:
            return pct_value
    return None


def _ta_aces_projection(match: Dict[str, Any], games: Optional[float]) -> Dict[str, Any]:
    if games is None or games <= 0:
        return {"aces_status": "NO_GAMES_PROJECTION"}
    surface = str(match.get("surface") or match.get("surface_raw") or "") or None
    p_ace = _first_ace_pct(match, (
        "ta_pick_ace_pct", "pick_ace_pct", "pick_aces_pct", "pick_ace_percent",
        "ta_pick_ace_percent", "pick_aces_percent",
    ))
    o_ace = _first_ace_pct(match, (
        "ta_opp_ace_pct", "ta_opponent_ace_pct", "opponent_ace_pct", "opp_ace_pct",
        "opponent_aces_pct", "ta_opp_ace_percent", "opponent_ace_percent",
    ))
    if p_ace is None:
        for key in ("ta_profile_pick", "pick_ta_profile", "ta_pick_profile", "ta_context_pick", "pick_profile"):
            if isinstance(match.get(key), dict):
                p_ace = _recursive_find_ace_pct(match.get(key), surface=surface)
                if p_ace is not None:
                    break
    if o_ace is None:
        for key in ("ta_profile_opponent", "opponent_ta_profile", "ta_opp_profile", "ta_context_opponent", "opponent_profile"):
            if isinstance(match.get(key), dict):
                o_ace = _recursive_find_ace_pct(match.get(key), surface=surface)
                if o_ace is not None:
                    break
    if p_ace is None and isinstance(match.get("ta_context"), dict):
        ctx = match.get("ta_context") or {}
        for key in ("pick", "player", "p", "player1", "side_pick"):
            if isinstance(ctx.get(key), dict):
                p_ace = _recursive_find_ace_pct(ctx.get(key), surface=surface)
                if p_ace is not None:
                    break
    if o_ace is None and isinstance(match.get("ta_context"), dict):
        ctx = match.get("ta_context") or {}
        for key in ("opponent", "opp", "o", "player2", "side_opponent"):
            if isinstance(ctx.get(key), dict):
                o_ace = _recursive_find_ace_pct(ctx.get(key), surface=surface)
                if o_ace is not None:
                    break
    if p_ace is None or o_ace is None:
        return {"aces_status": "MISSING_ACE_PCT", "pick_ace_pct": p_ace, "opponent_ace_pct": o_ace}
    service_points_each = (games / 2.0) * AVG_POINTS_PER_SERVICE_GAME
    pick = service_points_each * (p_ace / 100.0)
    opp = service_points_each * (o_ace / 100.0)
    total = pick + opp
    p_line = _prop_model_line(pick, 0.5, 20.5, 1.15, "Pick aces")
    o_line = _prop_model_line(opp, 0.5, 20.5, 1.15, "Opponent aces")
    t_line = _prop_model_line(total, 1.5, 35.5, 1.70, "Total aces")
    return {
        "aces_status": "OK",
        "pick_aces_projection": round(pick, 1),
        "opponent_aces_projection": round(opp, 1),
        "total_aces_projection": round(total, 1),
        "pick_aces": round(pick, 1),
        "opponent_aces": round(opp, 1),
        "total_aces": round(total, 1),
        "pick_ace_pct": p_ace,
        "opponent_ace_pct": o_ace,
        "pick_aces_line": p_line.get("line"),
        "pick_aces_side": p_line.get("side"),
        "pick_aces_selection": p_line.get("selection"),
        "pick_aces_probability": p_line.get("probability"),
        "opponent_aces_line": o_line.get("line"),
        "opponent_aces_side": o_line.get("side"),
        "opponent_aces_selection": o_line.get("selection"),
        "opponent_aces_probability": o_line.get("probability"),
        "total_aces_line": t_line.get("line"),
        "total_aces_side": t_line.get("side"),
        "total_aces_selection": t_line.get("selection"),
        "total_aces_probability": t_line.get("probability"),
        "aces_source": "TA A% + projected service points",
    }


def _best_model_bet(enriched: Dict[str, Any]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    for label, sel_key, prob_key in (
        ("Sets", "sets_selection", "sets_probability"),
        ("Games", "games_selection", "games_probability"),
        ("Best O/U", "best_total_selection", "best_total_probability"),
        ("TB", "tiebreak_selection", "tiebreak_probability"),
        ("Pick aces", "pick_aces_selection", "pick_aces_probability"),
        ("Opp aces", "opponent_aces_selection", "opponent_aces_probability"),
        ("Total aces", "total_aces_selection", "total_aces_probability"),
        ("Pick DF", "pick_df_selection", "pick_df_probability"),
        ("Opp DF", "opponent_df_selection", "opponent_df_probability"),
        ("Total DF", "total_df_selection", "total_df_probability"),
    ):
        selection = enriched.get(sel_key)
        probability = normalize_probability_value(enriched.get(prob_key))
        if selection and probability is not None:
            candidates.append({"label": label, "selection": selection, "probability": probability})
    if not candidates:
        return {}
    best = max(candidates, key=lambda item: abs(float(item["probability"]) - 0.50))
    return {
        "best_bet": f"{best['selection']}",
        "best_bet_display": f"{best['selection']} {round(best['probability'] * 100):.0f}%",
        "best_bet_probability": round(best["probability"], 4),
        "best_bet_market": best["label"],
    }


def build_market_aware_sets(match: Dict[str, Any], model_prediction: Dict[str, Any], set_markets: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build Sets/Games model fields using real market data when available."""
    set_markets = set_markets or {}
    best_of = _infer_bo(match)
    if _infer_is_doubles(match):
        best_of = 3
    p1_model = normalize_probability_value(model_prediction.get("probability_player1") or match.get("p1_probability"))
    p2_model = normalize_probability_value(model_prediction.get("probability_player2") or match.get("p2_probability"))
    mw = set_markets.get("match_winner") if isinstance(set_markets, dict) else None
    fsw = set_markets.get("first_set_winner") if isinstance(set_markets, dict) else None
    tg = set_markets.get("total_games") if isinstance(set_markets, dict) else None
    ts = set_markets.get("total_sets") if isinstance(set_markets, dict) else None
    tb = set_markets.get("tie_break") if isinstance(set_markets, dict) else None

    if isinstance(mw, dict) and mw.get("p1_probability") is not None:
        p1_match = float(mw["p1_probability"])
        p2_match = float(mw["p2_probability"])
    else:
        p1_match = p1_model if p1_model is not None else 0.5
        p2_match = p2_model if p2_model is not None else 1.0 - p1_match

    if p1_match >= p2_match:
        winner_side = "p1"
        match_prob = p1_match
        first_prob = fsw.get("p1_probability") if isinstance(fsw, dict) else None
    else:
        winner_side = "p2"
        match_prob = p2_match
        first_prob = fsw.get("p2_probability") if isinstance(fsw, dict) else None

    if set_markets:
        pressure = _market_set_pressure(best_of, tg, tb)
    else:
        pressure = _ta_set_pressure(match, best_of)
    if best_of == 5:
        dist = _bo5_distribution(winner_side, match_prob, first_prob, pressure)
        max_label = "O4.5"
    else:
        dist = _bo3_distribution(winner_side, match_prob, first_prob, pressure)
        max_label = "O2.5"

    expected_sets = _expected_sets_from_dist(dist)
    max_sets_prob = _probability_of_max_sets(dist, best_of)
    sets_source = "Model"
    if isinstance(ts, dict) and ts.get("line") is not None:
        ts_line = as_float(ts.get("line"))
        ts_over_prob = ts.get("over_probability")
        ts_under_prob = ts.get("under_probability")
        if ts_line is not None and ts_over_prob is not None and ts_under_prob is not None:
            if float(ts_over_prob) >= float(ts_under_prob):
                max_label = f"O{ts_line:g}"
                max_sets_prob = float(ts_over_prob)
            else:
                max_label = f"U{ts_line:g}"
                max_sets_prob = float(ts_under_prob)
            sets_source = "TennisApiMarkets"
    score = _most_likely_score(dist)
    if isinstance(tg, dict):
        games_line = tg.get("line")
        over_prob = tg.get("over_probability")
        under_prob = tg.get("under_probability")
        projected_games = games_line
        games_model_source = "TennisApiMarkets"
    else:
        projected_games = _ta_total_games_projection(match, best_of, expected_sets)
        games_model_source = "TA profile"
        if projected_games is None:
            projected_games = _fallback_total_games_projection(best_of, expected_sets, match_prob)
            games_model_source = "ModelFallback"
        low, high = (28.5, 49.5) if best_of == 5 else (18.5, 25.5)
        games_line = _standard_half_line(projected_games, low, high)
        over_prob = _over_probability_from_projection(projected_games, games_line, 1.85 if best_of == 3 else 3.2)
        under_prob = round(1.0 - over_prob, 4)
    games_pick = None
    games_selection = None
    games_probability = None
    if games_line is not None and over_prob is not None and under_prob is not None:
        if over_prob >= under_prob:
            games_pick = f"Over {games_line:g}"
            games_selection = f"O{games_line:g}"
            games_probability = over_prob
        else:
            games_pick = f"Under {games_line:g}"
            games_selection = f"U{games_line:g}"
            games_probability = under_prob
    tie_break_probability = tb.get("yes_probability") if isinstance(tb, dict) else _ta_tiebreak_probability(match, best_of)
    tie_break_selection = "Yes" if tie_break_probability is not None and tie_break_probability >= 0.50 else "No" if tie_break_probability is not None else None

    return {
        "expected_sets": expected_sets,
        "sets_selection": max_label,
        "sets_probability": max_sets_prob,
        "sets_probability_label": max_label,
        "sets_o25_probability": max_sets_prob if best_of == 3 else None,
        "sets_o45_probability": max_sets_prob if best_of == 5 else None,
        "most_likely_score": score,
        "most_likely_score_probability": dist.get(score),
        "score_probabilities": dist,
        "score_basis": "player1_vs_player2",
        "sets_source": sets_source,
        "first_set_player1_odds": fsw.get("p1_odds") if isinstance(fsw, dict) else None,
        "first_set_player2_odds": fsw.get("p2_odds") if isinstance(fsw, dict) else None,
        "first_set_player1_probability": fsw.get("p1_probability") if isinstance(fsw, dict) else None,
        "first_set_player2_probability": fsw.get("p2_probability") if isinstance(fsw, dict) else None,
        "expected_games": projected_games,
        "projected_total_games": projected_games,
        "games_line": games_line,
        "total_games_line": games_line,
        "games_pick": games_pick,
        "games_selection": games_selection,
        "games_probability": games_probability,
        "games_model_source": games_model_source,
        "games_data_quality": "B" if games_model_source == "TA profile" else "C+",
        "best_total_selection": games_selection,
        "best_total_probability": games_probability,
        "games_over_odds": tg.get("over_odds") if isinstance(tg, dict) else None,
        "games_under_odds": tg.get("under_odds") if isinstance(tg, dict) else None,
        "games_over_probability": round(float(over_prob), 4) if over_prob is not None else None,
        "games_under_probability": round(float(under_prob), 4) if under_prob is not None else None,
        "tie_break_yes_odds": tb.get("yes_odds") if isinstance(tb, dict) else None,
        "tie_break_no_odds": tb.get("no_odds") if isinstance(tb, dict) else None,
        "tie_break_selection": tie_break_selection,
        "tiebreak_selection": tie_break_selection,
        "tie_break_probability": round(float(tie_break_probability), 4) if tie_break_probability is not None else None,
        "tb_probability": round(float(tie_break_probability), 4) if tie_break_probability is not None else None,
        "tiebreak_probability": round(float(tie_break_probability), 4) if tie_break_probability is not None else None,
        "sets_model_source": "TennisApiMarkets" if set_markets else "ModelFallback",
    }



def _df_pct_from_value(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", ".")
        number = float(value)
        if 0 < number <= 1:
            number *= 100.0
        # Tennis double-fault percentage above 30% is almost certainly not a DF%.
        if 0 < number < 30:
            return number
    except Exception:
        return None
    return None


def _recursive_find_df_pct(obj: Any, surface: Optional[str] = None) -> Optional[float]:
    """Find a real double-fault percentage in TA/Sackmann-like player records."""
    if not isinstance(obj, (dict, list)):
        return None
    preferred_keys = {
        "df%", "df_pct", "df_percent", "df_percentage", "df_rate", "dfs_pct", "dfs_percent",
        "double_fault_pct", "double_fault_percent", "double_fault_percentage", "double_fault_rate",
        "double_faults_pct", "double_faults_percent", "double_faults_percentage",
        "ta_df_pct", "ta_df_percent", "ta_double_fault_pct", "ta_double_fault_percent",
        "dfPct", "dfPercent", "doubleFaultPct", "doubleFaultPercent",
    }
    if isinstance(obj, dict):
        if surface:
            surf = str(surface).strip().lower()
            for key, value in obj.items():
                if str(key).strip().lower() == surf and isinstance(value, dict):
                    pct_value = _recursive_find_df_pct(value, surface=None)
                    if pct_value is not None:
                        return pct_value
        for key, value in obj.items():
            key_text = str(key).strip()
            if key_text in preferred_keys or key_text.lower() in preferred_keys:
                pct_value = _df_pct_from_value(value)
                if pct_value is not None:
                    return pct_value
        for key in ("surface", "surfaces", "splits", "totals", "last52", "last_52", "recent", "current_year", "yearly", "career"):
            pct_value = _recursive_find_df_pct(obj.get(key), surface=surface)
            if pct_value is not None:
                return pct_value
        for value in obj.values():
            pct_value = _recursive_find_df_pct(value, surface=surface)
            if pct_value is not None:
                return pct_value
    if isinstance(obj, list):
        for value in obj:
            pct_value = _recursive_find_df_pct(value, surface=surface)
            if pct_value is not None:
                return pct_value
    return None


def _first_df_pct(row: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    for key in keys:
        pct_value = _df_pct_from_value(row.get(key))
        if pct_value is not None:
            return pct_value
    return None


def _projection_side(projection: Any, line: Any) -> Optional[str]:
    proj = as_float(projection)
    ln = as_float(line)
    if proj is None or ln is None:
        return None
    return "Over" if proj >= ln else "Under"


def build_ta_double_faults_projection(match: Dict[str, Any], games_line: Any = None, surface: Optional[str] = None) -> Dict[str, Any]:
    """Project double faults from real TA/Sackmann DF% plus projected games.

    No synthetic DF% is created. If DF% is missing for either side, the function
    returns unavailable values and the UI can show N/A.
    """
    games = as_float(games_line or match.get("projected_total_games") or match.get("expected_games") or match.get("games_line") or match.get("total_games_line"))
    if games is None or games <= 0:
        return {"double_faults_available": False, "df_status": "NO_GAMES_LINE"}

    surface = surface or str(match.get("surface") or match.get("surface_raw") or "") or None
    pick_df_pct = _first_df_pct(match, (
        "pick_df_pct", "ta_pick_df_pct", "pick_double_fault_pct", "pick_double_faults_pct",
        "df_pick_pct", "pick_df_percent", "ta_pick_double_fault_pct",
    ))
    opp_df_pct = _first_df_pct(match, (
        "opponent_df_pct", "opp_df_pct", "ta_opp_df_pct", "ta_opponent_df_pct",
        "opponent_double_fault_pct", "opp_double_fault_pct", "opponent_double_faults_pct",
        "df_opponent_pct", "opponent_df_percent", "ta_opp_double_fault_pct",
    ))

    if pick_df_pct is None:
        for key in ("ta_profile_pick", "pick_ta_profile", "ta_pick_profile", "ta_context_pick", "pick_profile"):
            if isinstance(match.get(key), dict):
                pick_df_pct = _recursive_find_df_pct(match.get(key), surface=surface)
                if pick_df_pct is not None:
                    break
    if opp_df_pct is None:
        for key in ("ta_profile_opponent", "opponent_ta_profile", "ta_opp_profile", "ta_context_opponent", "opponent_profile"):
            if isinstance(match.get(key), dict):
                opp_df_pct = _recursive_find_df_pct(match.get(key), surface=surface)
                if opp_df_pct is not None:
                    break

    if pick_df_pct is None and isinstance(match.get("ta_context"), dict):
        ctx = match.get("ta_context") or {}
        for key in ("pick", "player", "p", "player1", "side_pick"):
            if isinstance(ctx.get(key), dict):
                pick_df_pct = _recursive_find_df_pct(ctx.get(key), surface=surface)
                if pick_df_pct is not None:
                    break
    if opp_df_pct is None and isinstance(match.get("ta_context"), dict):
        ctx = match.get("ta_context") or {}
        for key in ("opponent", "opp", "o", "player2", "side_opponent"):
            if isinstance(ctx.get(key), dict):
                opp_df_pct = _recursive_find_df_pct(ctx.get(key), surface=surface)
                if opp_df_pct is not None:
                    break

    if pick_df_pct is None or opp_df_pct is None:
        return {
            "double_faults_available": False,
            "df_status": "MISSING_DF_PCT",
            "pick_df_pct": pick_df_pct,
            "opponent_df_pct": opp_df_pct,
        }

    service_games_each = games / 2.0
    service_points_each = service_games_each * AVG_POINTS_PER_SERVICE_GAME
    pick_df = service_points_each * (pick_df_pct / 100.0)
    opp_df = service_points_each * (opp_df_pct / 100.0)
    total_df = pick_df + opp_df

    pick_line = as_float(match.get("pick_df_line") or match.get("pick_double_faults_line"))
    opp_line = as_float(match.get("opponent_df_line") or match.get("opp_df_line") or match.get("opponent_double_faults_line"))
    total_line = as_float(match.get("total_df_line") or match.get("total_double_faults_line"))

    output = {
        "double_faults_available": True,
        "df_pick": round(pick_df, 1),
        "df_opponent": round(opp_df, 1),
        "df_total": round(total_df, 1),
        "pick_df_pct": round(pick_df_pct, 2),
        "opponent_df_pct": round(opp_df_pct, 2),
        "df_source": "TA/Sackmann DF% + games_line",
        "df_status": "OK",
    }
    if pick_line is None:
        pick_line = _standard_half_line(pick_df, 0.5, 12.5)
    if opp_line is None:
        opp_line = _standard_half_line(opp_df, 0.5, 12.5)
    if total_line is None:
        total_line = _standard_half_line(total_df, 1.5, 22.5)

    def add_df(prefix: str, projection: float, line: float, scale: float) -> None:
        side = _projection_side(projection, line)
        over_probability = _over_probability_from_projection(projection, line, scale)
        probability = over_probability if side == "Over" else round(1.0 - over_probability, 4)
        short = "O" if side == "Over" else "U"
        output[f"{prefix}_df_line"] = line
        output[f"{prefix}_df_side"] = side
        output[f"{prefix}_df_selection"] = f"{short}{line:g}"
        output[f"{prefix}_df_probability"] = probability

    add_df("pick", pick_df, pick_line, 0.90)
    add_df("opponent", opp_df, opp_line, 0.90)
    add_df("total", total_df, total_line, 1.25)
    return output

def build_sets_games_from_match(match: Dict[str, Any], model_prediction: Optional[Dict[str, Any]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch markets and build Sets/Games fields for a current project match row."""
    event_id = match.get("event_id") or match.get("match_id") or match.get("id")
    set_markets = get_tennisapi_set_markets(event_id, force_refresh=force_refresh) if event_id else {}
    output = build_market_aware_sets(match, model_prediction or match, set_markets=set_markets)
    enriched = dict(match)
    enriched.update(output)
    df_info = build_ta_double_faults_projection(
        enriched,
        games_line=enriched.get("projected_total_games") or enriched.get("expected_games") or enriched.get("games_line") or enriched.get("total_games_line"),
        surface=str(enriched.get("surface") or enriched.get("surface_raw") or "") or None,
    )
    if isinstance(df_info, dict):
        enriched.update(df_info)
    aces_info = _ta_aces_projection(enriched, as_float(enriched.get("projected_total_games") or enriched.get("expected_games")))
    if isinstance(aces_info, dict):
        enriched.update(aces_info)
    best_info = _best_model_bet(enriched)
    if isinstance(best_info, dict):
        enriched.update(best_info)
    value_candidates = build_sets_games_value_candidates(enriched)
    enriched["sets_games_value_candidates"] = value_candidates
    if value_candidates and value_candidates[0].get("selection"):
        enriched["value_bet"] = value_candidates[0].get("selection")
        enriched["value_bet_display"] = value_candidates[0].get("selection")
        enriched["sets_games_best_value"] = value_candidates[0].get("selection")
        enriched["sets_games_best_value_edge"] = value_candidates[0].get("edge")
    else:
        enriched["value_bet"] = None
        enriched["value_bet_display"] = None
        enriched.setdefault("sets_games_best_value", None)
    return enriched



# ---------------------------------------------------------------------------
# Runtime override: TennisAPI PRO /odds/{provider}/all real market-line parser
# ---------------------------------------------------------------------------
# The functions below intentionally override earlier definitions with the same
# names.  They keep older Bet365/TA helpers intact, but prefer TennisAPI PRO
# real market lines when provider payloads expose them.

_REAL_LINE_SOURCE = "TennisApiPRO getAllOddsForEvent"


def _line_from_market_or_choices(market: Dict[str, Any]) -> Optional[float]:
    for key in ("choiceGroup", "line", "handicap", "total", "points"):
        val = as_float(market.get(key))
        if val is not None:
            return val
    choices = market.get("choices") or market.get("outcomes") or []
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            for key in ("choiceGroup", "line", "handicap", "total", "points", "name", "label"):
                val = as_float(choice.get(key))
                if val is not None:
                    return val
                line = _extract_line(choice.get(key))
                if line is not None:
                    return line
    for key in ("marketName", "name", "marketGroup", "group"):
        line = _extract_line(market.get(key))
        if line is not None:
            return line
    return None


def _market_name_blob(market: Dict[str, Any]) -> str:
    parts = []
    for key in ("marketName", "name", "marketGroup", "group", "marketPeriod", "choiceGroup"):
        value = market.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts).strip()


def _market_kind_from_blob(blob: str, line: Optional[float] = None) -> Optional[str]:
    low = blob.lower().replace("-", " ")
    if "double fault" in low or "doublefault" in low or " double faults" in low or " df" in low:
        return "total_df" if "total" in low and "player" not in low else "player_df"
    if "ace" in low:
        return "total_aces" if "total" in low and "player" not in low else "player_aces"
    # TennisAPI sometimes uses one family name like Total sets/games and choiceGroup is the line.
    if "total sets/games" in low or ("total" in low and "sets" in low and "game" in low):
        if line is not None and line <= 5.5:
            return "total_sets"
        return "total_games"
    if "total set" in low or "sets total" in low:
        return "total_sets"
    if "total game" in low or "games total" in low:
        return "total_games"
    if "tie break" in low or "tiebreak" in low or "tie-break" in low:
        return "tie_break"
    if "first set winner" in low:
        return "first_set_winner"
    if "full time" in low or "match winner" in low or "winner" == low.strip():
        return "match_winner"
    return None


def _ou_details_from_market(market: Dict[str, Any]) -> Dict[str, Any]:
    details = _find_over_under_details(market)
    line = _line_from_market_or_choices(market)
    if line is not None:
        details["line"] = line
    over_odds, under_odds = details.get("over_odds"), details.get("under_odds")
    over_prob, under_prob = normalize_pair_probability(over_odds, under_odds)
    details["over_probability"] = over_prob
    details["under_probability"] = under_prob
    details["source"] = _REAL_LINE_SOURCE
    return details


def _pair_details_from_market(market: Dict[str, Any]) -> Dict[str, Any]:
    details = _market_choices_pair_details(market)
    p1, p2 = details.get("p1_odds"), details.get("p2_odds")
    p1_prob, p2_prob = normalize_pair_probability(p1, p2)
    details["p1_probability"] = p1_prob
    details["p2_probability"] = p2_prob
    details["source"] = _REAL_LINE_SOURCE
    return details


def parse_tennisapi_set_markets(payload: Dict[str, Any], event_id: Optional[int] = None) -> Dict[str, Any]:
    """Parse rich TennisAPI PRO all-odds payload into real market-line fields.

    Primary endpoint shape: /api/tennis/event/{event_id}/odds/{provider_id}/all.
    The parser captures match winner, Total Sets, Total Games, TB, player/total
    aces and player/total double-fault lines when those markets are available.
    """
    markets = _normalize_tennisapi_markets_payload(payload or {})
    output: Dict[str, Any] = {
        "event_id": event_id or (payload.get("eventId") if isinstance(payload, dict) else None),
        "match_winner": None,
        "first_set_winner": None,
        "total_games": None,
        "total_sets": None,
        "tie_break": None,
        "player_aces_markets": [],
        "total_aces": None,
        "player_df_markets": [],
        "total_df": None,
        "raw_market_count": len(markets),
        "market_source": _REAL_LINE_SOURCE,
    }

    for market in markets:
        if not isinstance(market, dict):
            continue
        line = _line_from_market_or_choices(market)
        blob = _market_name_blob(market)
        market_id = market.get("marketId")
        kind = _market_kind_from_blob(blob, line=line)
        # Legacy ids can still help where names are sparse.
        if kind is None:
            if market_id == 1:
                kind = "match_winner"
            elif market_id == 11:
                kind = "first_set_winner"
            elif market_id == 12:
                kind = "total_games"
            elif market_id == 13:
                kind = "tie_break"
        meta = {
            "market_id": market_id,
            "market_name": str(market.get("marketName") or market.get("name") or ""),
            "market_group": str(market.get("marketGroup") or market.get("group") or ""),
            "market_period": str(market.get("marketPeriod") or ""),
            "raw_label": blob,
            "source": _REAL_LINE_SOURCE,
        }
        if kind == "match_winner":
            details = _pair_details_from_market(market)
            if details.get("p1_odds") and details.get("p2_odds"):
                output["match_winner"] = {**details, **meta}
        elif kind == "first_set_winner":
            details = _pair_details_from_market(market)
            if details.get("p1_odds") and details.get("p2_odds"):
                output["first_set_winner"] = {**details, **meta}
        elif kind in {"total_games", "total_sets"}:
            details = _ou_details_from_market(market)
            if details.get("line") is not None and details.get("over_odds") and details.get("under_odds"):
                target = "total_sets" if kind == "total_sets" else "total_games"
                output[target] = {**details, **meta}
        elif kind == "tie_break":
            details = _pair_details_from_market(market)
            yes_odds, no_odds = details.get("p1_odds"), details.get("p2_odds")
            yes_prob, no_prob = normalize_pair_probability(yes_odds, no_odds)
            if yes_odds and no_odds:
                output["tie_break"] = {
                    "yes_odds": yes_odds,
                    "no_odds": no_odds,
                    "yes_initial_odds": details.get("p1_initial_odds"),
                    "no_initial_odds": details.get("p2_initial_odds"),
                    "yes_change": details.get("p1_change"),
                    "no_change": details.get("p2_change"),
                    "yes_probability": yes_prob,
                    "no_probability": no_prob,
                    **meta,
                }
        elif kind in {"player_aces", "player_df", "total_aces", "total_df"}:
            details = _ou_details_from_market(market)
            if details.get("line") is None or not (details.get("over_odds") and details.get("under_odds")):
                continue
            payload_line = {**details, **meta}
            if kind == "total_aces":
                output["total_aces"] = payload_line
            elif kind == "total_df":
                output["total_df"] = payload_line
            elif kind == "player_aces":
                output.setdefault("player_aces_markets", []).append(payload_line)
            elif kind == "player_df":
                output.setdefault("player_df_markets", []).append(payload_line)
    return output


def _score_prop_market_for_player(market: Dict[str, Any], player_name: str, side_hint: Optional[str] = None) -> float:
    blob = f"{market.get('raw_label') or ''} {market.get('market_name') or ''} {market.get('market_group') or ''}"
    try:
        score = name_match_score(player_name, blob)
    except Exception:
        score = 0.0
    low = blob.lower()
    if side_hint:
        side = side_hint.lower()
        if side == "home" and any(x in low for x in ("player 1", "home", "team 1", "1 ")):
            score = max(score, 0.75)
        if side == "away" and any(x in low for x in ("player 2", "away", "team 2", "2 ")):
            score = max(score, 0.75)
    return score


def _select_player_prop(markets: List[Dict[str, Any]], player_name: str, side_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not markets:
        return None
    scored = sorted(
        ((_score_prop_market_for_player(m, player_name, side_hint), m) for m in markets),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] >= 0.45:
        return scored[0][1]
    # If only two markets exist but names are unusable, preserve order as a fallback.
    return None


def _prop_selection_from_projection(projection: Any, line: Any, scale: float) -> Dict[str, Any]:
    proj = as_float(projection)
    ln = as_float(line)
    if proj is None or ln is None:
        return {"side": None, "selection": None, "probability": None}
    over_p = _over_probability_from_projection(proj, ln, scale)
    if proj >= ln:
        return {"side": "Over", "selection": f"O{ln:g}", "probability": over_p}
    return {"side": "Under", "selection": f"U{ln:g}", "probability": round(1.0 - over_p, 4)}


def _apply_real_prop_lines(enriched: Dict[str, Any], set_markets: Dict[str, Any]) -> None:
    """Overlay real Aces/DF bookmaker lines on top of model projections.

    Projection still comes from API/TA serve stats. Line comes from the real
    market when available. If no real market is present, the existing synthetic
    projection line remains unchanged.
    """
    pick = str(enriched.get("pick") or enriched.get("player") or enriched.get("player1") or "")
    opp = str(enriched.get("opponent") or enriched.get("opp") or enriched.get("player2") or "")
    pick_side = str(enriched.get("pick_side") or "").strip().upper() or None
    opp_side = str(enriched.get("opponent_side") or "").strip().upper() or None

    for family, market_key, prefix, total_key, scale in (
        ("aces", "player_aces_markets", "aces", "total_aces", 1.15),
        ("df", "player_df_markets", "df", "total_df", 1.05),
    ):
        p_market = _select_player_prop(set_markets.get(market_key) or [], pick, pick_side)
        o_market = _select_player_prop(set_markets.get(market_key) or [], opp, opp_side)
        # Order fallback: if two player markets exist and matching did not work, use row side order.
        candidate_markets = set_markets.get(market_key) or []
        if p_market is None and len(candidate_markets) >= 1:
            p_market = candidate_markets[0 if pick_side != "AWAY" else min(1, len(candidate_markets) - 1)]
        if o_market is None and len(candidate_markets) >= 2:
            o_market = candidate_markets[1 if pick_side != "AWAY" else 0]
        t_market = set_markets.get(total_key)

        mappings = [
            ("pick", p_market, f"pick_{prefix}"),
            ("opponent", o_market, f"opponent_{prefix}"),
            ("total", t_market, f"total_{prefix}"),
        ]
        for side_name, market, base in mappings:
            if not isinstance(market, dict):
                continue
            line = as_float(market.get("line"))
            if line is None:
                continue
            projection = enriched.get(f"{base}_projection") or enriched.get(base)
            sel = _prop_selection_from_projection(projection, line, scale)
            enriched[f"{base}_line"] = line
            enriched[f"{base}_over_odds"] = market.get("over_odds")
            enriched[f"{base}_under_odds"] = market.get("under_odds")
            enriched[f"{base}_market_source"] = market.get("source") or _REAL_LINE_SOURCE
            if sel.get("side"):
                enriched[f"{base}_side"] = sel["side"]
                enriched[f"{base}_selection"] = sel["selection"]
                enriched[f"{base}_probability"] = sel["probability"]
            enriched[f"{base}_line_source"] = "REAL_MARKET_LINE"


def build_sets_games_from_match(match: Dict[str, Any], model_prediction: Optional[Dict[str, Any]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch markets and build Sets/Games fields for a current project match row.

    Real TennisAPI PRO market lines are preferred for Sets, Games, Aces and DF.
    Model/serve projections are used to decide O/U probability against those
    lines. If a real prop line is missing, existing projection fallback remains.
    """
    event_id = match.get("event_id") or match.get("match_id") or match.get("id")
    set_markets = get_tennisapi_set_markets(event_id, force_refresh=force_refresh) if event_id else {}
    output = build_market_aware_sets(match, model_prediction or match, set_markets=set_markets)
    enriched = dict(match)
    enriched.update(output)
    enriched["sets_games_market_source"] = set_markets.get("market_source") if isinstance(set_markets, dict) else None
    enriched["sets_games_raw_market_count"] = set_markets.get("raw_market_count") if isinstance(set_markets, dict) else None

    df_info = build_ta_double_faults_projection(
        enriched,
        games_line=enriched.get("projected_total_games") or enriched.get("expected_games") or enriched.get("games_line") or enriched.get("total_games_line"),
        surface=str(enriched.get("surface") or enriched.get("surface_raw") or "") or None,
    )
    if isinstance(df_info, dict):
        enriched.update(df_info)
    aces_info = _ta_aces_projection(enriched, as_float(enriched.get("projected_total_games") or enriched.get("expected_games")))
    if isinstance(aces_info, dict):
        enriched.update(aces_info)

    if isinstance(set_markets, dict):
        _apply_real_prop_lines(enriched, set_markets)

    best_info = _best_model_bet(enriched)
    if isinstance(best_info, dict):
        enriched.update(best_info)
    value_candidates = build_sets_games_value_candidates(enriched)
    enriched["sets_games_value_candidates"] = value_candidates
    if value_candidates and value_candidates[0].get("selection"):
        enriched["value_bet"] = value_candidates[0].get("selection")
        enriched["value_bet_display"] = value_candidates[0].get("selection")
        enriched["sets_games_best_value"] = value_candidates[0].get("selection")
        enriched["sets_games_best_value_edge"] = value_candidates[0].get("edge")
    else:
        enriched["value_bet"] = None
        enriched["value_bet_display"] = None
        enriched.setdefault("sets_games_best_value", None)
    return enriched
