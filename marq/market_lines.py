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
    candidates: List[Dict[str, Any]] = []

    sets_line = as_float(row.get("sets_o25_line")) or 2.5
    sets_prob = row.get("sets_o25_probability") or row.get("sets_over_25_probability")
    sets_edge = edge_from_probability(sets_prob, row.get("sets_o25_over_odds"), row.get("sets_o25_under_odds"))
    if sets_prob is not None and row.get("sets_o25_over_odds"):
        candidates.append({
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
        candidates.append({
            "market": "total_games",
            "selection": f"{games_side} {games_line:g} games",
            "model_probability": pct(prob),
            "market_odds": as_float(row.get(odds_key)),
            "edge": edge,
        })

    tb_prob = row.get("tb_probability") or row.get("tie_break_probability")
    tb_edge = edge_from_probability(tb_prob, row.get("tb_yes_odds"), row.get("tb_no_odds"))
    if tb_prob is not None and row.get("tb_yes_odds"):
        candidates.append({
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
        candidates.append({
            "market": f"{prefix}_aces",
            "selection": selection,
            "model_probability": pct(prob),
            "market_odds": as_float(row.get(odds_key)),
            "edge": edge,
        })

    # Edge is the real value metric. If edge is unknown, sort by model probability as fallback.
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
