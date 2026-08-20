"""THINQ service with side-orientation audit.

THINQ is always calculated for pick/opponent.
player1 and player2 are kept as canonical HOME/AWAY input fields only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from corq.sides import build_side_audit

try:
    from thinq.loaders.elo_loader import build_elo_context
except Exception:
    def build_elo_context(pick: str, opponent: str, surface: Optional[str] = None) -> Dict[str, Any]:
        return {"status": "NO_DATA", "selected_elo_type": None, "elo_edge": 0.0, "flags": ["MISSING_ELO"]}

try:
    from thinq.loaders.h2h_loader import build_h2h_context
except Exception:
    def build_h2h_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "NO_DATA", "source": "none", "total_matches": 0, "pick_wins": 0, "opponent_wins": 0, "edge": 0.0, "confidence": 0.0, "reason": "H2H loader unavailable"}

try:
    from thinq.features.recent_form import build_recent_form_context
except Exception:
    def build_recent_form_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "NO_DATA", "flags": ["RECENT_FORM_NO_DATA"], "recent_form_edge": 0.0, "short_form_edge": 0.0, "surface_recent_form_edge": 0.0, "opponent_quality_edge": 0.0, "form_confidence": 0.0}

try:
    from thinq.features.match_dynamics import build_match_dynamics_context
except Exception:
    def build_match_dynamics_context(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {
            "status": "NO_DATA",
            "source": None,
            "projected_sets": None,
            "projected_games": None,
            "tiebreak_probability": None,
            "decider_probability": None,
            "straight_sets_probability": None,
            "sets_edge": 0.0,
            "games_edge": 0.0,
            "confidence": 0.0,
            "flags": ["MATCH_DYNAMICS_UNAVAILABLE"],
        }


try:
    from thinq.loaders.ta_profile_loader import build_match_ta_context
except Exception:
    def build_match_ta_context(pick: str, opponent: str, surface: str = "") -> Dict[str, Any]:
        return {
            "ta_status": "N/A",
            "ta_pick_status": "N/A",
            "ta_opp_status": "N/A",
            "ta_pick_set_pct": None,
            "ta_opp_set_pct": None,
            "ta_pick_game_pct": None,
            "ta_opp_game_pct": None,
            "ta_pick_tb_split": None,
            "ta_opp_tb_split": None,
            "ta_pick_tb_pct": None,
            "ta_opp_tb_pct": None,
            "ta_pick_ace_pct": None,
            "ta_opp_ace_pct": None,
            "ta_pick_df_pct": None,
            "ta_opp_df_pct": None,
            "pick_ace_pct": None,
            "opponent_ace_pct": None,
            "pick_df_pct": None,
            "opponent_df_pct": None,
            "ta_pick_surface_dr": None,
            "ta_opp_surface_dr": None,
            "ta_pick_rpw_pct": None,
            "ta_opp_rpw_pct": None,
            "ta_pick_depth": None,
            "ta_opp_depth": None,
            "pick_aces_line": None,
            "opponent_aces_line": None,
            "total_aces_line": None,
            "aces_status": "N/A",
            "ta_winner_decision": "N/A",
            "ta_sets_decision": "N/A",
            "ta_games_decision": "N/A",
            "ta_tb_decision": "N/A",
            "ta_serve_return_pattern": "N/A",
            "ta_match_shape": "N/A",
            "ta_depth_label": "N/A",
            "ta_decision_confidence": 0.0,
            "ta_decision_notes": [],
        }

try:
    from thinq.features.probability_layer import build_thinq_probability_layer
except Exception:
    def build_thinq_probability_layer(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        pick = kwargs.get("pick") or ""
        opponent = kwargs.get("opponent") or ""
        return {
            "status": "NO_DATA",
            "model_version": "THINQ_PROBABILITY_UNAVAILABLE",
            "pick": pick,
            "opponent": opponent,
            "pick_probability": 0.50,
            "pick_probability_pct": 50.0,
            "opponent_probability": 0.50,
            "opponent_probability_pct": 50.0,
            "winner": pick,
            "winner_probability": 0.50,
            "winner_probability_pct": 50.0,
            "edge": 0.0,
            "confidence": 0.0,
            "components": {},
            "flags": ["THINQ_PROBABILITY_UNAVAILABLE"],
        }


def _flags_from_context(ctx: Dict[str, Any]) -> List[str]:
    value = ctx.get("flags") if isinstance(ctx, dict) else []
    return [str(x) for x in value if x] if isinstance(value, list) else ([str(value)] if value else [])


def _safe_elo_context(pick: str, opponent: str, surface: Optional[str]) -> Dict[str, Any]:
    try:
        ctx = build_elo_context(pick, opponent, surface)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["ELO_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "selected_elo_type": None,
            "overall_elo_edge": 0.0,
            "surface_elo_edge": 0.0,
            "elo_edge": 0.0,
            "flags": ["ELO_CONTEXT_FAILED", "MISSING_ELO"],
            "error": str(exc),
        }


def _safe_h2h_context(**kwargs: Any) -> Dict[str, Any]:
    try:
        ctx = build_h2h_context(**kwargs)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["H2H_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": "none",
            "total_matches": 0,
            "pick_wins": 0,
            "opponent_wins": 0,
            "edge": 0.0,
            "confidence": 0.0,
            "reason": "H2H context failed",
            "flags": ["H2H_CONTEXT_FAILED"],
            "error": str(exc),
        }


def _safe_recent_form_context(pick: str, opponent: str, surface: Optional[str], level: Optional[str], **kwargs: Any) -> Dict[str, Any]:
    try:
        ctx = build_recent_form_context(pick, opponent, surface, level, **kwargs)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["RECENT_FORM_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": None,
            "reason": "Recent form context failed",
            "recent_form_edge": 0.0,
            "short_form_edge": 0.0,
            "surface_recent_form_edge": 0.0,
            "opponent_quality_edge": 0.0,
            "form_confidence": 0.0,
            "form_data_depth": 0.0,
            "flags": ["RECENT_FORM_CONTEXT_FAILED", "RECENT_FORM_NO_DATA"],
            "history_status": {"status": "ERROR", "match_count": 0, "file_count": 0},
            "error": str(exc),
        }


def _safe_match_dynamics_context(**kwargs: Any) -> Dict[str, Any]:
    try:
        ctx = build_match_dynamics_context(**kwargs)
        return ctx if isinstance(ctx, dict) else {"status": "ERROR", "flags": ["MATCH_DYNAMICS_RETURNED_NON_DICT"]}
    except Exception as exc:
        return {
            "status": "ERROR",
            "source": None,
            "projected_sets": None,
            "projected_games": None,
            "sets_edge": 0.0,
            "games_edge": 0.0,
            "confidence": 0.0,
            "flags": ["MATCH_DYNAMICS_CONTEXT_FAILED"],
            "error": str(exc),
        }


def _safe_ta_context(pick: str, opponent: str, surface: str = "") -> Dict[str, Any]:
    """TA profile context is disabled for production model inputs.

    Policy: API PRO is the only external stats source for aces/DF/serve props.
    Keep TA-shaped keys as None only for compatibility with legacy render fields.
    """
    return {
        "ta_status": "DISABLED",
        "ta_pick_status": "DISABLED",
        "ta_opp_status": "DISABLED",
        "ta_pick_set_pct": None,
        "ta_opp_set_pct": None,
        "ta_pick_game_pct": None,
        "ta_opp_game_pct": None,
        "ta_pick_tb_split": None,
        "ta_opp_tb_split": None,
        "ta_pick_tb_pct": None,
        "ta_opp_tb_pct": None,
        "ta_pick_ace_pct": None,
        "ta_opp_ace_pct": None,
        "ta_pick_df_pct": None,
        "ta_opp_df_pct": None,
        "pick_ace_pct": None,
        "opponent_ace_pct": None,
        "pick_df_pct": None,
        "opponent_df_pct": None,
        "ta_pick_depth": None,
        "ta_opp_depth": None,
        "pick_aces_line": None,
        "opponent_aces_line": None,
        "total_aces_line": None,
        "aces_status": "DISABLED",
        "ta_decision_confidence": 0.0,
        "ta_decision_notes": ["TA_CONTEXT_DISABLED_API_PRO_ONLY"],
    }

def _first_non_null(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", "N/A", "—", "-"):
            return value
    return None


def _avg_pct(*values: Any) -> Optional[float]:
    nums: List[float] = []
    for value in values:
        try:
            if value not in (None, "", "N/A", "—", "-"):
                nums.append(float(value))
        except Exception:
            continue
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


def _ta_data_status(*values: Any) -> str:
    return "OK" if all(value not in (None, "", "N/A", "—", "-") for value in values) else "MISSING_TA_DATA"


def _ta_depth_pct(pick_depth: Any, opp_depth: Any) -> Optional[float]:
    avg = _avg_pct(pick_depth, opp_depth)
    if avg is None:
        return None
    return max(0.0, min(100.0, avg))

def normalize_surface(surface: Optional[str]) -> Dict[str, Any]:
    raw = str(surface or "").strip()
    text = raw.lower()
    flags: List[str] = []
    if "clay" in text:
        bucket = "Clay"
        elo_type = "clay_elo"
    elif "grass" in text:
        bucket = "Grass"
        elo_type = "grass_elo"
    elif "carpet" in text:
        bucket = "Hard"
        elo_type = "hard_elo"
        flags.append("CARPET_AS_HARD_FALLBACK")
    elif "hard" in text or "indoor" in text:
        bucket = "Hard"
        elo_type = "hard_elo"
    else:
        bucket = "Unknown"
        elo_type = "elo"
        flags.append("SURFACE_UNKNOWN")
    return {
        "surface": bucket,
        "surface_raw": raw or None,
        "surface_environment": None,
        "surface_model_bucket": bucket,
        "surface_source": "match_payload" if raw else "unknown",
        "surface_confidence": "MEDIUM" if raw else "LOW",
        "selected_elo_type": elo_type,
        "flags": flags,
    }




API_PRO_HOST = "tennisapi1.p.rapidapi.com"
API_PRO_BASE_URL = "https://tennisapi1.p.rapidapi.com"
API_PRO_TIMEOUT = 20
API_PRO_CACHE_DIR = Path("thinq/data/players/team_year_stats")
API_PRO_PREVIOUS_MATCHES_CACHE_DIR = Path("thinq/data/players/previous_matches")
API_PRO_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
API_PRO_PREVIOUS_MATCHES_MAX_PAGES = 2
API_PRO_PREVIOUS_MATCHES_SAMPLE = 12
API_PRO_PREVIOUS_MATCHES_MIN_SAMPLE = 3


def _api_pro_key() -> str:
    return os.getenv("RAPIDAPI_KEY", "").strip()


def _api_pro_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": API_PRO_HOST,
        "x-rapidapi-key": _api_pro_key(),
    }


def _team_stats_cache_path(team_id: Any, year: int) -> Path:
    API_PRO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return API_PRO_CACHE_DIR / f"{team_id}_{year}.json"


def _read_api_cache(path: Path) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        saved_at = float(payload.get("saved_at", 0))
        if time.time() - saved_at > API_PRO_CACHE_TTL_SECONDS:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_api_cache(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _fetch_team_year_statistics(team_id: Any, year: int, force_refresh: bool = False) -> Dict[str, Any]:
    if team_id in (None, ""):
        return {"status": "NO_TEAM_ID", "statistics": []}
    cache_path = _team_stats_cache_path(team_id, year)
    if not force_refresh:
        cached = _read_api_cache(cache_path)
        if isinstance(cached, dict):
            cached.setdefault("cache_path", str(cache_path))
            cached.setdefault("from_cache", True)
            return cached
    if not _api_pro_key():
        return {"status": "NO_API_KEY", "statistics": [], "cache_path": str(cache_path)}
    url = f"{API_PRO_BASE_URL}/api/tennis/team/{team_id}/year-statistics/{year}"
    try:
        response = requests.get(url, headers=_api_pro_headers(), timeout=API_PRO_TIMEOUT)
        status = response.status_code
        if status == 429:
            return {"status": "RATE_LIMITED", "statistics": [], "api_status_code": status, "cache_path": str(cache_path)}
        response.raise_for_status()
        payload = response.json()
        result = {"status": "OK", "payload": payload, "api_status_code": status, "cache_path": str(cache_path), "from_cache": False}
        _write_api_cache(cache_path, result)
        return result
    except Exception as exc:
        return {"status": "FETCH_FAILED", "statistics": [], "error": str(exc), "cache_path": str(cache_path)}



def _previous_matches_cache_path(player_id: Any, page: int) -> Path:
    API_PRO_PREVIOUS_MATCHES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return API_PRO_PREVIOUS_MATCHES_CACHE_DIR / f"{player_id}_{page}.json"


def _fetch_previous_player_matches(player_id: Any, page: int = 0, force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch API PRO getPreviousPlayerMatches.

    Endpoint pagination starts at page 0. Only the configured first pages are
    requested so the daily workflow remains quota-conscious; cached responses
    are reused for seven days.
    """
    if player_id in (None, ""):
        return {"status": "NO_PLAYER_ID", "events": [], "page": page}
    cache_path = _previous_matches_cache_path(player_id, page)
    if not force_refresh:
        cached = _read_api_cache(cache_path)
        if isinstance(cached, dict):
            cached.setdefault("cache_path", str(cache_path))
            cached.setdefault("from_cache", True)
            return cached
    if not _api_pro_key():
        return {"status": "NO_API_KEY", "events": [], "page": page, "cache_path": str(cache_path)}
    url = f"{API_PRO_BASE_URL}/api/tennis/player/{player_id}/events/previous/{page}"
    try:
        response = requests.get(url, headers=_api_pro_headers(), timeout=API_PRO_TIMEOUT)
        status = response.status_code
        if status == 429:
            return {"status": "RATE_LIMITED", "events": [], "page": page, "api_status_code": status, "cache_path": str(cache_path)}
        response.raise_for_status()
        payload = response.json()
        events = payload.get("events") if isinstance(payload, dict) else []
        result = {
            "status": "OK",
            "events": events if isinstance(events, list) else [],
            "has_next_page": bool(payload.get("hasNextPage")) if isinstance(payload, dict) else False,
            "page": page,
            "api_status_code": status,
            "cache_path": str(cache_path),
            "from_cache": False,
        }
        _write_api_cache(cache_path, result)
        return result
    except Exception as exc:
        return {"status": "FETCH_FAILED", "events": [], "page": page, "error": str(exc), "cache_path": str(cache_path)}


def _as_of_timestamp(as_of_date: Any) -> Optional[int]:
    if as_of_date in (None, ""):
        return None
    try:
        text = str(as_of_date).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def _completed_singles_score_shape(event: Dict[str, Any], as_of_ts: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(event, dict):
        return None
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    if str(status.get("type") or "").lower() != "finished":
        return None
    description = str(status.get("description") or "").lower()
    if any(word in description for word in ("retired", "walkover", "canceled", "cancelled", "postponed", "abandoned")):
        return None
    filters = event.get("eventFilters") if isinstance(event.get("eventFilters"), dict) else {}
    categories = [str(x).lower() for x in (filters.get("category") or [])]
    if categories and "singles" not in categories:
        return None
    start_ts = event.get("startTimestamp")
    try:
        start_ts_int = int(start_ts)
    except Exception:
        start_ts_int = 0
    if as_of_ts is not None and start_ts_int and start_ts_int >= as_of_ts:
        return None
    home = event.get("homeScore") if isinstance(event.get("homeScore"), dict) else {}
    away = event.get("awayScore") if isinstance(event.get("awayScore"), dict) else {}
    set_games: List[int] = []
    tiebreak_sets = 0
    for idx in range(1, 6):
        hk, ak = f"period{idx}", f"period{idx}"
        if home.get(hk) in (None, "") or away.get(ak) in (None, ""):
            continue
        try:
            hg, ag = int(home.get(hk)), int(away.get(ak))
        except Exception:
            return None
        if hg < 0 or ag < 0 or hg + ag < 6:
            return None
        set_games.append(hg + ag)
        if home.get(f"period{idx}TieBreak") not in (None, "") or away.get(f"period{idx}TieBreak") not in (None, ""):
            tiebreak_sets += 1
    if not set_games:
        return None
    return {
        "event_id": event.get("id"),
        "start_timestamp": start_ts_int or None,
        "surface": _surface_bucket(event.get("groundType") or ((event.get("tournament") or {}).get("uniqueTournament") or {}).get("groundType")),
        "sets": len(set_games),
        "games": sum(set_games),
        "tiebreak_sets": tiebreak_sets,
    }


def _build_previous_matches_shape(player_id: Any, surface: Any, as_of_date: Any = None, force_refresh: bool = False) -> Dict[str, Any]:
    requested_surface = _surface_bucket(surface)
    as_of_ts = _as_of_timestamp(as_of_date)
    events: List[Dict[str, Any]] = []
    pages: List[Dict[str, Any]] = []
    for page in range(API_PRO_PREVIOUS_MATCHES_MAX_PAGES):
        result = _fetch_previous_player_matches(player_id, page=page, force_refresh=force_refresh)
        pages.append(result)
        events.extend([x for x in result.get("events", []) if isinstance(x, dict)])
        if result.get("status") != "OK" or not result.get("has_next_page"):
            break
        current_shapes = [x for x in (_completed_singles_score_shape(e, as_of_ts=as_of_ts) for e in events) if isinstance(x, dict)]
        current_surface_count = sum(1 for x in current_shapes if x.get("surface") == requested_surface and requested_surface != "Unknown")
        if len(current_shapes) >= 20 and current_surface_count >= 8:
            break
    shapes = [x for x in (_completed_singles_score_shape(e, as_of_ts=as_of_ts) for e in events) if isinstance(x, dict)]
    shapes.sort(key=lambda x: int(x.get("start_timestamp") or 0), reverse=True)
    surface_shapes = [x for x in shapes if x.get("surface") == requested_surface and requested_surface != "Unknown"]
    selected = surface_shapes[:API_PRO_PREVIOUS_MATCHES_SAMPLE]
    scope = "surface"
    if len(selected) < API_PRO_PREVIOUS_MATCHES_MIN_SAMPLE:
        selected = shapes[:API_PRO_PREVIOUS_MATCHES_SAMPLE]
        scope = "overall"
    sample = len(selected)
    status = "OK" if sample >= API_PRO_PREVIOUS_MATCHES_MIN_SAMPLE else "LOW_SAMPLE" if sample > 0 else "NO_DATA"
    avg_games = round(sum(float(x["games"]) for x in selected) / sample, 2) if sample else None
    avg_sets = round(sum(float(x["sets"]) for x in selected) / sample, 2) if sample else None
    tb_rate = round(sum(1 for x in selected if int(x.get("tiebreak_sets") or 0) > 0) / sample, 4) if sample else None
    decider_rate = round(sum(1 for x in selected if int(x.get("sets") or 0) >= 3) / sample, 4) if sample else None
    games_over_22_5_rate = round(sum(1 for x in selected if float(x.get("games") or 0) > 22.5) / sample, 4) if sample else None
    return {
        "status": status,
        "source": "API_PRO_GET_PREVIOUS_PLAYER_MATCHES",
        "scope": scope,
        "requested_surface": requested_surface,
        "sample": sample,
        "average_games": avg_games if status == "OK" else None,
        "average_sets": avg_sets if status == "OK" else None,
        "tiebreak_match_rate": tb_rate if status == "OK" else None,
        "decider_match_rate": decider_rate if status == "OK" else None,
        "games_over_22_5_rate": games_over_22_5_rate if status == "OK" else None,
        "valid_events": len(shapes),
        "raw_events": len(events),
        "pages_fetched": len(pages),
        "cache_paths": [x.get("cache_path") for x in pages if x.get("cache_path")],
        "api_statuses": [x.get("status") for x in pages],
    }


def _combined_previous_matches_projection(pick_shape: Dict[str, Any], opponent_shape: Dict[str, Any]) -> Optional[float]:
    values = [x.get("average_games") for x in (pick_shape, opponent_shape) if x.get("status") == "OK" and x.get("average_games") is not None]
    if len(values) < 2:
        return None
    return round(sum(float(x) for x in values) / len(values), 2)

def _iter_stat_dicts(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        if any(k in obj for k in ("aces", "doubleFaults", "totalServeAttempts", "matches", "groundType")):
            out.append(obj)
        for value in obj.values():
            out.extend(_iter_stat_dicts(value))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_iter_stat_dicts(item))
    return out


def _surface_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "clay" in text or "red clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "hard" in text or "indoor" in text or "carpet" in text:
        return "Hard"
    return "Unknown"


def _stat_num(stat: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        try:
            value = stat.get(key)
            if value not in (None, ""):
                return float(value)
        except Exception:
            continue
    return 0.0


def _aggregate_team_stats(stats: List[Dict[str, Any]], requested_surface: Any = None, min_matches: int = 3) -> Dict[str, Any]:
    requested_bucket = _surface_bucket(requested_surface)
    usable = [s for s in stats if isinstance(s, dict)]
    surface_rows = [s for s in usable if _surface_bucket(s.get("groundType") or s.get("surface")) == requested_bucket and requested_bucket != "Unknown"]
    selected = surface_rows if sum(_stat_num(s, "matches") for s in surface_rows) >= min_matches else usable
    source_scope = "surface" if selected is surface_rows and selected else "overall"
    aces = sum(_stat_num(s, "aces") for s in selected)
    dfs = sum(_stat_num(s, "doubleFaults", "double_faults", "doubleFault") for s in selected)
    serves = sum(_stat_num(s, "totalServeAttempts", "serveAttempts", "servicePoints", "totalServicePoints") for s in selected)
    matches = sum(_stat_num(s, "matches") for s in selected)
    ace_pct = round(aces / serves * 100.0, 2) if serves > 0 else None
    df_pct = round(dfs / serves * 100.0, 2) if serves > 0 else None
    return {
        "status": "OK" if serves > 0 and (ace_pct is not None or df_pct is not None) else "NO_SERVE_STATS",
        "scope": source_scope,
        "requested_surface_bucket": requested_bucket,
        "rows": len(selected),
        "matches": int(matches),
        "aces": int(aces),
        "double_faults": int(dfs),
        "total_serve_attempts": int(serves),
        "ace_pct": ace_pct,
        "df_pct": df_pct,
        "ground_types": sorted({str(s.get("groundType") or s.get("surface") or "").strip() for s in selected if str(s.get("groundType") or s.get("surface") or "").strip()}),
    }


def _season_year(as_of_date: Any = None) -> int:
    text = str(as_of_date or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return datetime.now(timezone.utc).year


def _project_serve_prop(pct: Any, projected_games: Any) -> Optional[float]:
    try:
        p = float(pct)
        g = float(projected_games)
        if p <= 0 or g <= 0:
            return None
        service_points = (g / 2.0) * 6.2
        return round(service_points * (p / 100.0), 1)
    except Exception:
        return None


def build_api_pro_serve_stats_context(
    pick_player_id: Any,
    opponent_player_id: Any,
    surface: Any,
    projected_games: Any,
    as_of_date: Any = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    year = _season_year(as_of_date)
    pick_previous_shape = _build_previous_matches_shape(pick_player_id, surface, as_of_date=as_of_date, force_refresh=force_refresh)
    opp_previous_shape = _build_previous_matches_shape(opponent_player_id, surface, as_of_date=as_of_date, force_refresh=force_refresh)
    supplied_games = projected_games
    if supplied_games in (None, "", 0, 0.0):
        projected_games = _combined_previous_matches_projection(pick_previous_shape, opp_previous_shape)
    games_source = "UPSTREAM_REAL_PROJECTION" if supplied_games not in (None, "", 0, 0.0) else "API_PRO_PREVIOUS_MATCHES" if projected_games is not None else "NO_REAL_GAMES_SAMPLE"
    pick_raw = _fetch_team_year_statistics(pick_player_id, year, force_refresh=force_refresh)
    opp_raw = _fetch_team_year_statistics(opponent_player_id, year, force_refresh=force_refresh)
    # If current year is thin or missing, try previous year. This matters in early season and for players with sparse 2026 sample.
    pick_stats = _aggregate_team_stats(_iter_stat_dicts(pick_raw.get("payload", pick_raw)), requested_surface=surface)
    opp_stats = _aggregate_team_stats(_iter_stat_dicts(opp_raw.get("payload", opp_raw)), requested_surface=surface)
    if pick_stats.get("status") != "OK" and year > 2000:
        pick_prev_raw = _fetch_team_year_statistics(pick_player_id, year - 1, force_refresh=force_refresh)
        pick_prev_stats = _aggregate_team_stats(_iter_stat_dicts(pick_prev_raw.get("payload", pick_prev_raw)), requested_surface=surface)
        if pick_prev_stats.get("status") == "OK":
            pick_raw = pick_prev_raw
            pick_stats = pick_prev_stats
            pick_stats["year"] = year - 1
    else:
        pick_stats["year"] = year
    if opp_stats.get("status") != "OK" and year > 2000:
        opp_prev_raw = _fetch_team_year_statistics(opponent_player_id, year - 1, force_refresh=force_refresh)
        opp_prev_stats = _aggregate_team_stats(_iter_stat_dicts(opp_prev_raw.get("payload", opp_prev_raw)), requested_surface=surface)
        if opp_prev_stats.get("status") == "OK":
            opp_raw = opp_prev_raw
            opp_stats = opp_prev_stats
            opp_stats["year"] = year - 1
    else:
        opp_stats["year"] = year
    pick_aces = _project_serve_prop(pick_stats.get("ace_pct"), projected_games)
    opp_aces = _project_serve_prop(opp_stats.get("ace_pct"), projected_games)
    pick_df = _project_serve_prop(pick_stats.get("df_pct"), projected_games)
    opp_df = _project_serve_prop(opp_stats.get("df_pct"), projected_games)
    return {
        "api_serve_stats_source": "API_PRO_TEAM_YEAR_STATS",
        "serve_props_source_policy": "API_PRO_ONLY_NO_TA_NO_BET365_FALLBACK",
        "api_previous_matches_source": "API_PRO_GET_PREVIOUS_PLAYER_MATCHES",
        "api_previous_matches_games_source": games_source,
        "api_previous_matches_projected_games": projected_games,
        "api_pick_previous_matches_status": pick_previous_shape.get("status"),
        "api_opp_previous_matches_status": opp_previous_shape.get("status"),
        "api_pick_previous_matches_scope": pick_previous_shape.get("scope"),
        "api_opp_previous_matches_scope": opp_previous_shape.get("scope"),
        "api_pick_previous_matches_sample": pick_previous_shape.get("sample"),
        "api_opp_previous_matches_sample": opp_previous_shape.get("sample"),
        "api_pick_previous_average_games": pick_previous_shape.get("average_games"),
        "api_opp_previous_average_games": opp_previous_shape.get("average_games"),
        "api_pick_previous_average_sets": pick_previous_shape.get("average_sets"),
        "api_opp_previous_average_sets": opp_previous_shape.get("average_sets"),
        "api_pick_previous_tiebreak_rate": pick_previous_shape.get("tiebreak_match_rate"),
        "api_opp_previous_tiebreak_rate": opp_previous_shape.get("tiebreak_match_rate"),
        "api_serve_stats_status": "OK" if pick_stats.get("status") == "OK" and opp_stats.get("status") == "OK" else "PARTIAL",
        "api_pick_serve_stats_status": pick_stats.get("status"),
        "api_opp_serve_stats_status": opp_stats.get("status"),
        "api_pick_ace_pct": pick_stats.get("ace_pct"),
        "api_opp_ace_pct": opp_stats.get("ace_pct"),
        "api_pick_df_pct": pick_stats.get("df_pct"),
        "api_opp_df_pct": opp_stats.get("df_pct"),
        "api_pick_serve_matches": pick_stats.get("matches"),
        "api_opp_serve_matches": opp_stats.get("matches"),
        "api_pick_serve_attempts": pick_stats.get("total_serve_attempts"),
        "api_opp_serve_attempts": opp_stats.get("total_serve_attempts"),
        "api_pick_serve_scope": pick_stats.get("scope"),
        "api_opp_serve_scope": opp_stats.get("scope"),
        "api_pick_serve_year": pick_stats.get("year", year),
        "api_opp_serve_year": opp_stats.get("year", year),
        "api_pick_serve_cache_path": pick_raw.get("cache_path"),
        "api_opp_serve_cache_path": opp_raw.get("cache_path"),
        "api_pick_serve_api_status": pick_raw.get("api_status_code"),
        "api_opp_serve_api_status": opp_raw.get("api_status_code"),
        "pick_aces_projection": pick_aces,
        "opponent_aces_projection": opp_aces,
        "total_aces_projection": round(pick_aces + opp_aces, 1) if pick_aces is not None and opp_aces is not None else None,
        "pick_df_projection": pick_df,
        "opponent_df_projection": opp_df,
        "total_df_projection": round(pick_df + opp_df, 1) if pick_df is not None and opp_df is not None else None,
        "aces_status": "OK" if pick_aces is not None and opp_aces is not None else "MISSING_API_SERVE_STATS",
        "df_status": "OK" if pick_df is not None and opp_df is not None else "MISSING_API_SERVE_STATS",
    }

class ThinqService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def build_match_features(
        self,
        player1: str,
        player2: str,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        tournament_url: Optional[str] = None,
        tour_type: Optional[str] = None,
        as_of_date: Optional[str] = None,
        event_id: Optional[Any] = None,
        event_custom_id: Optional[Any] = None,
        player1_id: Optional[Any] = None,
        player2_id: Optional[Any] = None,
        tournament_id: Optional[Any] = None,
        best_of: int = 3,
        save_snapshot: bool = False,
        pick: Optional[str] = None,
        opponent: Optional[str] = None,
        pick_side: Optional[str] = None,
        opponent_side: Optional[str] = None,
        side_audit: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        analysis_pick = pick or player1
        analysis_opponent = opponent or (player2 if analysis_pick == player1 else player1)
        thinq_side = side_audit or build_side_audit(
            {
                "player1": player1,
                "player2": player2,
                "pick": analysis_pick,
                "opponent": analysis_opponent,
                "pick_side": pick_side,
                "opponent_side": opponent_side,
            }
        )

        raw_payload = kwargs.get("raw") or kwargs.get("match_raw") or kwargs.get("raw_event") or {}
        if not event_custom_id:
            event_custom_id = kwargs.get("event_custom_id") or kwargs.get("custom_id") or kwargs.get("customId")
        if not event_custom_id and isinstance(raw_payload, dict):
            event_custom_id = raw_payload.get("customId") or raw_payload.get("custom_id")

        canonical_pick_side = str(pick_side or thinq_side.get("pick_side") or "").upper().strip()
        if canonical_pick_side == "HOME":
            pick_player_id = player1_id
            opponent_player_id = player2_id
        elif canonical_pick_side == "AWAY":
            pick_player_id = player2_id
            opponent_player_id = player1_id
        else:
            # Legacy fallback: preserve old behavior when no valid side is available.
            pick_player_id = player1_id
            opponent_player_id = player2_id

        surface_ctx = normalize_surface(surface)
        surface_bucket = surface_ctx.get("surface") or surface
        elo = _safe_elo_context(analysis_pick, analysis_opponent, surface_bucket)
        h2h = _safe_h2h_context(
            event_id=event_id,
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            player1_id=pick_player_id,
            player2_id=opponent_player_id,
            event_custom_id=event_custom_id,
        )
        recent_form = _safe_recent_form_context(
            analysis_pick,
            analysis_opponent,
            surface_bucket,
            level,
            pick_player_id=pick_player_id,
            opponent_player_id=opponent_player_id,
            event_id=event_id,
            event_custom_id=event_custom_id,
            match_start=kwargs.get("match_start") or kwargs.get("start_time") or as_of_date,
            as_of_date=as_of_date,
            force_refresh_api_recent_form=bool(kwargs.get("force_refresh_api_recent_form", False)),
        )
        match_dynamics = _safe_match_dynamics_context(
            pick=analysis_pick,
            opponent=analysis_opponent,
            surface=surface_bucket,
            best_of=best_of,
            elo=elo,
            h2h=h2h,
            recent_form=recent_form,
            odds_player1=kwargs.get("odds_player1") or kwargs.get("p1_odds") or kwargs.get("odds1") or kwargs.get("home_odds"),
            odds_player2=kwargs.get("odds_player2") or kwargs.get("p2_odds") or kwargs.get("odds2") or kwargs.get("away_odds"),
            pick_odds=kwargs.get("pick_odds") or kwargs.get("odds"),
            opponent_odds=kwargs.get("opponent_odds"),
        )
        ta_context = _safe_ta_context(analysis_pick, analysis_opponent, str(surface_bucket or ""))
        try:
            api_serve_stats = build_api_pro_serve_stats_context(
                pick_player_id=pick_player_id,
                opponent_player_id=opponent_player_id,
                surface=surface_bucket,
                projected_games=(
                    match_dynamics.get("projected_games")
                    or kwargs.get("projected_games")
                    or kwargs.get("projected_total_games")
                    or kwargs.get("games_line")
                    or kwargs.get("total_games_line")
                ),
                as_of_date=as_of_date,
                force_refresh=bool(kwargs.get("force_refresh_api_serve_stats", False)),
            )
        except Exception as exc:
            api_serve_stats = {
                "api_serve_stats_source": "API_PRO_TEAM_YEAR_STATS",
                "api_serve_stats_status": "ERROR",
                "api_serve_stats_error": str(exc),
                "api_pick_ace_pct": None,
                "api_opp_ace_pct": None,
                "api_pick_df_pct": None,
                "api_opp_df_pct": None,
                "api_pick_serve_matches": None,
                "api_opp_serve_matches": None,
                "api_pick_serve_attempts": None,
                "api_opp_serve_attempts": None,
                "api_pick_serve_scope": None,
                "api_opp_serve_scope": None,
                "api_pick_serve_year": None,
                "api_opp_serve_year": None,
                "pick_aces_projection": None,
                "opponent_aces_projection": None,
                "total_aces_projection": None,
                "pick_df_projection": None,
                "opponent_df_projection": None,
                "total_df_projection": None,
                "aces_status": "MISSING_API_SERVE_STATS",
                "df_status": "MISSING_API_SERVE_STATS",
            }

        edges = {
            "overall_elo_edge": float(elo.get("overall_elo_edge") or 0.0),
            "surface_elo_edge": float(elo.get("surface_elo_edge") or 0.0),
            "elo_edge": float(elo.get("elo_edge") or 0.0),
            "h2h_edge": float(h2h.get("effective_edge", h2h.get("edge")) or 0.0),
            "recent_form_edge": float(recent_form.get("effective_recent_form_edge", recent_form.get("recent_form_edge")) or 0.0),
            "short_form_edge": float(recent_form.get("effective_short_form_edge", recent_form.get("short_form_edge")) or 0.0),
            "surface_recent_form_edge": float(recent_form.get("effective_surface_recent_form_edge", recent_form.get("surface_recent_form_edge")) or 0.0),
            "opponent_quality_edge": float(recent_form.get("effective_opponent_quality_edge", recent_form.get("opponent_quality_edge")) or 0.0),
            "sets_edge": float(match_dynamics.get("sets_edge") or 0.0),
            "games_edge": float(match_dynamics.get("games_edge") or 0.0),
        }

        flags: List[str] = []
        flags.extend(surface_ctx.get("flags") or [])
        flags.extend(elo.get("flags") or [])
        flags.extend(recent_form.get("flags") or [])
        flags.extend(match_dynamics.get("flags") or [])
        if h2h.get("status") == "NO_PREVIOUS_H2H":
            flags.append("NO_PREVIOUS_H2H")
        elif h2h.get("status") != "OK":
            flags.append("NO_H2H_DATA")
        if recent_form.get("status") != "OK":
            flags.append("RECENT_FORM_NO_DATA")
        if not thinq_side.get("side_valid"):
            flags.append("THINQ_SIDE_ORIENTATION_INVALID")

        confidence = 0.20
        if elo.get("status") == "OK":
            confidence += 0.35
        if h2h.get("status") == "OK":
            confidence += 0.10
        if recent_form.get("status") == "OK":
            confidence += min(float(recent_form.get("form_confidence") or 0.0) * 0.25, 0.18)
        if match_dynamics.get("status") == "OK":
            confidence += min(float(match_dynamics.get("confidence") or 0.0) * 0.08, 0.06)
        if surface_ctx.get("surface") != "Unknown":
            confidence += 0.05
        if not thinq_side.get("side_valid"):
            # Do not let a side-orientation problem produce a high-confidence signal.
            confidence = min(confidence, 0.35)
        confidence = round(max(min(confidence, 0.88), 0.0), 4)

        thinq_probability_layer = build_thinq_probability_layer(
            pick=analysis_pick,
            opponent=analysis_opponent,
            pick_side=pick_side,
            opponent_side=opponent_side,
            edges=edges,
            confidence=confidence,
            elo=elo,
            h2h=h2h,
            recent_form=recent_form,
            match_dynamics=match_dynamics,
            flags=flags,
        )

        return {
            "available": True,
            "error": None,
            "confidence": confidence,
            "thinq_data_confidence": confidence,
            "thinq_data_confidence_pct": round(confidence * 100.0, 2),
            "thinq_side": thinq_side,
            "surface": surface_ctx,
            "elo": elo,
            "h2h": {
                "status": h2h.get("status"),
                "source": h2h.get("source"),
                "total_matches": h2h.get("total_matches", 0),
                "pick_wins": h2h.get("pick_wins", 0),
                "opponent_wins": h2h.get("opponent_wins", 0),
                "pick_win_pct": h2h.get("pick_win_pct"),
                "same_surface_matches": h2h.get("same_surface_matches"),
                "same_surface_pick_wins": h2h.get("same_surface_pick_wins"),
                "same_surface_opponent_wins": h2h.get("same_surface_opponent_wins"),
                "same_surface_pick_win_pct": h2h.get("same_surface_pick_win_pct"),
                "same_surface_edge": h2h.get("same_surface_edge", 0.0),
                "h2h_requested_surface": h2h.get("h2h_requested_surface"),
                "h2h_requested_surface_bucket": h2h.get("h2h_requested_surface_bucket"),
                "h2h_detected_surface_buckets": h2h.get("h2h_detected_surface_buckets") or [],
                "h2h_missing_surface_matches": h2h.get("h2h_missing_surface_matches"),
                "edge": h2h.get("edge", 0.0),
                "confidence": h2h.get("confidence", 0.0),
                "reason": h2h.get("reason"),
                "endpoint": h2h.get("endpoint"),
                "params": h2h.get("params"),
                "endpoint_attempts": h2h.get("endpoint_attempts") or [],
                "api_status_code": h2h.get("api_status_code"),
                "api_error": h2h.get("api_error"),
                "cache_path": h2h.get("cache_path"),
                "requested_event_id": h2h.get("requested_event_id"),
                "requested_event_custom_id": h2h.get("requested_event_custom_id"),
                "requested_player1_id": h2h.get("requested_player1_id"),
                "requested_player2_id": h2h.get("requested_player2_id"),
                "h2h_raw_event_count": h2h.get("h2h_raw_event_count"),
                "h2h_finished_event_count": h2h.get("h2h_finished_event_count"),
                "h2h_usable_event_count": h2h.get("h2h_usable_event_count"),
                "h2h_excluded_event_count": h2h.get("h2h_excluded_event_count"),
                "h2h_excluded_reasons": h2h.get("h2h_excluded_reasons") or {},
                "h2h_score_shape_status": h2h.get("h2h_score_shape_status"),
                "h2h_score_shape_source": h2h.get("h2h_score_shape_source"),
                "h2h_score_shape_sample": h2h.get("h2h_score_shape_sample"),
                "h2h_score_shape_quality": h2h.get("h2h_score_shape_quality"),
                "h2h_projected_sets": h2h.get("h2h_projected_sets"),
                "h2h_projected_games": h2h.get("h2h_projected_games"),
                "h2h_tiebreak_probability": h2h.get("h2h_tiebreak_probability"),
                "h2h_decider_probability": h2h.get("h2h_decider_probability"),
                "h2h_all_score_sample": h2h.get("h2h_all_score_sample"),
                "h2h_same_surface_score_sample": h2h.get("h2h_same_surface_score_sample"),
            },
            "recent_form": recent_form,
            "match_dynamics": match_dynamics,
            "thinq_probability_layer": thinq_probability_layer,
            "probability_layer": thinq_probability_layer,
            "contexts": {
                "match_dynamics": match_dynamics,
                "h2h": h2h,
                "recent_form": recent_form,
                "elo": elo,
                "thinq_probability_layer": thinq_probability_layer,
                "ta_context": ta_context,
                "api_serve_stats": api_serve_stats,
            },
            "edges": edges,
            "flags": sorted(set(flags)),
            "thinq_available": True,
            "thinq_probability_status": thinq_probability_layer.get("status"),
            "thinq_model_version": thinq_probability_layer.get("model_version"),
            "thinq_pick_probability": thinq_probability_layer.get("pick_probability"),
            "thinq_pick_probability_pct": thinq_probability_layer.get("pick_probability_pct"),
            "thinq_probability": thinq_probability_layer.get("pick_probability"),
            "thinq_probability_pct": thinq_probability_layer.get("pick_probability_pct"),
            "thinq_winner": thinq_probability_layer.get("winner"),
            "thinq_winner_side": thinq_probability_layer.get("winner_side"),
            "thinq_winner_probability": thinq_probability_layer.get("winner_probability"),
            "thinq_winner_probability_pct": thinq_probability_layer.get("winner_probability_pct"),
            "thinq_edge": thinq_probability_layer.get("edge"),
            "thinq_probability_confidence": thinq_probability_layer.get("confidence"),
            "thinq_probability_components": thinq_probability_layer.get("components"),
            "thinq_confidence": confidence,
            "thinq_data_confidence": confidence,
            "thinq_data_confidence_pct": round(confidence * 100.0, 2),
            "thinq_selected_elo_type": elo.get("selected_elo_type"),
            "thinq_elo_pick": elo.get("pick_elo"),
            "thinq_elo_opponent": elo.get("opponent_elo"),
            "thinq_yelo_pick": elo.get("pick_yelo"),
            "thinq_yelo_opponent": elo.get("opponent_yelo"),
            "thinq_overall_elo_edge": edges["overall_elo_edge"],
            "thinq_surface_elo_edge": edges["surface_elo_edge"],
            "thinq_elo_edge": edges["elo_edge"],
            "thinq_h2h_status": h2h.get("status"),
            "thinq_h2h_source": h2h.get("source"),
            "thinq_h2h_total_matches": h2h.get("total_matches", 0),
            "thinq_h2h_pick_wins": h2h.get("pick_wins", 0),
            "thinq_h2h_opponent_wins": h2h.get("opponent_wins", 0),
            "thinq_h2h_same_surface_matches": h2h.get("same_surface_matches", 0),
            "thinq_surface_h2h_pick_wins": h2h.get("same_surface_pick_wins", 0),
            "thinq_surface_h2h_opponent_wins": h2h.get("same_surface_opponent_wins", 0),
            "thinq_surface_h2h_pick_win_pct": h2h.get("same_surface_pick_win_pct"),
            "thinq_surface_h2h_raw_edge": h2h.get("same_surface_raw_edge"),
            "thinq_surface_h2h_effective_edge": h2h.get("same_surface_effective_edge", h2h.get("same_surface_edge", 0.0)),
            "thinq_surface_h2h_edge": h2h.get("same_surface_effective_edge", h2h.get("same_surface_edge", 0.0)),
            "thinq_surface_h2h_sample_quality": h2h.get("same_surface_sample_quality"),
            "thinq_h2h_requested_surface_bucket": h2h.get("h2h_requested_surface_bucket"),
            "thinq_h2h_detected_surface_buckets": h2h.get("h2h_detected_surface_buckets") or [],
            "thinq_h2h_missing_surface_matches": h2h.get("h2h_missing_surface_matches"),
            "thinq_h2h_raw_edge": h2h.get("raw_edge", edges["h2h_edge"]),
            "thinq_h2h_effective_edge": h2h.get("effective_edge", edges["h2h_edge"]),
            "thinq_h2h_edge": edges["h2h_edge"],
            "thinq_h2h_sample_cap": h2h.get("sample_cap"),
            "thinq_h2h_sample_quality": h2h.get("sample_quality"),
            "thinq_h2h_confidence": h2h.get("confidence", 0.0),
            "thinq_h2h_endpoint": h2h.get("endpoint"),
            "thinq_h2h_params": h2h.get("params"),
            "thinq_h2h_endpoint_attempts": h2h.get("endpoint_attempts") or [],
            "thinq_h2h_api_status_code": h2h.get("api_status_code"),
            "thinq_h2h_api_error": h2h.get("api_error"),
            "thinq_h2h_cache_path": h2h.get("cache_path"),
            "thinq_h2h_requested_event_id": h2h.get("requested_event_id"),
            "thinq_h2h_requested_event_custom_id": h2h.get("requested_event_custom_id"),
            "thinq_recent_form_edge": edges["recent_form_edge"],
            "thinq_short_form_edge": edges["short_form_edge"],
            "thinq_surface_recent_form_edge": edges["surface_recent_form_edge"],
            "thinq_opponent_quality_edge": edges["opponent_quality_edge"],
            "thinq_sets_edge": edges["sets_edge"],
            "thinq_games_edge": edges["games_edge"],
            "thinq_projected_sets": match_dynamics.get("projected_sets"),
            "thinq_projected_games": match_dynamics.get("projected_games"),
            "thinq_tiebreak_probability": match_dynamics.get("tiebreak_probability"),
            "thinq_decider_probability": match_dynamics.get("decider_probability"),
            "thinq_straight_sets_probability": match_dynamics.get("straight_sets_probability"),
            "thinq_match_shape": match_dynamics.get("match_shape"),
            "thinq_match_dynamics_confidence": match_dynamics.get("confidence", 0.0),
            "thinq_form_confidence": recent_form.get("form_confidence", 0.0),
            "recent_form_source": recent_form.get("source"),
            "recent_form_freshness_status": recent_form.get("recent_form_freshness_status"),
            "pick_local_last_match_date": recent_form.get("pick_local_last_match_date"),
            "opponent_local_last_match_date": recent_form.get("opponent_local_last_match_date"),
            "pick_local_days_old": recent_form.get("pick_local_days_old"),
            "opponent_local_days_old": recent_form.get("opponent_local_days_old"),
            "pick_api_last10_record": recent_form.get("pick_api_last10_record"),
            "opponent_api_last10_record": recent_form.get("opponent_api_last10_record"),
            "pick_api_surface_record": recent_form.get("pick_api_surface_record"),
            "opponent_api_surface_record": recent_form.get("opponent_api_surface_record"),
            "pick_api_last_match_date": recent_form.get("pick_api_last_match_date"),
            "opponent_api_last_match_date": recent_form.get("opponent_api_last_match_date"),
            "pick_api_status": recent_form.get("pick_api_status"),
            "opponent_api_status": recent_form.get("opponent_api_status"),
            "pick_api_event_count": recent_form.get("pick_api_event_count"),
            "opponent_api_event_count": recent_form.get("opponent_api_event_count"),
            "pick_api_usable_match_count": recent_form.get("pick_api_usable_match_count"),
            "opponent_api_usable_match_count": recent_form.get("opponent_api_usable_match_count"),
            "ta_context": ta_context,
            "thinq_ta_context": ta_context,
            "ta_status": ta_context.get("ta_status"),
            "ta_pick_status": ta_context.get("ta_pick_status"),
            "ta_opp_status": ta_context.get("ta_opp_status"),
            "ta_pick_set_pct": ta_context.get("ta_pick_set_pct"),
            "ta_opp_set_pct": ta_context.get("ta_opp_set_pct"),
            "ta_pick_game_pct": ta_context.get("ta_pick_game_pct"),
            "ta_opp_game_pct": ta_context.get("ta_opp_game_pct"),
            "ta_pick_tb_split": ta_context.get("ta_pick_tb_split"),
            "ta_opp_tb_split": ta_context.get("ta_opp_tb_split"),
            "ta_pick_tb_pct": ta_context.get("ta_pick_tb_pct"),
            "ta_opp_tb_pct": ta_context.get("ta_opp_tb_pct"),
            "ta_pick_ace_pct": ta_context.get("ta_pick_ace_pct"),
            "ta_opp_ace_pct": ta_context.get("ta_opp_ace_pct"),
            "ta_pick_df_pct": ta_context.get("ta_pick_df_pct"),
            "ta_opp_df_pct": ta_context.get("ta_opp_df_pct"),
            "api_serve_stats": api_serve_stats,
            "api_serve_stats_source": api_serve_stats.get("api_serve_stats_source"),
            "api_serve_stats_status": api_serve_stats.get("api_serve_stats_status"),
            "aces_source": "API_PRO_TEAM_YEAR_STATS" if api_serve_stats.get("aces_status") == "OK" else "NO_DATA",
            "df_source": "API_PRO_TEAM_YEAR_STATS" if api_serve_stats.get("df_status") == "OK" else "NO_DATA",
            "serve_props_source_policy": "API_PRO_ONLY_NO_FALLBACK",
            "api_pick_ace_pct": api_serve_stats.get("api_pick_ace_pct"),
            "api_opp_ace_pct": api_serve_stats.get("api_opp_ace_pct"),
            "api_pick_df_pct": api_serve_stats.get("api_pick_df_pct"),
            "api_opp_df_pct": api_serve_stats.get("api_opp_df_pct"),
            "api_pick_serve_matches": api_serve_stats.get("api_pick_serve_matches"),
            "api_opp_serve_matches": api_serve_stats.get("api_opp_serve_matches"),
            "api_pick_serve_attempts": api_serve_stats.get("api_pick_serve_attempts"),
            "api_opp_serve_attempts": api_serve_stats.get("api_opp_serve_attempts"),
            "api_pick_serve_scope": api_serve_stats.get("api_pick_serve_scope"),
            "api_opp_serve_scope": api_serve_stats.get("api_opp_serve_scope"),
            "api_pick_serve_year": api_serve_stats.get("api_pick_serve_year"),
            "api_opp_serve_year": api_serve_stats.get("api_opp_serve_year"),
            # Compatibility aliases consumed by the Sets/Games/Aces/DF layers. Prefer TA if available, otherwise API PRO team yearly stats.
            "pick_ace_pct": api_serve_stats.get("api_pick_ace_pct"),
            "opponent_ace_pct": api_serve_stats.get("api_opp_ace_pct"),
            "pick_df_pct": api_serve_stats.get("api_pick_df_pct"),
            "opponent_df_pct": api_serve_stats.get("api_opp_df_pct"),
            "pick_tb_pct": None,
            "opponent_tb_pct": None,
            "tb_probability": match_dynamics.get("tiebreak_probability"),
            "tiebreak_probability": match_dynamics.get("tiebreak_probability"),
            "tie_break_probability": match_dynamics.get("tiebreak_probability"),
            "ace_status": api_serve_stats.get("aces_status"),
            "df_status": api_serve_stats.get("df_status"),
            "ta_pick_surface_dr": ta_context.get("ta_pick_surface_dr"),
            "ta_opp_surface_dr": ta_context.get("ta_opp_surface_dr"),
            "ta_pick_rpw_pct": ta_context.get("ta_pick_rpw_pct"),
            "ta_opp_rpw_pct": ta_context.get("ta_opp_rpw_pct"),
            "ta_pick_depth": ta_context.get("ta_pick_depth"),
            "ta_opp_depth": ta_context.get("ta_opp_depth"),
            "s_data_depth": None,
            "sets_games_data_depth": None,
            "sets_model_source": "API_PRO_H2H_MATCH_DYNAMICS",
            "pick_aces_line": None,
            "opponent_aces_line": None,
            "total_aces_line": None,
            "pick_aces_projection": api_serve_stats.get("pick_aces_projection"),
            "opponent_aces_projection": api_serve_stats.get("opponent_aces_projection"),
            "total_aces_projection": api_serve_stats.get("total_aces_projection"),
            "pick_df_projection": api_serve_stats.get("pick_df_projection"),
            "opponent_df_projection": api_serve_stats.get("opponent_df_projection"),
            "total_df_projection": api_serve_stats.get("total_df_projection"),
            "aces_status": api_serve_stats.get("aces_status"),
            "ta_scope": ta_context.get("ta_scope"),
            "ta_surface": ta_context.get("ta_surface"),
            "ta_pick_hold_pct": ta_context.get("ta_pick_hold_pct"),
            "ta_opp_hold_pct": ta_context.get("ta_opp_hold_pct"),
            "ta_pick_break_pct": ta_context.get("ta_pick_break_pct"),
            "ta_opp_break_pct": ta_context.get("ta_opp_break_pct"),
            "ta_pick_spw_pct": ta_context.get("ta_pick_spw_pct"),
            "ta_opp_spw_pct": ta_context.get("ta_opp_spw_pct"),
            "ta_pick_tpw_pct": ta_context.get("ta_pick_tpw_pct"),
            "ta_opp_tpw_pct": ta_context.get("ta_opp_tpw_pct"),
            "ta_pick_matches": ta_context.get("ta_pick_matches"),
            "ta_opp_matches": ta_context.get("ta_opp_matches"),
            "ta_winner_decision": ta_context.get("ta_winner_decision"),
            "ta_winner_read": ta_context.get("ta_winner_decision"),
            "ta_sets_decision": ta_context.get("ta_sets_decision"),
            "ta_games_decision": ta_context.get("ta_games_decision"),
            "ta_tb_decision": ta_context.get("ta_tb_decision"),
            "ta_projected_sets": ta_context.get("ta_projected_sets"),
            "ta_projected_games": ta_context.get("ta_projected_games"),
            "ta_straight_sets_probability": ta_context.get("ta_straight_sets_probability"),
            "ta_decider_probability": ta_context.get("ta_decider_probability"),
            "ta_tiebreak_probability": ta_context.get("ta_tiebreak_probability"),
            "ta_score_projection": ta_context.get("ta_score_projection"),
            "ta_sets_model_status": ta_context.get("ta_sets_model_status"),
            "ta_signal": ta_context.get("ta_signal"),
            "ta_signal_label": ta_context.get("ta_signal_label"),
            "ta_signal_action": ta_context.get("ta_signal_action"),
            "ta_signal_market": ta_context.get("ta_signal_market"),
            "ta_signal_type": ta_context.get("ta_signal_type"),
            "ta_signal_strength": ta_context.get("ta_signal_strength"),
            "ta_signal_confidence": ta_context.get("ta_signal_confidence"),
            "ta_signal_reasons": ta_context.get("ta_signal_reasons") or [],
            "ta_signal_score_projection": ta_context.get("ta_signal_score_projection"),
            "ta_serve_return_pattern": ta_context.get("ta_serve_return_pattern"),
            "ta_match_shape": ta_context.get("ta_match_shape"),
            "ta_depth_label": ta_context.get("ta_depth_label"),
            "ta_decision_confidence": ta_context.get("ta_decision_confidence"),
            "ta_decision_notes": ta_context.get("ta_decision_notes") or [],
            "thinq_pick_player_id": pick_player_id,
            "thinq_opponent_player_id": opponent_player_id,
            "thinq_id_orientation": "PICK_IDS_SIDE_AWARE_V1",
            "thinq_flags": sorted(set(flags)),
            "thinq_source_status": {
                "elo": elo.get("status"),
                "h2h": h2h.get("status"),
                "recent_form": recent_form.get("status"),
                "match_dynamics": match_dynamics.get("status"),
                "ta": ta_context.get("ta_status"),
                "history_match_count": (recent_form.get("history_status") or {}).get("match_count") if isinstance(recent_form.get("history_status"), dict) else None,
                "history_file_count": (recent_form.get("history_status") or {}).get("file_count") if isinstance(recent_form.get("history_status"), dict) else None,
            },
        }


def build_match_features(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return ThinqService().build_match_features(*args, **kwargs)
