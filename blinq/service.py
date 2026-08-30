"""BlinQ orchestration over the canonical ThinQ model.

BlinQ does not implement a second prediction formula. It runs ThinQ in both
orientations and accepts a prediction only when the real A/B model runs are
complementary. Exact 50:50 always means NO_PREDICTION.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from thinq.service import ThinqService
from blinq.loaders.elo_loader import build_elo_context as build_blinq_elo_context
from blinq.loaders.h2h_loader import build_h2h_context as build_blinq_h2h_context
from blinq.features.recent_form import build_recent_form_context as build_blinq_recent_form_context

REGISTRY_PATH = Path("thinq/data/players/player_registry.json")
TOLERANCE = 0.0001
API_PRO_HOST = "tennisapi1.p.rapidapi.com"
API_PRO_BASE_URL = "https://tennisapi1.p.rapidapi.com"
API_TIMEOUT = 20
BLINQ_CACHE_DIR = Path("blinq/data/api_cache/previous_matches")
BLINQ_CACHE_TTL_SECONDS = 60 * 60 * 12
BLINQ_MAX_PAGES = 3
BLINQ_MIN_OVERALL_MATCHES = 10
BLINQ_MIN_SURFACE_MATCHES = 5


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def _int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(row: Dict[str, Any]) -> str:
    return str(
        row.get("display_name")
        or row.get("canonical_name")
        or row.get("name")
        or row.get("player")
        or ""
    ).strip()


def _registry_mtime() -> int:
    try:
        return REGISTRY_PATH.stat().st_mtime_ns
    except OSError:
        return 0


@lru_cache(maxsize=2)
def _registry_cached(_mtime_ns: int) -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("players") if isinstance(payload, dict) else []
    if isinstance(rows, dict):
        rows = list(rows.values())
    index: Dict[str, Dict[str, Any]] = {}
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        name = _name(raw)
        if not name:
            continue
        row = dict(raw)
        row["player"] = name
        keys = [name, row.get("normalized_name"), row.get("compact_key")]
        keys.extend(row.get("aliases") if isinstance(row.get("aliases"), list) else [])
        for value in keys:
            key = _compact(value)
            if key:
                index.setdefault(key, row)
    return index


def _registry() -> Dict[str, Dict[str, Any]]:
    return _registry_cached(_registry_mtime())


def _tour(row: Dict[str, Any]) -> Optional[str]:
    for value in (
        row.get("tour"), row.get("circuit"), row.get("category"),
        row.get("competition_type"), row.get("gender"), row.get("sex"),
        row.get("league"), row.get("source_tour"),
    ):
        text = str(value or "").strip().upper()
        if "WTA" in text or text in {"F", "W", "WOMEN", "FEMALE"}:
            return "WTA"
        if "ATP" in text or text in {"M", "MEN", "MALE"}:
            return "ATP"
    return None


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    country = row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2")
    return {
        "player": row.get("player") or _name(row),
        "player_id": _int(row.get("api_team_id") or row.get("rapidapi_id") or row.get("player_id")),
        "country_code": str(country).upper() if country else None,
        "country_name": row.get("country_name") or row.get("country"),
        "tour": _tour(row),
        "rank": _int(row.get("rank") or row.get("api_rank")),
        "rank_points": _int(row.get("rank_points") or row.get("api_points")),
        "elo": _float(row.get("elo")),
        "hard_elo": _float(row.get("hard_elo")),
        "clay_elo": _float(row.get("clay_elo")),
        "grass_elo": _float(row.get("grass_elo")),
    }


def _layer(result: Dict[str, Any]) -> Dict[str, Any]:
    value = result.get("thinq_probability_layer") or result.get("probability_layer")
    return value if isinstance(value, dict) else {}



def _pair_index(value1: Any, value2: Any, *, samples1: int = 1, samples2: int = 1) -> Dict[str, Any]:
    """Return a real-data pair index. Missing samples stay unavailable, never 50:50."""
    first = _float(value1)
    second = _float(value2)
    if first is None or second is None or samples1 <= 0 or samples2 <= 0:
        return {"available": False, "p1": None, "p2": None}
    total = first + second
    if total <= 0:
        return {"available": False, "p1": None, "p2": None}
    p1 = round(first / total * 100.0, 1)
    return {"available": True, "p1": p1, "p2": round(100.0 - p1, 1)}


def _elo_index(elo: Dict[str, Any]) -> Dict[str, Any]:
    first = _float(elo.get("pick_elo"))
    second = _float(elo.get("opponent_elo"))
    if first is None or second is None:
        return {"available": False, "p1": None, "p2": None, "label": "S-index"}
    # Same neutral ELO scale as the model, exposed only as a 0-100 strength index.
    probability = 1.0 / (1.0 + 10.0 ** (-(first - second) / 400.0))
    p1 = round(probability * 100.0, 1)
    return {"available": True, "p1": p1, "p2": round(100.0 - p1, 1), "label": "S-index"}


def _window(form: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    player = form.get(side) if isinstance(form.get(side), dict) else {}
    value = player.get(key) if isinstance(player.get(key), dict) else {}
    return value


def _form_record(form: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    window = _window(form, side, key)
    wins = _int(window.get("wins") if window.get("wins") is not None else window.get("w"))
    losses = _int(window.get("losses") if window.get("losses") is not None else window.get("l"))
    count = _int(window.get("count"))
    if count is None and wins is not None and losses is not None:
        count = wins + losses
    if wins is None or losses is None or not count or count <= 0:
        return {"available": False, "wins": None, "losses": None, "count": 0}
    return {"available": True, "wins": wins, "losses": losses, "count": count}


def _form_records(form: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player1": {
            "last10": _form_record(form, "pick", "last10"),
            "surface": _form_record(form, "pick", "surface_last10"),
        },
        "player2": {
            "last10": _form_record(form, "opponent", "last10"),
            "surface": _form_record(form, "opponent", "surface_last10"),
        },
    }


def _form_index(form: Dict[str, Any], key: str, prefix: str) -> Dict[str, Any]:
    first = _window(form, "pick", key)
    second = _window(form, "opponent", key)
    count1 = _int(first.get("count")) or 0
    count2 = _int(second.get("count")) or 0
    sample = min(count1, count2)
    index = _pair_index(first.get("win_pct"), second.get("win_pct"), samples1=count1, samples2=count2)
    index.update({"label": f"{prefix}{sample}-index" if sample > 0 else f"{prefix}-index", "sample": sample})
    return index


def _h2h_index(h2h: Dict[str, Any]) -> Dict[str, Any]:
    total = _int(h2h.get("total_matches")) or 0
    first = _int(h2h.get("pick_wins"))
    second = _int(h2h.get("opponent_wins"))
    index = _pair_index(first, second, samples1=total, samples2=total)
    index.update({"label": f"H{total}-index" if total > 0 else "H-index", "sample": total})
    return index


def _surface_elo_index(elo: Dict[str, Any]) -> Dict[str, Any]:
    first = _float(elo.get("surface_pick_elo"))
    second = _float(elo.get("surface_opponent_elo"))
    if first is None or second is None:
        return {"available": False, "p1": None, "p2": None, "label": "SE-INDEX"}
    probability = 1.0 / (1.0 + 10.0 ** (-(first - second) / 400.0))
    p1 = max(5, min(95, int(round(probability * 20.0) * 5)))
    return {"available": True, "p1": p1, "p2": 100 - p1, "label": "SE-INDEX"}


def _surface_h2h_index(h2h: Dict[str, Any]) -> Dict[str, Any]:
    total = _int(h2h.get("same_surface_matches")) or 0
    first = _int(h2h.get("same_surface_pick_wins"))
    second = _int(h2h.get("same_surface_opponent_wins"))
    index = _pair_index(first, second, samples1=total, samples2=total)
    if index.get("available"):
        p1 = max(25, min(75, int(round(float(index["p1"]) / 5.0) * 5)))
        index.update({"p1": p1, "p2": 100 - p1})
    index.update({"label": "SH-INDEX", "sample": total})
    return index


def _market_index(result: Dict[str, Any]) -> Dict[str, Any]:
    """Use market information only when an exact-event movement payload exists."""
    candidates = [result.get("marq"), result.get("market"), (result.get("contexts") or {}).get("marq")]
    for market in candidates:
        if not isinstance(market, dict):
            continue
        exact = market.get("exact_event") is True or str(market.get("match_status") or "").upper() == "EXACT"
        first = _float(market.get("player1_index") or market.get("pick_index"))
        second = _float(market.get("player2_index") or market.get("opponent_index"))
        if exact and first is not None and second is not None:
            index = _pair_index(first, second)
            index.update({"label": "M-index", "source": market.get("source")})
            return index
    return {"available": False, "p1": None, "p2": None, "label": "M-index"}


def _data_index(public: Dict[str, Any], elo: Dict[str, Any], form_window: Dict[str, Any], surface_window: Dict[str, Any], h2h_total: int) -> float:
    checks = [
        public.get("player_id") is not None,
        public.get("elo") is not None,
        elo.get("pick_elo") is not None,
        (_int(form_window.get("count")) or 0) >= 5,
        (_int(surface_window.get("count")) or 0) >= 3,
        h2h_total > 0,
        public.get("rank") is not None,
        bool(public.get("country_code")),
    ]
    return round(sum(1 for item in checks if item) / len(checks) * 100.0, 1)


def _build_indices(forward: Dict[str, Any], player1: Dict[str, Any], player2: Dict[str, Any]) -> Dict[str, Any]:
    elo = forward.get("elo") if isinstance(forward.get("elo"), dict) else {}
    form = forward.get("recent_form") if isinstance(forward.get("recent_form"), dict) else {}
    h2h = forward.get("h2h") if isinstance(forward.get("h2h"), dict) else {}
    p1_last10 = _window(form, "pick", "last10")
    p2_last10 = _window(form, "opponent", "last10")
    p1_surface = _window(form, "pick", "surface_last10")
    p2_surface = _window(form, "opponent", "surface_last10")
    h2h_total = _int(h2h.get("total_matches")) or 0
    return {
        "strength": _elo_index(elo),
        "surface_strength": _surface_elo_index(elo),
        "form": _form_index(form, "last10", "F"),
        "court_form": _form_index(form, "surface_last10", "CF"),
        "h2h": _h2h_index(h2h),
        "surface_h2h": _surface_h2h_index(h2h),
        "market": _market_index(forward),
        "data": {
            "available": True,
            "p1": _data_index(player1, elo, p1_last10, p1_surface, h2h_total),
            "p2": _data_index(player2, {"pick_elo": elo.get("opponent_elo")}, p2_last10, p2_surface, h2h_total),
            "label": "D-index",
        },
    }



def _surface_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def _api_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": API_PRO_HOST,
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY", "").strip(),
    }


def _cache_path(player_id: Any, page: int) -> Path:
    return BLINQ_CACHE_DIR / f"{player_id}_{page}.json"


def _read_cache(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(payload.get("saved_at", 0)) > BLINQ_CACHE_TTL_SECONDS:
            return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_cache(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _fetch_previous_page(player_id: Any, page: int) -> Dict[str, Any]:
    if player_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "events": [], "page": page}
    path = _cache_path(player_id, page)
    cached = _read_cache(path)
    if cached is not None:
        return {**cached, "from_cache": True, "cache_path": str(path)}
    if not os.getenv("RAPIDAPI_KEY", "").strip():
        return {"status": "NO_API_KEY", "events": [], "page": page, "cache_path": str(path)}
    endpoint = f"{API_PRO_BASE_URL}/api/tennis/player/{player_id}/events/previous/{page}"
    try:
        response = requests.get(endpoint, headers=_api_headers(), timeout=API_TIMEOUT)
        if response.status_code == 429:
            return {"status": "RATE_LIMITED", "events": [], "page": page, "api_status_code": 429, "endpoint": endpoint}
        response.raise_for_status()
        payload = response.json() if response.content else {}
        result = {
            "status": "OK",
            "events": payload.get("events", []) if isinstance(payload, dict) and isinstance(payload.get("events", []), list) else [],
            "has_next_page": bool(payload.get("hasNextPage")) if isinstance(payload, dict) else False,
            "page": page,
            "api_status_code": response.status_code,
            "endpoint": endpoint,
            "from_cache": False,
            "cache_path": str(path),
        }
        _write_cache(path, result)
        return result
    except Exception as exc:
        return {"status": "FETCH_FAILED", "events": [], "page": page, "endpoint": endpoint, "error": str(exc)}


def _event_surface(event: Dict[str, Any]) -> str:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    return _surface_bucket(event.get("groundType") or tournament.get("groundType") or unique.get("groundType"))


def _team_id(team: Any) -> Any:
    if not isinstance(team, dict):
        return None
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return team.get("id") or info.get("id")


def _usable_event(event: Any) -> bool:
    if not isinstance(event, dict):
        return False
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    if str(status.get("type") or "").lower() != "finished":
        return False
    description = str(status.get("description") or "").lower()
    if any(token in description for token in ("retired", "walkover", "cancelled", "canceled", "postponed", "abandoned")):
        return False
    categories = (event.get("eventFilters") or {}).get("category") if isinstance(event.get("eventFilters"), dict) else None
    if isinstance(categories, list) and categories and "singles" not in {str(x).lower() for x in categories}:
        return False
    return event.get("winnerCode") in (1, 2, "1", "2")


def _history(player: Dict[str, Any], surface: str) -> Dict[str, Any]:
    player_id = player.get("player_id")
    raw_events: List[Dict[str, Any]] = []
    page_statuses: List[str] = []
    for page in range(BLINQ_MAX_PAGES):
        result = _fetch_previous_page(player_id, page)
        page_statuses.append(str(result.get("status") or "UNKNOWN"))
        raw_events.extend(x for x in (result.get("events") or []) if isinstance(x, dict))
        usable = [x for x in raw_events if _usable_event(x)]
        surface_count = sum(1 for x in usable if _event_surface(x) == _surface_bucket(surface))
        if result.get("status") != "OK" or not result.get("has_next_page"):
            break
        if len(usable) >= BLINQ_MIN_OVERALL_MATCHES and surface_count >= BLINQ_MIN_SURFACE_MATCHES:
            break
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for event in raw_events:
        if not _usable_event(event):
            continue
        event_id = str(event.get("id") or event.get("customId") or "")
        if not event_id or event_id in seen:
            continue
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), dict) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), dict) else {}
        is_home = str(_team_id(home)) == str(player_id)
        is_away = str(_team_id(away)) == str(player_id)
        if not is_home and not is_away:
            continue
        winner_code = int(event.get("winnerCode"))
        won = (is_home and winner_code == 1) or (is_away and winner_code == 2)
        normalized.append({
            "event_id": event_id,
            "timestamp": int(event.get("startTimestamp") or 0),
            "surface": _event_surface(event),
            "won": won,
            "home_id": _team_id(home),
            "away_id": _team_id(away),
            "winner_code": winner_code,
        })
        seen.add(event_id)
    normalized.sort(key=lambda x: int(x.get("timestamp") or 0), reverse=True)
    status = "OK" if normalized else ("RATE_LIMITED" if "RATE_LIMITED" in page_statuses else page_statuses[-1] if page_statuses else "NO_DATA")
    return {"status": status, "matches": normalized, "pages_fetched": len(page_statuses), "page_statuses": page_statuses}


def _summary(matches: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    sample = matches[:limit]
    wins = sum(1 for x in sample if x.get("won") is True)
    count = len(sample)
    return {
        "count": count,
        "wins": wins,
        "losses": count - wins,
        "record": f"{wins}-{count - wins}" if count else "N/A",
        "win_pct": round(wins / count, 4) if count else None,
    }


def _direct_data_bundle(player1: Dict[str, Any], player2: Dict[str, Any], surface: str, forward: Dict[str, Any]) -> Dict[str, Any]:
    """Build a BlinQ-owned snapshot from independent BlinQ JSON/cache sources."""
    elo = build_blinq_elo_context(player1.get("player", ""), player2.get("player", ""), surface)
    form = build_blinq_recent_form_context(
        player1.get("player", ""),
        player2.get("player", ""),
        surface,
        None,
        pick_player_id=player1.get("player_id"),
        opponent_player_id=player2.get("player_id"),
    )
    h2h = build_blinq_h2h_context(
        player1.get("player", ""),
        player2.get("player", ""),
        player1.get("player_id"),
        player2.get("player_id"),
        surface,
    )
    return {
        "elo": elo,
        "form": form,
        "h2h": h2h,
        "source": "BLINQ_INDEPENDENT_JSON_V1",
        "api_calls_needed": False,
    }

def _coverage(player1: Dict[str, Any], player2: Dict[str, Any], elo: Dict[str, Any], form: Dict[str, Any], h2h: Dict[str, Any], surface: str) -> Dict[str, Any]:
    p1_last = _form_record(form, "pick", "last10")
    p2_last = _form_record(form, "opponent", "last10")
    p1_surface = _form_record(form, "pick", "surface_last10")
    p2_surface = _form_record(form, "opponent", "surface_last10")
    surface_key = {"Hard": "hard_elo", "Clay": "clay_elo", "Grass": "grass_elo"}.get(_surface_bucket(surface))
    families = {
        "elo": bool(player1.get("elo") is not None and player2.get("elo") is not None),
        "surface_elo": bool(surface_key and player1.get(surface_key) is not None and player2.get(surface_key) is not None),
        "form": bool(p1_last.get("available") and p2_last.get("available") and min(p1_last["count"], p2_last["count"]) >= 5),
        "surface_form": bool(p1_surface.get("available") and p2_surface.get("available") and min(p1_surface["count"], p2_surface["count"]) >= 3),
        "h2h": bool((_int(h2h.get("total_matches")) or 0) > 0),
    }
    weighted = {"elo": 30, "surface_elo": 15, "form": 30, "surface_form": 15, "h2h": 10}
    score = sum(weighted[key] for key, available in families.items() if available)
    independent = families["form"] or families["h2h"]
    return {
        "score": float(score),
        "families": families,
        "independent_signal_available": independent,
        "prediction_allowed": bool(families["elo"] and independent and score >= 60),
        "required_rule": "ELO plus usable Form or real H2H, with coverage >= 60",
    }

def _no_prediction(reason: str, flags: List[str], **extra: Any) -> Dict[str, Any]:
    return {
        "model": "BlinQ",
        "model_version": "BLINQ_INDEPENDENT_DATA_V4",
        "status": "NO_PREDICTION",
        "prediction_status": "NO_PREDICTION",
        "winner": None,
        "winner_side": None,
        "winner_probability": 0.5,
        "player1_probability": 0.5,
        "player2_probability": 0.5,
        "reason": reason,
        "flags": sorted(set(flags)),
        **extra,
    }


class BlinqService:
    def __init__(self) -> None:
        self.thinq = ThinqService()

    def players(self) -> List[Dict[str, Any]]:
        unique: Dict[str, Dict[str, Any]] = {}
        for row in _registry().values():
            public = _public(row)
            if public["player"] and public["elo"] is not None:
                unique.setdefault(_compact(public["player"]), public)
        return sorted(unique.values(), key=lambda row: str(row["player"]).casefold())

    def _resolve(self, value: str) -> Optional[Dict[str, Any]]:
        return _registry().get(_compact(value))

    def _run(self, pick: Dict[str, Any], opponent: Dict[str, Any], surface: str) -> Dict[str, Any]:
        pick_public, opponent_public = _public(pick), _public(opponent)
        return self.thinq.build_match_features(
            player1=pick_public["player"],
            player2=opponent_public["player"],
            pick=pick_public["player"],
            opponent=opponent_public["player"],
            pick_side="HOME",
            opponent_side="AWAY",
            player1_id=pick_public["player_id"],
            player2_id=opponent_public["player_id"],
            surface=surface,
            level=None,
            best_of=3,
            save_snapshot=False,
        )

    def predict(self, player1: str, player2: str, surface: Optional[str] = None) -> Dict[str, Any]:
        if not str(player1 or "").strip() or not str(player2 or "").strip():
            return _no_prediction("Both players are required.", ["INVALID_INPUT"])
        if _compact(player1) == _compact(player2):
            return _no_prediction("Select two different players.", ["SAME_PLAYER"])

        row1, row2 = self._resolve(player1), self._resolve(player2)
        if row1 is None or row2 is None:
            missing = ([player1] if row1 is None else []) + ([player2] if row2 is None else [])
            return _no_prediction("Player not found in central registry.", ["PLAYER_NOT_FOUND"], missing_players=missing)

        tour1, tour2 = _tour(row1), _tour(row2)
        if not tour1 or not tour2:
            return _no_prediction(
                "Player tour is unavailable. Comparison suppressed.",
                ["PLAYER_TOUR_UNKNOWN"], player1=_public(row1), player2=_public(row2),
            )
        if tour1 != tour2:
            return _no_prediction(
                "ATP and WTA players cannot be compared.",
                ["CROSS_TOUR_COMPARISON"], player1=_public(row1), player2=_public(row2),
            )

        surface_name = str(surface or "Overall")
        forward = self._run(row1, row2, surface_name)
        reverse = self._run(row2, row1, surface_name)
        player1_public, player2_public = _public(row1), _public(row2)
        data_bundle = _direct_data_bundle(player1_public, player2_public, surface_name, forward)
        enriched_forward = dict(forward)
        enriched_forward["elo"] = data_bundle.get("elo") or {}
        enriched_forward["recent_form"] = data_bundle.get("form") or {}
        enriched_forward["h2h"] = data_bundle.get("h2h") or {}
        coverage = _coverage(player1_public, player2_public, enriched_forward.get("elo") or {}, enriched_forward["recent_form"], enriched_forward["h2h"], surface_name)
        layer_ab, layer_ba = _layer(forward), _layer(reverse)
        p_ab = _float(layer_ab.get("pick_probability"))
        p_ba = _float(layer_ba.get("pick_probability"))
        edge_ab = _float(layer_ab.get("edge"))
        edge_ba = _float(layer_ba.get("edge"))

        probability_ok = p_ab is not None and p_ba is not None and abs((p_ab + p_ba) - 1.0) <= TOLERANCE
        edge_ok = edge_ab is not None and edge_ba is not None and abs(edge_ab + edge_ba) <= TOLERANCE
        tie_ok = not (
            p_ab == 0.5
            and (layer_ab.get("prediction_status") != "NO_PREDICTION" or layer_ab.get("winner") is not None)
        )
        symmetry_ok = bool(probability_ok and edge_ok and tie_ok)

        audit = {
            "status": "PASS" if symmetry_ok else "FAIL",
            "probability_complement_ok": probability_ok,
            "edge_antisymmetry_ok": edge_ok,
            "tie_guard_ok": tie_ok,
            "probability_sum": round((p_ab or 0.0) + (p_ba or 0.0), 8),
            "edge_sum": round((edge_ab or 0.0) + (edge_ba or 0.0), 8),
            "tolerance": TOLERANCE,
        }

        indices = _build_indices(enriched_forward, player1_public, player2_public)
        blocked = (
            not symmetry_ok
            or p_ab is None
            or p_ba is None
            or layer_ab.get("prediction_status") == "NO_PREDICTION"
            or p_ab == 0.5
            or not coverage.get("prediction_allowed")
        )
        if blocked:
            flags = list(layer_ab.get("flags") or [])
            if not symmetry_ok:
                flags.append("BLINQ_REAL_AB_SYMMETRY_FAILED")
            if not coverage.get("prediction_allowed"):
                flags.append("INSUFFICIENT_SIGNAL_COVERAGE")
            return _no_prediction(
                "ThinQ data is insufficient, tied, or failed the real A/B audit.",
                flags,
                player1=_public(row1),
                player2=_public(row2),
                surface=surface_name,
                symmetry_audit=audit,
                thinq_forward=forward,
                thinq_reverse=reverse,
                indices=indices,
                data_coverage=coverage,
                data_bundle_source=data_bundle.get("source"),
                h2h=enriched_forward.get("h2h") or {},
                recent_form=enriched_forward.get("recent_form") or {},
                elo=enriched_forward.get("elo") or {},
                form_records=_form_records(enriched_forward.get("recent_form") if isinstance(enriched_forward.get("recent_form"), dict) else {}),
            )

        winner_is_p1 = p_ab > 0.5
        return {
            "model": "BlinQ",
            "model_version": "BLINQ_INDEPENDENT_DATA_V4",
            "status": "PREDICTION",
            "prediction_status": "PREDICTION",
            "surface": surface_name,
            "player1": _public(row1),
            "player2": _public(row2),
            "player1_probability": round(p_ab, 4),
            "player2_probability": round(1.0 - p_ab, 4),
            "winner": _public(row1)["player"] if winner_is_p1 else _public(row2)["player"],
            "winner_side": "PLAYER1" if winner_is_p1 else "PLAYER2",
            "winner_probability": round(max(p_ab, 1.0 - p_ab), 4),
            "confidence": layer_ab.get("confidence"),
            "edge": edge_ab,
            "components": layer_ab.get("components") or {},
            "h2h": enriched_forward.get("h2h") or {},
            "recent_form": enriched_forward.get("recent_form") or {},
            "elo": enriched_forward.get("elo") or {},
            "data_coverage": coverage,
            "data_bundle_source": data_bundle.get("source"),
            "flags": sorted(set(layer_ab.get("flags") or [])),
            "symmetry_audit": audit,
            "indices": indices,
            "form_records": _form_records(enriched_forward.get("recent_form") if isinstance(enriched_forward.get("recent_form"), dict) else {}),
        }
