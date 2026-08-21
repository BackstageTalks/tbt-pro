"""RapidAPI PRO client for CORQ runtime.

This patch keeps the simple robust name matcher, but adds a pragmatic rule for
RapidAPI odds payloads where outcome labels are numeric:
- label "1" means home/player1
- label "2" means away/player2

Therefore those odds are considered confirmed as DIRECT_BY_NUMERIC_OUTCOME.
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote
from zoneinfo import ZoneInfo

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from corq.name_match import name_match_score, normalize_name
except Exception:
    from difflib import SequenceMatcher
    def normalize_name(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())
    def name_match_score(a: Any, b: Any) -> float:
        a_norm = normalize_name(a)
        b_norm = normalize_name(b)
        if not a_norm or not b_norm:
            return 0.0
        if a_norm == b_norm:
            return 1.0
        a_parts = a_norm.split()
        b_parts = b_norm.split()
        if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
            return 0.82
        return SequenceMatcher(None, a_norm, b_norm).ratio()

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
_DAILY_ODDS_BY_DATE_CACHE: Dict[str, List[Dict[str, Any]]] = {}
TENNISAPI_MAX_PAGE_SIZE = 200



class RapidApiError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("events", "data", "items", "categories", "results"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _team_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("name", "fullName", "full_name", "displayName", "display_name", "shortName", "short_name", "slug"):
            if value.get(key):
                return str(value.get(key)).strip()
        return None
    text = str(value).strip()
    return text or None


def parse_category_ids() -> List[int]:
    raw = os.getenv("TENNISAPI_CATEGORY_IDS", "3,6,871")
    ids: List[int] = []
    for part in raw.split(","):
        try:
            ids.append(int(part.strip()))
        except Exception:
            pass
    return ids or [3, 6, 871]


def target_betting_day(now: Optional[datetime] = None) -> datetime:
    """Return the local calendar date used for TennisAPI event fetches.

    Important distinction:
    - When ``now`` is passed explicitly, the caller is iterating a concrete
      fetch date. In that case environment variables must not override it.
    - When ``now`` is omitted, manual backfills may still use CORQ_TARGET_DATE,
      TENNISAPI_TARGET_DATE or RUN_DATE.

    This prevents a 06:00 -> 06:00 betting-day run from fetching the same
    calendar date twice when the window spans two provider calendar dates.
    """
    if now is not None:
        current = now
        if current.tzinfo is None:
            current = current.replace(tzinfo=LOCAL_TZ)
        return current.astimezone(LOCAL_TZ)

    explicit = os.getenv("CORQ_TARGET_DATE") or os.getenv("TENNISAPI_TARGET_DATE") or os.getenv("RUN_DATE")
    if explicit:
        try:
            parsed = datetime.fromisoformat(str(explicit)[:10])
            return parsed.replace(tzinfo=LOCAL_TZ)
        except Exception:
            pass

    current = datetime.now(LOCAL_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=LOCAL_TZ)
    return current.astimezone(LOCAL_TZ)


def unix_to_datetime(timestamp: Any) -> Optional[datetime]:
    if timestamp in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except Exception:
        return None


def unix_to_iso(timestamp: Any) -> Optional[str]:
    dt = unix_to_datetime(timestamp)
    return dt.isoformat() if dt else None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return unix_to_datetime(value)
    if isinstance(value, str):
        try:
            text = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def normalize_surface(value: Any) -> Tuple[str, Optional[str]]:
    raw = str(value or "").strip()
    text = raw.lower()
    if "clay" in text:
        return "Clay", raw or None
    if "grass" in text:
        return "Grass", raw or None
    if "carpet" in text:
        return "Hard", raw or None
    if "hard" in text or "indoor" in text:
        return "Hard", raw or None
    return "Unknown", raw or None


def deep_find_first(obj: Any, keys: Iterable[str]) -> Any:
    wanted = set(keys)
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) in wanted and value not in (None, ""):
                return value
        for value in obj.values():
            found = deep_find_first(value, wanted)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = deep_find_first(item, wanted)
            if found not in (None, ""):
                return found
    return None



# TENNISAPI_CURRENT_RANKING_PATCH_V1
# Ranking lookups are intentionally conservative and configurable. They never
# fabricate missing ranks: callers receive None values and the renderer displays
# the project fallback (X).
_RANKING_LOOKUP_CACHE: Dict[str, Dict[str, Any]] = {}


def _rank_int(value: Any) -> Optional[int]:
    if value in (None, "") or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "n/a", "na", "-", "--", "—", "x", "(x)"}:
        return None
    if text.startswith("#"):
        text = text[1:].strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    try:
        rank = int(float(text))
    except Exception:
        return None
    return rank if rank > 0 else None


def _points_int(value: Any) -> Optional[int]:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        points = int(float(str(value).replace(",", "").strip()))
    except Exception:
        return None
    return points if points >= 0 else None


def _walk_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_dicts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_dicts(item)


def _ranking_candidates(payload: Any) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for item in _walk_dicts(payload):
        rank = None
        for key in ("rank", "ranking", "position", "currentRank", "current_rank", "place"):
            rank = _rank_int(item.get(key))
            if rank is not None:
                break
        if rank is None:
            continue
        points = None
        for key in ("points", "rankingPoints", "ranking_points", "currentPoints", "current_points"):
            points = _points_int(item.get(key))
            if points is not None:
                break
        name = _team_name(item.get("player")) or _team_name(item.get("team")) or _team_name(item.get("participant")) or _team_name(item)
        player_id = item.get("id") or item.get("player_id") or item.get("playerId") or deep_find_first(item, {"playerId", "player_id"})
        tour = item.get("tour") or item.get("category") or item.get("type")
        candidates.append({
            "rank": rank,
            "points": points,
            "name": name,
            "player_id": player_id,
            "tour": tour,
            "raw": item,
        })
    return candidates


def _ranking_tour_tokens(tour: Optional[str]) -> List[str]:
    text = normalize_name(tour or "")
    if "wta" in text or "women" in text or text in {"w"}:
        return ["wta", "women"]
    if "atp" in text or "men" in text or text in {"m"}:
        return ["atp", "men"]
    return ["atp", "wta", "men", "women"]


def _best_ranking_candidate(player_name: str, payload: Any, tour: Optional[str] = None) -> Optional[Dict[str, Any]]:
    candidates = _ranking_candidates(payload)
    if not candidates:
        return None
    player_norm = normalize_name(player_name)
    tour_tokens = _ranking_tour_tokens(tour)
    best_score = -1.0
    best: Optional[Dict[str, Any]] = None
    for item in candidates:
        name_score = name_match_score(player_name, item.get("name")) if item.get("name") else 0.0
        if not item.get("name"):
            # Ranking endpoints searched by player id/name may return one object
            # without a display name. Accept it only if it is the sole candidate.
            name_score = 0.80 if len(candidates) == 1 and player_norm else 0.0
        tour_text = normalize_name(item.get("tour") or "")
        tour_bonus = 0.05 if not tour_text or any(tok in tour_text for tok in tour_tokens) else -0.10
        score = name_score + tour_bonus
        if score > best_score:
            best_score = score
            best = item
    if best is None or best_score < 0.70:
        return None
    return best


def _ranking_cache_key(player_name: str, tour: Optional[str]) -> str:
    return f"{normalize_name(tour or '*')}:{normalize_name(player_name)}"

def event_status_type(event: Dict[str, Any]) -> str:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    return str(status.get("type") or status.get("description") or "unknown").strip().lower()


def event_status_code(event: Dict[str, Any]) -> Optional[int]:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    try:
        return int(status.get("code"))
    except Exception:
        return None


def is_event_notstarted_future(event: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """Loose loader-level gate.

    This function is retained for compatibility, but the main normalizer no
    longer calls it. It rejects only obviously closed/cancelled statuses if
    called elsewhere.
    """
    status_type = event_status_type(event)
    status_code = event_status_code(event)
    closed_types = {"finished", "ended", "inprogress", "in progress", "live", "cancelled", "canceled", "postponed", "interrupted", "retired", "walkover"}
    if status_type in closed_types:
        return False, f"status_type={status_type}"
    if status_code == 100:
        return False, "status_code=100"
    return True, None


@dataclass
class RapidApiClient:
    api_key: Optional[str] = None
    host: Optional[str] = None
    timeout: int = 30
    sleep_seconds: float = 0.24

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("RAPIDAPI_KEY")
        self.host = self.host or os.getenv("TENNISAPI_RAPIDAPI_HOST") or os.getenv("RAPIDAPI_HOST") or "tennisapi1.p.rapidapi.com"
        if requests is None:
            raise RapidApiError("requests package is not installed")
        if not self.api_key:
            raise RapidApiError("RAPIDAPI_KEY is missing")
        try:
            max_rps = float(os.getenv("TENNISAPI_MAX_RPS", "5"))
            if max_rps <= 0:
                max_rps = 5.0
            self.sleep_seconds = max(float(self.sleep_seconds or 0.0), (1.0 / max_rps) + 0.02)
        except Exception:
            self.sleep_seconds = max(float(self.sleep_seconds or 0.0), 0.24)
        self.last_get_status: Optional[int] = None
        self.last_get_note: Optional[str] = None
        self.last_get_path: Optional[str] = None
        self.odds_endpoint_stats: Dict[str, Dict[str, Any]] = {}

    @property
    def headers(self) -> Dict[str, str]:
        return {"x-rapidapi-key": str(self.api_key), "x-rapidapi-host": str(self.host)}

    def _sanitize_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply provider paging rule: pageSize must never exceed 200.

        Mail from TennisApi provider says requests above pageSize=200 are
        automatically cut to 200. Keeping the request explicit avoids silent
        partial data. Pagination must use pageNo=1,2,3... in callers that need
        more than one page.
        """
        clean = dict(params or {})
        for key in ("pageSize", "page_size", "pagesize"):
            if key not in clean:
                continue
            try:
                value = int(float(clean.get(key)))
            except Exception:
                value = TENNISAPI_MAX_PAGE_SIZE
            if value > TENNISAPI_MAX_PAGE_SIZE:
                print(f"RAPIDAPI PAGE SIZE CLAMP key={key} requested={value} capped={TENNISAPI_MAX_PAGE_SIZE}")
                value = TENNISAPI_MAX_PAGE_SIZE
            if value <= 0:
                value = TENNISAPI_MAX_PAGE_SIZE
            clean[key] = value
        return clean

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"https://{self.host}{path}"
        params = self._sanitize_params(params)
        attempts = 2
        self.last_get_path = path
        self.last_get_status = None
        self.last_get_note = None
        for attempt in range(attempts):
            try:
                response = requests.get(url, headers=self.headers, params=params or {}, timeout=self.timeout)
                status = int(response.status_code)
                self.last_get_status = status
                if status == 429:
                    self.last_get_note = "RATE_LIMIT"
                    print(f"RAPIDAPI GET {path} status=429 rate_limited attempt={attempt + 1}")
                    if attempt + 1 < attempts:
                        try:
                            sleep_for = float(os.getenv("TENNISAPI_429_SLEEP_SECONDS", "10"))
                        except Exception:
                            sleep_for = 10.0
                        time.sleep(max(3.0, sleep_for))
                        continue
                    return None
                if status == 204:
                    self.last_get_note = "NO_CONTENT"
                    print(f"RAPIDAPI GET {path} status=204")
                    return None
                if status == 404:
                    self.last_get_note = "NOT_FOUND"
                    print(f"RAPIDAPI GET {path} status=404")
                    return None
                if status >= 400:
                    self.last_get_note = "HTTP_ERROR"
                    response.raise_for_status()
                if not response.text:
                    self.last_get_note = "EMPTY_BODY"
                    print(f"RAPIDAPI GET {path} status={status} empty_body")
                    return None
                self.last_get_note = "OK"
                return response.json()
            except Exception as exc:
                if self.last_get_note is None:
                    self.last_get_note = "EXCEPTION"
                print(f"RAPIDAPI GET ERROR path={path} params={params or {}} error={exc}")
                return None
            finally:
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
        return None


    def paginated_get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        items_keys: Iterable[str] = ("data", "items", "results", "events", "rankings", "players"),
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetch every page for TennisAPI list endpoints using provider-safe paging.

        Provider guidance: pageSize is capped at 200. Larger values are silently
        reduced by the API, so callers that need full coverage must request
        pageSize=200 and iterate pageNo=1,2,3... until the payload reports no
        more pages or returns an empty page.

        This method never invents missing pages or rows. If the first page is
        empty or an error occurs, the returned status makes that explicit.
        """
        base_params: Dict[str, Any] = dict(params or {})
        base_params["pageSize"] = TENNISAPI_MAX_PAGE_SIZE
        base_params.pop("page_size", None)
        base_params.pop("pagesize", None)

        def extract_items(payload: Any) -> List[Any]:
            if isinstance(payload, list):
                return list(payload)
            if isinstance(payload, dict):
                for key in items_keys:
                    value = payload.get(key)
                    if isinstance(value, list):
                        return list(value)
                nested = payload.get("result") or payload.get("response")
                if isinstance(nested, dict):
                    for key in items_keys:
                        value = nested.get(key)
                        if isinstance(value, list):
                            return list(value)
            return []

        def has_next(payload: Any, items: List[Any]) -> bool:
            if not isinstance(payload, dict):
                return False
            for key in ("hasNextPage", "has_next_page", "hasMore", "has_more", "nextPage", "next_page"):
                value = payload.get(key)
                if isinstance(value, bool):
                    return value
                if value not in (None, "", 0, "0", False):
                    return True
            meta = payload.get("meta") or payload.get("pagination") or payload.get("page")
            if isinstance(meta, dict):
                for key in ("hasNextPage", "has_next_page", "hasMore", "has_more", "nextPage", "next_page"):
                    value = meta.get(key)
                    if isinstance(value, bool):
                        return value
                    if value not in (None, "", 0, "0", False):
                        return True
                total_pages = meta.get("totalPages") or meta.get("total_pages")
                current_page = meta.get("pageNo") or meta.get("page") or meta.get("currentPage")
                try:
                    return int(current_page) < int(total_pages)
                except Exception:
                    pass
            # If exactly 200 rows were returned and no explicit flag is present,
            # one more page is safe. An empty next page will stop the loop.
            return len(items) >= TENNISAPI_MAX_PAGE_SIZE

        all_items: List[Any] = []
        pages: List[Dict[str, Any]] = []
        page_no = 1
        status = "OK"
        while True:
            if max_pages is not None and page_no > max_pages:
                status = "MAX_PAGES_REACHED"
                break
            page_params = dict(base_params)
            page_params["pageNo"] = page_no
            payload = self.get(path, params=page_params)
            note = self.last_get_note or "OK"
            if payload is None:
                status = note if page_no == 1 else "STOPPED_ON_EMPTY_OR_ERROR_PAGE"
                pages.append({"pageNo": page_no, "status": note, "item_count": 0})
                break
            items = extract_items(payload)
            all_items.extend(items)
            pages.append({"pageNo": page_no, "status": note, "item_count": len(items)})
            if not items:
                status = "EMPTY_FIRST_PAGE" if page_no == 1 else "OK"
                break
            if not has_next(payload, items):
                break
            page_no += 1

        return {
            "status": status,
            "items": all_items,
            "pageSize": TENNISAPI_MAX_PAGE_SIZE,
            "page_count": len(pages),
            "item_count": len(all_items),
            "pages": pages,
            "source_path": path,
        }


    def get_on_host(self, host: str, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET helper for provider modules that live on a different RapidAPI host.

        Keeps the same API key, timeout, retry behavior and provider pageSize rule.
        This is used for the MatchStat/Tennis-API H2H stats service while the
        main event/odds runtime continues to use TENNISAPI_RAPIDAPI_HOST.
        """
        old_host = self.host
        try:
            self.host = host
            return self.get(path, params=params)
        finally:
            self.host = old_host

    def _h2h_host(self) -> str:
        return os.getenv("TENNISAPI_H2H_RAPIDAPI_HOST") or "tennis-api-atp-wta-itf.p.rapidapi.com"

    def _normalize_h2h_stats_payload(
        self,
        payload: Any,
        *,
        source_path: str,
        source_host: str,
        player1_name: Optional[str] = None,
        player2_name: Optional[str] = None,
        surface: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize provider H2H stats without inventing unavailable metrics.

        The provider can return either:
        - {data: {player1Stats, player2Stats, matchesCount}}
        - {player1, player2, matchesCount}

        Aces and double faults are totals. They are exposed as totals and per
        match only when matches/statMatchesPlayed is available. They are not
        mapped to percentages because no serve-game or serve-point denominator is
        provided by these H2H stats endpoints.
        """
        def as_dict(value: Any) -> Dict[str, Any]:
            return value if isinstance(value, dict) else {}

        def first(obj: Dict[str, Any], *keys: str) -> Any:
            for key in keys:
                if key in obj and obj.get(key) not in (None, ""):
                    return obj.get(key)
            return None

        def num(value: Any) -> Optional[float]:
            if value in (None, "", "N/A", "n/a", "-", "—"):
                return None
            try:
                return float(str(value).replace(",", "."))
            except Exception:
                return None

        root = as_dict(payload)
        data = as_dict(root.get("data")) if isinstance(root.get("data"), dict) else root
        p1 = as_dict(data.get("player1Stats")) or as_dict(data.get("player1"))
        p2 = as_dict(data.get("player2Stats")) or as_dict(data.get("player2"))
        matches_count = num(first(data, "matchesCount", "matchCount", "matches"))

        def stat_matches(stats: Dict[str, Any]) -> Optional[float]:
            return num(first(stats, "statMatchesPlayed", "matchesPlayed", "matchesCount", "matches")) or matches_count

        def player_stats(stats: Dict[str, Any], label: str) -> Dict[str, Any]:
            played = stat_matches(stats)
            aces = num(first(stats, "aces", "acesCount"))
            dfs = num(first(stats, "doubleFaults", "doubleFaultsCount"))
            out: Dict[str, Any] = {
                f"{label}_name": first(stats, "name") or (player1_name if label == "player1" else player2_name),
                f"{label}_stat_matches_played": int(played) if played is not None and float(played).is_integer() else played,
                f"{label}_aces_total": int(aces) if aces is not None and float(aces).is_integer() else aces,
                f"{label}_double_faults_total": int(dfs) if dfs is not None and float(dfs).is_integer() else dfs,
                f"{label}_first_serve_pct": num(first(stats, "firstServePercentage")),
                f"{label}_winning_first_serve_pct": num(first(stats, "winningOnFirstServePercentage")),
                f"{label}_winning_second_serve_pct": num(first(stats, "winningOnSecondServePercentage")),
                f"{label}_return_pts_win_pct": num(first(stats, "returnPtsWinPercentage")),
                f"{label}_breakpoints_won_pct": num(first(stats, "breakpointsWonPercentage")),
                f"{label}_tiebreak_won": num(first(stats, "tiebreakWon")),
                f"{label}_tiebreak_count": num(first(stats, "tiebreakCount")),
                f"{label}_sets_won": num(first(stats, "setsWon")),
                f"{label}_games_won": num(first(stats, "gamesWon")),
                f"{label}_matches_won": num(first(stats, "matchesWon")),
            }
            if played and played > 0:
                if aces is not None:
                    out[f"{label}_aces_per_match"] = round(aces / played, 3)
                if dfs is not None:
                    out[f"{label}_double_faults_per_match"] = round(dfs / played, 3)
            return out

        normalized: Dict[str, Any] = {
            "api_serve_stats_source": "TENNISAPI_H2H_STATS",
            "api_serve_stats_status": "OK" if p1 or p2 else "NO_PLAYER_STATS",
            "api_h2h_source_host": source_host,
            "api_h2h_source_path": source_path,
            "api_h2h_surface": surface,
            "api_h2h_matches_count": int(matches_count) if matches_count is not None and float(matches_count).is_integer() else matches_count,
            "raw": payload,
        }
        normalized.update(player_stats(p1, "player1"))
        normalized.update(player_stats(p2, "player2"))
        return normalized

    def get_h2h_stats_by_ids(
        self,
        tour_type: str,
        player1_id: Any,
        player2_id: Any,
        surface: Optional[str] = None,
        player1_name: Optional[str] = None,
        player2_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not _env_bool("TENNISAPI_H2H_STATS_ENABLED", False):
            return {
                "api_serve_stats_status": "H2H_STATS_DISABLED",
                "api_serve_stats_source": "TENNISAPI_H2H_STATS",
                "api_h2h_resolution": "DISABLED",
                "api_h2h_disabled_reason": "TENNISAPI_H2H_STATS_ENABLED is not enabled",
            }
        tour = str(tour_type or "").strip().lower()
        if tour not in {"atp", "wta"}:
            return {"api_serve_stats_status": "MISSING_TOUR_TYPE", "api_serve_stats_source": "TENNISAPI_H2H_STATS"}
        if player1_id in (None, "") or player2_id in (None, ""):
            return {"api_serve_stats_status": "MISSING_PLAYER_IDS", "api_serve_stats_source": "TENNISAPI_H2H_STATS"}
        host = self._h2h_host()
        path = f"/tennis/v2/extend/api/{tour}/h2h/stats/{quote(str(player1_id), safe='')}/{quote(str(player2_id), safe='')}"
        params: Dict[str, Any] = {}
        if surface:
            params["surface"] = str(surface).lower().replace("hardcourt", "hard")
        payload = self.get_on_host(host, path, params=params or None)
        primary_status = self.last_get_note or "NO_DATA"
        if not payload:
            if str(player1_name or "").strip() and str(player2_name or "").strip():
                if not _env_bool("TENNISAPI_H2H_NAME_FALLBACK_ENABLED", False):
                    return {
                        "api_serve_stats_status": f"PRIMARY_{primary_status}_NAME_FALLBACK_DISABLED",
                        "api_serve_stats_source": "TENNISAPI_H2H_STATS",
                        "api_h2h_source_host": host,
                        "api_h2h_source_path": path,
                        "api_h2h_surface": surface,
                        "api_h2h_primary_status": primary_status,
                        "api_h2h_primary_path": path,
                        "api_h2h_fallback_status": "DISABLED",
                        "api_h2h_resolution": "ID_ENDPOINT_ONLY",
                    }
                fallback = self.get_h2h_stats_by_names(tour, str(player1_name), str(player2_name), surface=surface)
                fallback_status = str(fallback.get("api_serve_stats_status") or "NO_DATA")
                fallback["api_h2h_primary_status"] = primary_status
                fallback["api_h2h_primary_path"] = path
                fallback["api_h2h_fallback_status"] = fallback_status
                if fallback_status == "OK":
                    fallback["api_h2h_resolution"] = "NAME_ENDPOINT"
                    return fallback
                fallback["api_serve_stats_status"] = "NOT_FOUND_BOTH_ENDPOINTS" if primary_status == "NOT_FOUND" and fallback_status == "NOT_FOUND" else f"PRIMARY_{primary_status}_FALLBACK_{fallback_status}"
                fallback["api_h2h_resolution"] = "NOT_FOUND"
                return fallback
            return {
                "api_serve_stats_status": primary_status,
                "api_serve_stats_source": "TENNISAPI_H2H_STATS",
                "api_h2h_source_host": host,
                "api_h2h_source_path": path,
                "api_h2h_surface": surface,
                "api_h2h_primary_status": primary_status,
                "api_h2h_primary_path": path,
                "api_h2h_resolution": "NOT_FOUND",
            }
        result = self._normalize_h2h_stats_payload(payload, source_path=path, source_host=host, surface=surface)
        result["api_h2h_primary_status"] = "OK"
        result["api_h2h_primary_path"] = path
        result["api_h2h_fallback_status"] = "NOT_TRIED"
        result["api_h2h_resolution"] = "ID_ENDPOINT"
        return result

    def get_h2h_stats_by_names(
        self,
        tour_type: str,
        player1_name: str,
        player2_name: str,
        surface: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not _env_bool("TENNISAPI_H2H_NAME_FALLBACK_ENABLED", False):
            return {
                "api_serve_stats_status": "H2H_NAME_FALLBACK_DISABLED",
                "api_serve_stats_source": "TENNISAPI_H2H_STATS",
                "api_h2h_resolution": "DISABLED",
                "api_h2h_disabled_reason": "TENNISAPI_H2H_NAME_FALLBACK_ENABLED is not enabled",
            }
        tour = str(tour_type or "").strip().lower()
        if tour not in {"atp", "wta"}:
            return {"api_serve_stats_status": "MISSING_TOUR_TYPE", "api_serve_stats_source": "TENNISAPI_H2H_STATS"}
        if not str(player1_name or "").strip() or not str(player2_name or "").strip():
            return {"api_serve_stats_status": "MISSING_PLAYER_NAMES", "api_serve_stats_source": "TENNISAPI_H2H_STATS"}
        host = self._h2h_host()
        path = (
            f"/tennis/v2/ms-api/h2h/stats/{tour}/"
            f"{quote(str(player1_name).strip(), safe='')}/{quote(str(player2_name).strip(), safe='')}"
        )
        params: Dict[str, Any] = {}
        if surface:
            params["surface"] = str(surface).lower().replace("hardcourt", "hard")
        payload = self.get_on_host(host, path, params=params or None)
        if not payload:
            status = self.last_get_note or "NO_DATA"
            return {
                "api_serve_stats_status": status,
                "api_serve_stats_source": "TENNISAPI_H2H_STATS",
                "api_h2h_source_host": host,
                "api_h2h_source_path": path,
                "api_h2h_surface": surface,
                "api_h2h_fallback_status": status,
                "api_h2h_resolution": "NOT_FOUND",
            }
        result = self._normalize_h2h_stats_payload(
            payload,
            source_path=path,
            source_host=host,
            player1_name=player1_name,
            player2_name=player2_name,
            surface=surface,
        )
        result["api_h2h_fallback_status"] = "OK"
        result["api_h2h_resolution"] = "NAME_ENDPOINT"
        return result

    def get_player_ranking(self, player_name: str, tour: Optional[str] = None, identity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch current TennisApi ranking for one player.

        Returns a dict with rank/points/status/source. Missing or untrusted data
        is returned as None, never estimated. This makes render fallback (X)
        deterministic and avoids fake 0/None values in UI.
        """
        name = str(player_name or "").strip()
        if not name:
            return {"rank": None, "points": None, "status": "MISSING_NAME", "source": "TennisApi"}
        cache_key = _ranking_cache_key(name, tour)
        cached = _RANKING_LOOKUP_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        query = re.sub(r"\s+", "%20", name.strip())
        ids = self._candidate_player_ids(name, identity)
        tours = _ranking_tour_tokens(tour)
        attempts: List[str] = []

        for template in self._ranking_endpoint_templates():
            if "{player_id}" in template and not ids:
                continue
            id_values = ids if "{player_id}" in template else [""]
            tour_values = tours if "{tour}" in template else [tour or ""]
            for player_id in id_values:
                for tour_value in tour_values:
                    path = template.format(player_id=player_id, query=query, tour=str(tour_value or "").lower())
                    if re.search(r"/rankings/[^/]+$", path):
                        page_payload = self.paginated_get(path, items_keys=("data", "items", "results", "rankings", "players"))
                        payload = page_payload.get("items")
                        status = page_payload.get("status")
                        note = f"pages={page_payload.get('page_count')} items={page_payload.get('item_count')}"
                    else:
                        payload = self.get(path)
                        status = getattr(self, "last_get_status", None)
                        note = getattr(self, "last_get_note", None)
                    attempts.append(f"{path}:{status or note or 'UNKNOWN'}")
                    if not payload:
                        continue
                    best = _best_ranking_candidate(name, payload, tour=tour)
                    if not best:
                        continue
                    result = {
                        "rank": _rank_int(best.get("rank")),
                        "points": _points_int(best.get("points")),
                        "status": "OK",
                        "source": "TennisApi",
                        "player_id": best.get("player_id"),
                        "matched_name": best.get("name"),
                        "attempts": attempts,
                    }
                    _RANKING_LOOKUP_CACHE[cache_key] = dict(result)
                    return result

        result = {"rank": None, "points": None, "status": "NOT_FOUND", "source": "TennisApi", "attempts": attempts}
        _RANKING_LOOKUP_CACHE[cache_key] = dict(result)
        return result

    def attach_rankings_to_match(self, match: Dict[str, Any], tour: Optional[str] = None) -> Dict[str, Any]:
        """Attach TennisApi rank, points and rank gap to a normalized match row."""
        row = dict(match)
        p1 = row.get("player1") or row.get("home")
        p2 = row.get("player2") or row.get("away")
        r1 = self.get_player_ranking(str(p1 or ""), tour=tour or row.get("gender") or row.get("category"))
        r2 = self.get_player_ranking(str(p2 or ""), tour=tour or row.get("gender") or row.get("category"))
        rank1 = _rank_int(r1.get("rank"))
        rank2 = _rank_int(r2.get("rank"))
        gap = abs(rank1 - rank2) if rank1 is not None and rank2 is not None else None
        row.update({
            "player1_api_rank": rank1,
            "player2_api_rank": rank2,
            "player1_api_rank_points": _points_int(r1.get("points")),
            "player2_api_rank_points": _points_int(r2.get("points")),
            "api_rank_gap": gap,
            "api_ranking_source": "TennisApi",
            "api_ranking_status": "OK" if rank1 is not None and rank2 is not None else "PARTIAL_OR_MISSING",
            "api_ranking_attempts": {"player1": r1.get("attempts", []), "player2": r2.get("attempts", [])},
        })
        return row

    def _record_odds_endpoint_stat(self, endpoint_name: str, status: Optional[int], note: Optional[str], useful: bool = False) -> None:
        stats = self.odds_endpoint_stats.setdefault(endpoint_name, {
            "requests": 0,
            "status_counts": {},
            "useful_count": 0,
            "winner_market_count": 0,
        })
        stats["requests"] = int(stats.get("requests") or 0) + 1
        key = str(status if status is not None else note or "UNKNOWN")
        counts = stats.setdefault("status_counts", {})
        counts[key] = int(counts.get(key) or 0) + 1
        if useful:
            stats["useful_count"] = int(stats.get("useful_count") or 0) + 1
            stats["winner_market_count"] = int(stats.get("winner_market_count") or 0) + 1

    def discover_categories(self, target_date: datetime) -> List[int]:
        day, month, year = target_date.day, target_date.month, target_date.year
        for path in (f"/api/tennis/calendar/{day}/{month}/{year}/categories", f"/api/tennis/categories/{day}/{month}/{year}"):
            payload = self.get(path)
            found: List[int] = []
            for item in _as_list(payload):
                if not isinstance(item, dict):
                    continue
                value = item.get("id") or item.get("categoryId") or item.get("category_id")
                try:
                    found.append(int(value))
                except Exception:
                    pass
            if found:
                return sorted(set(found))
        return parse_category_ids()

    def get_events_for_category(self, category_id: int, target_date: datetime) -> List[Dict[str, Any]]:
        day, month, year = target_date.day, target_date.month, target_date.year
        paths = (
            f"/api/tennis/category/{category_id}/events/{day}/{month}/{year}",
            f"/api/tennis/categories/{category_id}/events/{day}/{month}/{year}",
        )
        for path in paths:
            payload = self.get(path)
            events = [item for item in _as_list(payload) if isinstance(item, dict)]
            if events:
                return events
        return []

    def get_events_for_date(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        day = target_betting_day(target_date)
        categories = self.discover_categories(day)
        events: List[Dict[str, Any]] = []
        print(f"RAPIDAPI EVENTS DATE: {day.strftime('%Y-%m-%d')} categories={categories}")
        for category_id in categories:
            category_events = self.get_events_for_category(category_id, day)
            print(f"RAPIDAPI CATEGORY {category_id} EVENTS: {len(category_events)}")
            events.extend(category_events)
        deduped = dedupe_events(events)
        print(f"RAPIDAPI RAW EVENTS: {len(events)} DEDUPED: {len(deduped)}")
        return deduped

    def _provider_ids_for_odds(self) -> List[int]:
        """Provider ids for TennisApi PRO odds endpoints.

        Default is intentionally provider 1 only. Manual RapidAPI tests showed
        providers 2-5 can return 204 empty for the same event, so sweeping them
        by default wastes requests. If another provider is later confirmed useful,
        set TENNISAPI_PROVIDER_IDS, for example: 1,3.
        """
        raw = os.getenv("TENNISAPI_PROVIDER_IDS") or os.getenv("TENNISAPI_PROVIDER_ID") or "1"
        ids: List[int] = []
        for part in str(raw).split(","):
            try:
                value = int(part.strip())
                if value > 0 and value not in ids:
                    ids.append(value)
            except Exception:
                pass
        return ids or [1]

    def _match_odds_date(self, match: Optional[Dict[str, Any]]) -> datetime:
        if isinstance(match, dict):
            for key in ("match_start", "start_time", "start_time_utc", "match_time_utc"):
                parsed = parse_datetime(match.get(key))
                if parsed:
                    return parsed.astimezone(LOCAL_TZ)
            ts = match.get("startTimestamp") or match.get("start_timestamp")
            parsed = unix_to_datetime(ts)
            if parsed:
                return parsed.astimezone(LOCAL_TZ)
        return target_betting_day()

    def _daily_odds_items_for_date(self, target_date: datetime, attempts: List[str]) -> List[Dict[str, Any]]:
        local_date = target_date.astimezone(LOCAL_TZ) if target_date.tzinfo else target_date.replace(tzinfo=LOCAL_TZ)
        date_key = local_date.strftime("%Y-%m-%d")
        if date_key in _DAILY_ODDS_BY_DATE_CACHE:
            attempts.append(f"events_odds_by_date:CACHE:{len(_DAILY_ODDS_BY_DATE_CACHE[date_key])}")
            return _DAILY_ODDS_BY_DATE_CACHE[date_key]
        day, month, year = local_date.day, local_date.month, local_date.year
        path = f"/api/tennis/events/odds/{day}/{month}/{year}"
        payload = self.get(path)
        if not payload:
            attempts.append("events_odds_by_date:NO_PAYLOAD")
            _DAILY_ODDS_BY_DATE_CACHE[date_key] = []
            return []
        items = [item for item in _as_list(payload) if isinstance(item, dict)]
        # If the payload itself is an event-like odds object, keep it too.
        if isinstance(payload, dict) and not items:
            items = [payload]
        _DAILY_ODDS_BY_DATE_CACHE[date_key] = items
        attempts.append(f"events_odds_by_date:OK:{len(items)}")
        return items

    def _find_daily_odds_for_match(self, items: List[Dict[str, Any]], match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_id = str(match.get("event_id") or match.get("match_id") or match.get("id") or "")
        player1 = match.get("player1")
        player2 = match.get("player2")
        best_score = 0.0
        best_item: Optional[Dict[str, Any]] = None
        for item in items:
            item_id = str(item.get("event_id") or item.get("match_id") or item.get("id") or "")
            score = 0.0
            if event_id and item_id and event_id == item_id:
                score = 2.0
            item_p1, item_p2 = event_players(item)
            if player1 and player2 and item_p1 and item_p2:
                direct = name_match_score(player1, item_p1) + name_match_score(player2, item_p2)
                reverse = name_match_score(player1, item_p2) + name_match_score(player2, item_p1)
                score = max(score, direct, reverse)
            if score >= 1.4 and score > best_score:
                normalized = normalize_winner_odds_payload(item)
                if normalized:
                    best_score = score
                    best_item = normalized
        return best_item

    def get_event_odds(self, event_id: Any, match: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch and normalize match-winner odds for one event.

        Production Daily runtime uses TennisApi exact-event odds only.
        Endpoint order mirrors MarQ V2 cleanup:
        1. /api/tennis/event/{event_id}/odds/{provider}/all
           Preferred because it can include initialFractionalValue for open/move.
        2. /api/tennis/event/{event_id}/provider/{provider}/winning-odds
           Current-only fallback.

        The observed betting-odds path returns 404 in production logs, so it is
        disabled by default and can be enabled only with
        TENNISAPI_ENABLE_BETTING_ODDS_ENDPOINT=true. No Bet365, no Tennis Live,
        no date/name fuzzy matching and no date-batch odds fallback are used.
        """
        self.last_odds_attempts = []
        self.last_odds_status = "MISSING"
        self.last_odds_endpoint = None
        self.last_odds_request_count = 0

        if event_id in (None, ""):
            self.last_odds_attempts.append("missing_event_id:SKIPPED")
            return None

        event_id_text = str(event_id)

        for provider in self._provider_ids_for_odds():
            endpoint_candidates = [
                (f"provider_all_odds[{provider}]", f"/api/tennis/event/{event_id_text}/odds/{provider}/all"),
                (f"provider_winning_odds[{provider}]", f"/api/tennis/event/{event_id_text}/provider/{provider}/winning-odds"),
            ]
            if str(os.getenv("TENNISAPI_ENABLE_BETTING_ODDS_ENDPOINT", "")).strip().lower() in {"1", "true", "yes", "on"}:
                endpoint_candidates.append((f"provider_betting_odds[{provider}]", f"/api/tennis/event/{event_id_text}/provider/{provider}/betting-odds"))
            for name, path in endpoint_candidates:
                self.last_odds_request_count += 1
                payload = self.get(path)
                status = getattr(self, "last_get_status", None)
                note = getattr(self, "last_get_note", None)

                if not payload:
                    self._record_odds_endpoint_stat(name, status, note, useful=False)
                    self.last_odds_attempts.append(f"{name}:NO_PAYLOAD:{status or note or 'UNKNOWN'}")
                    continue

                normalized = normalize_winner_odds_payload(payload)
                if not normalized:
                    self._record_odds_endpoint_stat(name, status, note or "NO_WINNER_MARKET", useful=False)
                    self.last_odds_attempts.append(f"{name}:NO_WINNER_MARKET:{status or note or 'UNKNOWN'}")
                    continue

                self._record_odds_endpoint_stat(name, status, note or "OK", useful=True)
                normalized["odds_endpoint"] = path
                normalized["odds_endpoint_name"] = name
                normalized["odds_source"] = normalized.get("odds_source") or f"RapidAPI PRO {name}"
                normalized["odds_status"] = "OK"
                normalized["odds_attempts"] = list(self.last_odds_attempts) + [f"{name}:OK"]
                normalized["odds_request_count"] = self.last_odds_request_count
                normalized["odds_removed_fallbacks"] = [
                    "Bet365PrematchAPI",
                    "TennisLiveAPI",
                    "/api/tennis/events/odds/{day}/{month}/{year}",
                    "date/name fuzzy matching",
                    "non-exact event discovery for odds",
                ]
                self.last_odds_attempts = normalized["odds_attempts"]
                self.last_odds_status = "OK"
                self.last_odds_endpoint = path
                return normalized

        self.last_odds_status = "NO_ODDS_ALL_ONLY"
        return None


def dedupe_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for event in events:
        event_id = event.get("id") or event.get("event_id") or event.get("match_id")
        home, away = event_players(event)
        key = event_id or f"{normalize_name(home)}::{normalize_name(away)}::{event.get('startTimestamp') or event.get('start_time')}"
        if key in seen:
            continue
        seen.add(key)
        output.append(event)
    return output


def _side_token(value: Any) -> str:
    return normalize_name(value or "")


def _participant_name(item: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return _team_name(item)
    for key in (
        "team",
        "player",
        "participant",
        "competitor",
        "athlete",
        "person",
        "entity",
    ):
        name = _team_name(item.get(key))
        if name:
            return name
    return _team_name(item)


def _participant_side(item: Dict[str, Any]) -> str:
    values: List[Any] = []
    for key in ("side", "homeAway", "home_away", "position", "type", "role", "qualifier", "designation"):
        values.append(item.get(key))
    for key in ("isHome", "home", "is_home"):
        if item.get(key) is True:
            return "home"
    for key in ("isAway", "away", "is_away"):
        if item.get(key) is True:
            return "away"
    text = _side_token(" ".join(str(v or "") for v in values))
    if text in {"home", "player 1", "player1", "competitor 1", "competitor1", "p1", "1"}:
        return "home"
    if text in {"away", "player 2", "player2", "competitor 2", "competitor2", "p2", "2"}:
        return "away"
    return ""


def _participants_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key in (
        "participants",
        "competitors",
        "contestants",
        "teams",
        "players",
        "opponents",
        "sides",
    ):
        value = event.get(key)
        if isinstance(value, list):
            out.extend(item for item in value if isinstance(item, dict))
    for parent_key in ("event", "match", "fixture", "game"):
        parent = event.get(parent_key)
        if isinstance(parent, dict):
            for key in ("participants", "competitors", "teams", "players", "opponents"):
                value = parent.get(key)
                if isinstance(value, list):
                    out.extend(item for item in value if isinstance(item, dict))
    return out


def _entity_id(value: Any) -> Optional[int]:
    if not isinstance(value, dict):
        return None
    for key in ("id", "teamId", "team_id", "playerId", "player_id"):
        raw = value.get(key)
        try:
            if raw not in (None, ""):
                return int(raw)
        except Exception:
            continue
    player_info = value.get("playerTeamInfo")
    if isinstance(player_info, dict):
        try:
            raw = player_info.get("id")
            return int(raw) if raw not in (None, "") else None
        except Exception:
            return None
    return None


def event_player_ids(event: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    home = (
        event.get("homeTeam")
        or event.get("home_team")
        or event.get("home")
        or event.get("player1")
        or event.get("participant1")
        or event.get("competitor1")
        or event.get("team1")
    )
    away = (
        event.get("awayTeam")
        or event.get("away_team")
        or event.get("away")
        or event.get("player2")
        or event.get("participant2")
        or event.get("competitor2")
        or event.get("team2")
    )
    home_id = _entity_id(home)
    away_id = _entity_id(away)
    if home_id is not None and away_id is not None:
        return home_id, away_id

    participants = _participants_from_event(event)
    side_home_id: Optional[int] = None
    side_away_id: Optional[int] = None
    ordered_ids: List[int] = []
    for item in participants:
        entity_id = _entity_id(item)
        if entity_id is None:
            continue
        side = _participant_side(item)
        if side == "home" and side_home_id is None:
            side_home_id = entity_id
        elif side == "away" and side_away_id is None:
            side_away_id = entity_id
        if entity_id not in ordered_ids:
            ordered_ids.append(entity_id)
    home_id = home_id or side_home_id
    away_id = away_id or side_away_id
    if home_id is not None and away_id is not None:
        return home_id, away_id
    if len(ordered_ids) >= 2:
        return ordered_ids[0], ordered_ids[1]
    return home_id, away_id


def event_players(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    home = (
        event.get("homeTeam")
        or event.get("home_team")
        or event.get("home")
        or event.get("player1")
        or event.get("participant1")
        or event.get("competitor1")
        or event.get("team1")
    )
    away = (
        event.get("awayTeam")
        or event.get("away_team")
        or event.get("away")
        or event.get("player2")
        or event.get("participant2")
        or event.get("competitor2")
        or event.get("team2")
    )

    home_name = _team_name(home)
    away_name = _team_name(away)
    if home_name and away_name:
        return home_name, away_name

    participants = _participants_from_event(event)
    side_home: Optional[str] = None
    side_away: Optional[str] = None
    ordered: List[str] = []
    for item in participants:
        name = _participant_name(item)
        if not name:
            continue
        side = _participant_side(item)
        if side == "home" and side_home is None:
            side_home = name
        elif side == "away" and side_away is None:
            side_away = name
        if name not in ordered:
            ordered.append(name)

    home_name = home_name or side_home
    away_name = away_name or side_away
    if home_name and away_name:
        return home_name, away_name
    if len(ordered) >= 2:
        return ordered[0], ordered[1]

    return home_name, away_name


def is_doubles_name(name: Any) -> bool:
    text = str(name or "")
    return "/" in text or " & " in text or " + " in text


def _category_name(event: Dict[str, Any]) -> Optional[str]:
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    category = tournament.get("category") if isinstance(tournament.get("category"), dict) else {}
    if category.get("name"):
        return str(category.get("name"))
    unique = tournament.get("uniqueTournament") if isinstance(tournament.get("uniqueTournament"), dict) else {}
    unique_category = unique.get("category") if isinstance(unique.get("category"), dict) else {}
    if unique_category.get("name"):
        return str(unique_category.get("name"))
    return None


def normalize_event_for_corq(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # IMPORTANT: do not apply strict status/time filtering in the loader.
    # The loader should keep events visible for ALL audit. Status/time eligibility
    # is handled later in corq.rules, where rejected events get explicit flags.
    player1, player2 = event_players(event)
    if not player1 or not player2:
        return None
    player1_id, player2_id = event_player_ids(event)
    event_id = event.get("id") or event.get("event_id") or event.get("match_id")
    start_ts = event.get("startTimestamp") or event.get("start_timestamp") or deep_find_first(event, {"startTimestamp", "start_time"})
    raw_surface = event.get("surfaceType") or event.get("surface") or event.get("groundType") or deep_find_first(event, {"surfaceType", "surface", "courtSurface", "groundType"})
    surface, surface_raw = normalize_surface(raw_surface)
    tournament_obj = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    unique = tournament_obj.get("uniqueTournament") if isinstance(tournament_obj.get("uniqueTournament"), dict) else {}
    tournament = _team_name(tournament_obj) or _team_name(unique)
    category_name = _category_name(event)
    event_filters = event.get("eventFilters") if isinstance(event.get("eventFilters"), dict) else {}
    gender_values = event_filters.get("gender")
    gender = gender_values[0] if isinstance(gender_values, list) and gender_values else category_name
    start_iso = unix_to_iso(start_ts) or event.get("start_time") or event.get("match_start")
    return {
        "match_id": event_id,
        "event_id": event_id,
        "id": event_id,
        "player1": player1,
        "player2": player2,
        "player1_id": player1_id,
        "player2_id": player2_id,
        "home_team_id": player1_id,
        "away_team_id": player2_id,
        "surface": surface,
        "surface_raw": surface_raw,
        "tournament": tournament,
        "category": category_name,
        "level": category_name,
        "gender": gender,
        "best_of": 5 if "grand slam" in normalize_name(tournament) else 3,
        "match_start": start_iso,
        "start_time": start_iso,
        "status_type": event_status_type(event),
        "status_code": event_status_code(event),
        "is_doubles": is_doubles_name(player1) or is_doubles_name(player2),
        "source": "RapidAPI PRO",
        "raw": event,
    }


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def fractional_to_decimal(value: Any) -> Optional[float]:
    if not isinstance(value, str) or "/" not in value:
        return _to_float(value)
    try:
        left, right = value.split("/", 1)
        return round((float(left) / float(right)) + 1.0, 4)
    except Exception:
        return None


def extract_markets(payload: Any) -> List[Dict[str, Any]]:
    """Extract market-like objects from TennisApi odds payloads.

    TennisApi returns several different shapes:
    - {home: {...}, away: {...}}                               handled earlier
    - {markets: [{marketName: "Full time", choices: [...]}]}
    - {featured: {default: {marketName: "Full time", choices: [...]}}}
    - {odds: {"16515714": {marketName: "Full time", choices: [...]}}}

    The last form is important for getTennisEventsWithOddsByDate, where the
    odds object is a dict keyed by event/source id rather than a list.
    """
    markets: List[Dict[str, Any]] = []

    if isinstance(payload, list):
        for item in payload:
            markets.extend(extract_markets(item))
        return markets

    if not isinstance(payload, dict):
        return []

    if any(k in payload for k in ("choices", "outcomes", "participants", "selections")):
        markets.append(payload)

    # Common wrappers. For dict values, recurse because daily odds and featured
    # odds often store market objects under arbitrary keys such as event ids or
    # "default"/"asian".
    for key in ("markets", "odds", "eventOdds", "winningOdds", "featured", "default", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                markets.extend(extract_markets(item))
        elif isinstance(value, dict):
            markets.extend(extract_markets(value))

    # Daily odds by date can be {odds: {event_id: market_payload}}. After the
    # recursive call sees the odds dict, it has arbitrary numeric keys, so scan
    # all dict values as potential market payloads. This is intentionally broad
    # but still safe because normalize_winner_odds_payload later accepts only
    # match-winner Home/Away markets.
    if not any(k in payload for k in ("markets", "eventOdds", "winningOdds", "featured", "default", "data", "items", "results")):
        for value in payload.values():
            if isinstance(value, (dict, list)):
                markets.extend(extract_markets(value))

    return markets


def market_choices(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("choices", "outcomes", "participants", "selections", "selection", "competitors"):
        value = market.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def choice_name(choice: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("name", "label", "choiceName", "participantName", "sourceName", "marketName"):
        if choice.get(key):
            parts.append(str(choice.get(key)))
    return " ".join(parts).strip()


def choice_price(choice: Dict[str, Any]) -> Optional[float]:
    for key in ("decimalValue", "decimal", "decimalOdds", "price", "odds", "value", "fractionalValue"):
        converted = fractional_to_decimal(choice.get(key))
        if converted is not None:
            return converted
    return None


def is_match_winner_market(market: Dict[str, Any]) -> bool:
    """Return True only for match winner / full-time Home-Away markets.

    This prevents accidentally taking first-set winner, total games, handicap,
    asian or set markets from getAllOddsForEvent / getMatchFeaturedOdds.
    """
    name = normalize_name(" ".join(str(market.get(k) or "") for k in ("name", "marketName", "market_name", "label", "type", "marketType")))
    group = normalize_name(" ".join(str(market.get(k) or "") for k in ("marketGroup", "choiceGroup", "group", "market_group")))
    period = normalize_name(" ".join(str(market.get(k) or "") for k in ("marketPeriod", "period", "market_period")))
    haystack = " ".join([name, group, period]).strip()

    bad_tokens = (
        "first set", "1st set", "second set", "2nd set", "third set", "3rd set",
        "set winner", "total game", "total games", "total sets", "handicap",
        "asian", "correct score", "tie break", "tiebreak", "extra time",
        "game winner", "point", "statistics", "power graph",
    )
    if any(token in haystack for token in bad_tokens):
        return False

    # The actual match winner market in the API screenshots is:
    # marketName="Full time", marketGroup="Home/Away", marketPeriod="Match".
    if "full time" in name and (not period or "match" in period) and (not group or "home away" in group):
        return True
    if "match winner" in name or "to win match" in name or "moneyline" in name:
        return True
    if "home away" in group and ("match" in period or "full time" in name):
        return True

    return False


def normalize_winner_odds_payload(payload: Any) -> Optional[Dict[str, Any]]:
    """Normalize match-winner odds from TennisApi PRO payloads.

    Handles both market-style payloads and provider winning-odds payloads:
    - {home: {fractionalValue: ...}, away: {fractionalValue: ...}}
    - nested markets/odds/eventOdds/data/items with choices/outcomes/selections
    """
    if not payload:
        return None

    direct = payload
    if isinstance(direct, dict) and isinstance(direct.get("odds"), dict):
        direct = direct.get("odds")
    elif isinstance(direct, dict) and isinstance(direct.get("data"), dict):
        direct = direct.get("data")

    if isinstance(direct, dict):
        home = direct.get("home") or direct.get("homeOdds") or direct.get("home_odds")
        away = direct.get("away") or direct.get("awayOdds") or direct.get("away_odds")
        if isinstance(home, dict) and isinstance(away, dict):
            home_price = None
            away_price = None
            for key in ("decimalValue", "decimal", "decimalOdds", "price", "odds", "value", "fractionalValue"):
                home_price = fractional_to_decimal(home.get(key))
                if home_price is not None:
                    break
            for key in ("decimalValue", "decimal", "decimalOdds", "price", "odds", "value", "fractionalValue"):
                away_price = fractional_to_decimal(away.get(key))
                if away_price is not None:
                    break
            if home_price is not None and away_price is not None:
                return {
                    "player1_label": "1",
                    "player2_label": "2",
                    "odds_player1": home_price,
                    "odds_player2": away_price,
                    "p1_odds": home_price,
                    "p2_odds": away_price,
                    "home_odds": home_price,
                    "away_odds": away_price,
                    "odds1": home_price,
                    "odds2": away_price,
                    "bookmaker": "TennisApi",
                    "odds_source": "RapidAPI PRO winning odds",
                    "raw": payload,
                }

    for market in extract_markets(payload):
        choices = market_choices(market)
        if len(choices) < 2:
            continue
        if not is_match_winner_market(market):
            continue

        by_label: Dict[str, float] = {}
        ordered: List[Tuple[str, float]] = []
        for choice in choices:
            label = choice_name(choice)
            price = choice_price(choice)
            if price is None:
                continue
            norm_label = normalize_name(label)
            if norm_label in {"1", "home", "home team", "player 1", "player1"}:
                by_label["1"] = price
            elif norm_label in {"2", "away", "away team", "player 2", "player2"}:
                by_label["2"] = price
            ordered.append((label, price))

        if "1" in by_label and "2" in by_label:
            p1_label, p2_label = "1", "2"
            p1_price, p2_price = by_label["1"], by_label["2"]
        elif len(ordered) >= 2:
            p1_label, p1_price = ordered[0]
            p2_label, p2_price = ordered[1]
        else:
            continue

        return {
            "player1_label": p1_label,
            "player2_label": p2_label,
            "odds_player1": p1_price,
            "odds_player2": p2_price,
            "p1_odds": p1_price,
            "p2_odds": p2_price,
            "home_odds": p1_price,
            "away_odds": p2_price,
            "odds1": p1_price,
            "odds2": p2_price,
            "bookmaker": None,
            "odds_source": "RapidAPI PRO event odds",
            "raw": payload,
        }
    return None

def _numeric_outcome_direction(label1: Any, label2: Any) -> Optional[str]:
    l1 = normalize_name(label1)
    l2 = normalize_name(label2)
    if l1 in {"1", "home", "home team", "player 1", "player1"} and l2 in {"2", "away", "away team", "player 2", "player2"}:
        return "DIRECT_BY_NUMERIC_OUTCOME"
    if l1 in {"2", "away", "away team", "player 2", "player2"} and l2 in {"1", "home", "home team", "player 1", "player1"}:
        return "REVERSED_BY_NUMERIC_OUTCOME"
    return None


def orient_odds_to_match(match: Dict[str, Any], odds: Dict[str, Any]) -> Tuple[Any, Any, str, float, float]:
    p1 = odds.get("odds_player1")
    p2 = odds.get("odds_player2")
    label1 = odds.get("player1_label")
    label2 = odds.get("player2_label")
    player1 = match.get("player1")
    player2 = match.get("player2")

    numeric_direction = _numeric_outcome_direction(label1, label2)
    if numeric_direction == "DIRECT_BY_NUMERIC_OUTCOME":
        return p1, p2, numeric_direction, 1.0, 0.0
    if numeric_direction == "REVERSED_BY_NUMERIC_OUTCOME":
        return p2, p1, numeric_direction, 0.0, 1.0

    direct_score = min(name_match_score(player1, label1), name_match_score(player2, label2)) if label1 and label2 else 0.0
    reverse_score = min(name_match_score(player1, label2), name_match_score(player2, label1)) if label1 and label2 else 0.0

    if direct_score >= 0.78 and direct_score >= reverse_score:
        return p1, p2, "DIRECT_TO_MATCH_PLAYERS", round(direct_score, 4), round(reverse_score, 4)
    if reverse_score >= 0.78 and reverse_score > direct_score:
        return p2, p1, "REVERSED_TO_MATCH_PLAYERS", round(direct_score, 4), round(reverse_score, 4)
    return p1, p2, "DIRECT_OR_LABEL_UNKNOWN", round(direct_score, 4), round(reverse_score, 4)




def _betting_day_window_for_corq(target_date: Optional[datetime] = None) -> Tuple[datetime, datetime, str]:
    """Return the CorQ betting-day window in Europe/Bratislava.

    Daily CorQ predictions are intentionally based on a 06:00 -> 06:00 local
    betting day so morning runs do not republish matches that started shortly
    after midnight.
    """
    if target_date is None:
        local_ref = datetime.now(LOCAL_TZ)
        betting_day = local_ref.date()
        if local_ref.time() < datetime.strptime("06:00", "%H:%M").time():
            betting_day = betting_day - timedelta(days=1)
    else:
        if target_date.tzinfo is None:
            local_ref = target_date.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        else:
            local_ref = target_date.astimezone(LOCAL_TZ)
        betting_day = local_ref.date()
    start_local = datetime.combine(betting_day, datetime.strptime("06:00", "%H:%M").time(), tzinfo=LOCAL_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local, end_local, betting_day.isoformat()


def _event_start_datetime_utc(match: Dict[str, Any]) -> Optional[datetime]:
    for key in ("match_start", "start_time", "start_time_utc", "match_time_utc", "commence_time"):
        dt = parse_datetime(match.get(key))
        if dt is not None:
            return dt.astimezone(timezone.utc)
    raw = match.get("raw") if isinstance(match.get("raw"), dict) else {}
    for key in ("startTimestamp", "start_timestamp"):
        dt = parse_datetime(raw.get(key))
        if dt is not None:
            return dt.astimezone(timezone.utc)
    return None


def _fetch_dates_for_betting_window(start_local: datetime, end_local: datetime) -> List[datetime]:
    dates: List[datetime] = []
    current = start_local.date()
    last = end_local.date()
    while current <= last:
        dates.append(datetime.combine(current, datetime.min.time(), tzinfo=LOCAL_TZ))
        current = current + timedelta(days=1)
    return dates

def _raw_event_diagnostic_bucket(event: Dict[str, Any]) -> str:
    player1, player2 = event_players(event)
    if not player1 or not player2:
        keys = sorted(str(k) for k in event.keys())[:18]
        return "missing_players keys=" + ",".join(keys)
    normalized = normalize_event_for_corq(event)
    if not isinstance(normalized, dict):
        return "normalize_failed"
    if _event_start_datetime_utc(normalized) is None:
        return "missing_start"
    if normalized.get("is_doubles"):
        return "doubles"
    return "ok_normalized"


def _print_loader_coverage(raw_events: List[Dict[str, Any]], normalized: List[Dict[str, Any]]) -> None:
    try:
        from collections import Counter
        buckets = Counter(_raw_event_diagnostic_bucket(e) for e in raw_events if isinstance(e, dict))
        print("RAPIDAPI NORMALIZATION COVERAGE:")
        for key, count in buckets.most_common(12):
            print(f"  {count:4d} {key}")
        shown = 0
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            if _raw_event_diagnostic_bucket(event).startswith("missing_players"):
                print("RAPIDAPI MISSING PLAYERS SAMPLE:", {
                    "id": event.get("id") or event.get("event_id") or event.get("match_id"),
                    "keys": sorted(str(k) for k in event.keys())[:20],
                    "tournament": _team_name(event.get("tournament")),
                    "status": event.get("status"),
                    "startTimestamp": event.get("startTimestamp") or event.get("start_timestamp"),
                })
                shown += 1
                if shown >= 3:
                    break
    except Exception as exc:
        print(f"RAPIDAPI NORMALIZATION COVERAGE ERROR: {exc}")

def fetch_daily_matches_with_odds(target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    client = RapidApiClient()
    window_start_local, window_end_local, betting_day = _betting_day_window_for_corq(target_date)
    fetch_dates = _fetch_dates_for_betting_window(window_start_local, window_end_local)
    print("RAPIDAPI FETCH CALENDAR DATES: " + ", ".join(d.strftime("%Y-%m-%d") for d in fetch_dates))

    raw_events: List[Dict[str, Any]] = []
    for fetch_date in fetch_dates:
        raw_events.extend(client.get_events_for_date(fetch_date))
    raw_events = dedupe_events(raw_events)

    matches_before_window = [item for item in (normalize_event_for_corq(event) for event in raw_events) if isinstance(item, dict)]
    print(f"RAPIDAPI NORMALIZED EVENTS BEFORE WINDOW: {len(matches_before_window)}")
    _print_loader_coverage(raw_events, matches_before_window)
    print(f"RAPIDAPI BETTING DAY WINDOW LOCAL: {window_start_local.isoformat()} -> {window_end_local.isoformat()}")

    matches: List[Dict[str, Any]] = []
    skipped_before_window = 0
    skipped_after_window = 0
    skipped_missing_start = 0
    start_utc = window_start_local.astimezone(timezone.utc)
    end_utc = window_end_local.astimezone(timezone.utc)

    for match in matches_before_window:
        match_start_utc = _event_start_datetime_utc(match)
        if match_start_utc is None:
            skipped_missing_start += 1
            continue
        if match_start_utc < start_utc:
            skipped_before_window += 1
            continue
        if match_start_utc >= end_utc:
            skipped_after_window += 1
            continue
        row = dict(match)
        row["betting_day"] = betting_day
        row["betting_day_start_local"] = window_start_local.isoformat()
        row["betting_day_end_local"] = window_end_local.isoformat()
        row["betting_day_timezone"] = "Europe/Bratislava"
        matches.append(row)

    print(f"RAPIDAPI SKIPPED BEFORE BETTING DAY WINDOW: {skipped_before_window}")
    print(f"RAPIDAPI SKIPPED AFTER BETTING DAY WINDOW: {skipped_after_window}")
    print(f"RAPIDAPI SKIPPED MISSING START TIME: {skipped_missing_start}")
    print(f"RAPIDAPI MATCHES IN BETTING DAY WINDOW: {len(matches)}")
    for sample in matches[:8]:
        print(
            "RAPIDAPI WINDOW MATCH:",
            sample.get("event_id") or sample.get("match_id") or sample.get("id"),
            sample.get("player1"),
            "vs",
            sample.get("player2"),
            sample.get("match_start") or sample.get("start_time"),
            sample.get("status_type"),
        )

    output: List[Dict[str, Any]] = []

    attach_rankings = (
        str(os.getenv("TENNISAPI_ATTACH_RANKINGS", "0")).strip().lower()
        in {"1", "true", "yes", "y", "on"}
        and str(os.getenv("LUCQ_SOURCE_POLICY", "")).strip().upper() != "API_PRO_ONLY"
    )

    doubles_skipped_before_odds = 0
    singles_odds_attempted = 0
    singles_with_winner_odds = 0
    singles_missing_winner_odds = 0

    for match in matches:
        if match.get("is_doubles"):
            doubles_skipped_before_odds += 1
            continue
        if attach_rankings:
            match = client.attach_rankings_to_match(match)
        singles_odds_attempted += 1
        odds = client.get_event_odds(match.get("event_id"), match=match)
        row = dict(match)
        if odds:
            singles_with_winner_odds += 1
            p1, p2, direction, direct_score, reverse_score = orient_odds_to_match(match, odds)
            row.update({
                "odds_matching_direction": direction,
                "odds_label_1": odds.get("player1_label"),
                "odds_label_2": odds.get("player2_label"),
                "odds_direct_match_score": direct_score,
                "odds_reverse_match_score": reverse_score,
                "odds_player1": p1,
                "odds_player2": p2,
                "p1_odds": p1,
                "p2_odds": p2,
                "home_odds": p1,
                "away_odds": p2,
                "odds1": p1,
                "odds2": p2,
                "price1": p1,
                "price2": p2,
                "odds_source": odds.get("odds_source"),
                "odds_endpoint": odds.get("odds_endpoint"),
                "odds_status": odds.get("odds_status", "OK"),
                "odds_attempts": odds.get("odds_attempts", []),
                "odds_pair_available": p1 is not None and p2 is not None,
                "odds_labels_confirmed": direction in {
                    "DIRECT_TO_MATCH_PLAYERS",
                    "REVERSED_TO_MATCH_PLAYERS",
                    "DIRECT_BY_NUMERIC_OUTCOME",
                    "REVERSED_BY_NUMERIC_OUTCOME",
                },
            })
            if p1 is not None and p2 is not None:
                gap = abs(float(p1) - float(p2))
                row["odds_gap_abs"] = round(gap, 4)
                row["odds_gap_pct"] = round(gap / max(min(float(p1), float(p2)), 0.0001), 4)
        else:
            singles_missing_winner_odds += 1
            row.update({
                "odds_pair_available": False,
                "odds_labels_confirmed": False,
                "odds_matching_direction": "NO_ODDS",
                "odds_status": "MISSING",
                "odds_attempts": list(getattr(client, "last_odds_attempts", [])),
                "no_odds_reason": "NO_RAPIDAPI_PRO_ODDS",
            })
        output.append(row)
    try:
        stats = getattr(client, "odds_endpoint_stats", {}) or {}
        if stats:
            print("RAPIDAPI ODDS ENDPOINT STATS:")
            for endpoint_name, endpoint_stats in sorted(stats.items()):
                print(f"  {endpoint_name}: {endpoint_stats}")
    except Exception:
        pass
    print(f"RAPIDAPI DOUBLES SKIPPED BEFORE ODDS: {doubles_skipped_before_odds}")
    print(f"RAPIDAPI SINGLES ODDS ATTEMPTED: {singles_odds_attempted}")
    print(f"RAPIDAPI SINGLES WITH WINNER ODDS: {singles_with_winner_odds}")
    print(f"RAPIDAPI SINGLES MISSING WINNER ODDS: {singles_missing_winner_odds}")
    print(f"RAPIDAPI SINGLES ROWS RETURNED: {len(output)}")
    return output
# 2026-08-03 note: Daily odds loader uses /event/{id}/odds/{provider}/all only.
