from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
RANKINGS_PATH = ROOT / "thinq" / "data" / "rankings" / "ta_rankings.json"
OUTPUT_PATH = ROOT / "thinq" / "data" / "ta_profiles" / "ta_player_profiles.json"

TA_BASE = "https://www.tennisabstract.com"
ATP_RANKINGS_URL = "https://tennisabstract.com/reports/atpRankings.html"
WTA_RANKINGS_URL = "https://tennisabstract.com/reports/wtaRankings.html"
ATP_PROFILE_URL = "https://www.tennisabstract.com/cgi-bin/player.cgi?p={player_key}"
WTA_PROFILE_URL = "https://www.tennisabstract.com/cgi-bin/wplayer.cgi?p={player_key}"

USER_AGENT = os.getenv(
    "TA_USER_AGENT",
    "Mozilla/5.0 (compatible; TBT-PRO-TA-Cache/1.0; +https://backstagetalks.example)",
)
REQUEST_TIMEOUT = int(os.getenv("TA_REQUEST_TIMEOUT_SECONDS", "25"))
REQUEST_DELAY_SECONDS = float(os.getenv("TA_REQUEST_DELAY_SECONDS", "0.35"))
DEFAULT_LIMIT = int(os.getenv("TA_PROFILE_LIMIT", "650"))

SURFACE_KEYS = {
    "hard": "hard",
    "clay": "clay",
    "grass": "grass",
    "carpet": "carpet",
}

STAT_FIELDS = {
    "M": "matches",
    "W": "wins",
    "L": "losses",
    "Win%": "win_pct",
    "Set W-L": "set_wl",
    "Set%": "set_pct",
    "Game W-L": "game_wl",
    "Game%": "game_pct",
    "TB W-L": "tb_wl",
    "TB%": "tb_pct",
    "A%": "ace_pct",
    "DF%": "df_pct",
    "1stIn": "first_in_pct",
    "1st%": "first_won_pct",
    "2nd%": "second_won_pct",
    "SPW": "serve_points_won_pct",
    "RPW": "return_points_won_pct",
    "TPW": "total_points_won_pct",
    "DR": "dominance_ratio",
}


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def normalize_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ł", "l").replace("đ", "d").replace("ð", "d").replace("þ", "th")
    text = text.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("œ", "oe")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_name(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(name))


def key_from_player_name(name: str) -> str:
    # Tennis Abstract profile keys are normally FirstLast without spaces/punctuation.
    parts = re.findall(r"[A-Za-z0-9]+", unicodedata.normalize("NFKD", str(name or "")))
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "nan", "None"}:
        return None
    text = text.replace("%", "").replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def parse_wl(value: Any) -> Optional[Dict[str, Any]]:
    text = str(value or "").strip()
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
    if not m:
        return None
    w = int(m.group(1))
    l = int(m.group(2))
    total = w + l
    return {"wins": w, "losses": l, "total": total, "win_pct": round(100.0 * w / total, 2) if total else None}


def fetch_url(url: str, retries: int = 2) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 + attempt * 0.5)
    raise RuntimeError(f"TA fetch failed url={url} error={last_error}")


def load_existing_rankings() -> List[Dict[str, Any]]:
    if not RANKINGS_PATH.exists():
        return []
    try:
        payload = json.loads(RANKINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []
    players = payload.get("players") if isinstance(payload, dict) else None
    if isinstance(players, dict):
        iterable = players.values()
    elif isinstance(players, list):
        iterable = players
    elif isinstance(payload, list):
        iterable = payload
    else:
        iterable = []

    for rec in iterable:
        if not isinstance(rec, dict):
            continue
        name = rec.get("player_name") or rec.get("name") or rec.get("player") or rec.get("Player")
        if not name:
            continue
        tour = str(rec.get("tour") or rec.get("gender") or rec.get("source") or "").lower()
        if "wta" in tour or tour == "w":
            tour = "wta"
        elif "atp" in tour or tour == "m":
            tour = "atp"
        else:
            tour = "wta" if rec.get("wta_rank") or rec.get("WTA Rank") else "atp"
        player_key = rec.get("player_key") or rec.get("ta_key") or rec.get("key") or key_from_player_name(str(name))
        profile_url = rec.get("profile_url") or (WTA_PROFILE_URL if tour == "wta" else ATP_PROFILE_URL).format(player_key=player_key)
        rows.append({
            "player_name": str(name),
            "player_key": str(player_key),
            "tour": tour,
            "rank": rec.get("rank") or rec.get("ta_rank") or rec.get("Rank") or rec.get("wta_rank") or rec.get("atp_rank"),
            "profile_url": profile_url,
            "source": "ranking_cache",
        })
    return rows


def scrape_ranking_page(url: str, tour: str) -> List[Dict[str, Any]]:
    html_text = fetch_url(url)
    pattern = r'<a[^>]+href=["\'](?:https?://(?:www\.)?tennisabstract\.com)?/cgi-bin/(?:wplayer|player)\.cgi\?p=([^"\'&#]+)[^"\']*["\'][^>]*>(.*?)</a>'
    rows: List[Dict[str, Any]] = []
    seen = set()
    for player_key, label in re.findall(pattern, html_text, flags=re.I | re.S):
        name = re.sub(r"<[^>]+>", "", label)
        name = html.unescape(name).strip()
        if not name or player_key in seen:
            continue
        seen.add(player_key)
        rows.append({
            "player_name": name,
            "player_key": player_key,
            "tour": tour,
            "rank": None,
            "profile_url": (WTA_PROFILE_URL if tour == "wta" else ATP_PROFILE_URL).format(player_key=player_key),
            "source": "ranking_page",
        })
    return rows


def build_player_index(limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    rows = load_existing_rankings()
    if not rows:
        rows = scrape_ranking_page(WTA_RANKINGS_URL, "wta") + scrape_ranking_page(ATP_RANKINGS_URL, "atp")

    dedup: Dict[str, Dict[str, Any]] = {}
    for rec in rows:
        key = f"{rec.get('tour')}:{rec.get('player_key')}"
        if key not in dedup:
            dedup[key] = rec
    out = list(dedup.values())

    def rank_sort(rec: Dict[str, Any]) -> Tuple[int, str]:
        val = to_float(rec.get("rank"))
        return (int(val) if val is not None else 999999, str(rec.get("player_name") or ""))

    out.sort(key=rank_sort)
    return out[:limit] if limit and limit > 0 else out


def try_read_tables(html_text: str) -> List[Any]:
    try:
        import pandas as pd  # type: ignore
        return pd.read_html(StringIO(html_text))
    except Exception:
        return []


def normalize_columns(df: Any) -> Any:
    try:
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception:
        return df


def record_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for src, dst in STAT_FIELDS.items():
        if src not in row:
            continue
        raw = row.get(src)
        if src in {"Set W-L", "Game W-L", "TB W-L"}:
            out[dst] = parse_wl(raw)
        elif src in {"M", "W", "L"}:
            val = to_float(raw)
            out[dst] = int(val) if val is not None else None
        else:
            out[dst] = to_float(raw)
    return {k: v for k, v in out.items() if v is not None}


def parse_table_rows(tables: List[Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "last52": {"overall": {}, "surface": {}},
        "career": {"overall": {}, "surface": {}},
        "current_season": {},
        "splits": {},
    }

    for raw_df in tables:
        df = normalize_columns(raw_df)
        try:
            columns = set(str(c) for c in df.columns)
            records = df.to_dict(orient="records")
        except Exception:
            continue

        # Tour / season table: Year + M/W/L + A%/RPW/DR
        if "Year" in columns and {"M", "W", "L"}.issubset(columns):
            for row in records:
                label = str(row.get("Year") or "").strip()
                rec = record_from_row(row)
                if not rec:
                    continue
                if label.lower().startswith("career"):
                    data["career"]["overall"] = rec
                elif re.match(r"^20\d{2}$", label) and not data["current_season"]:
                    data["current_season"] = {"year": int(label), **rec}

        # Split table: Split + stats, usually Career or Last 52 splits.
        if "Split" in columns and {"M", "W", "L"}.issubset(columns):
            # Heuristic: if a table contains Last 52 in surrounding title we cannot always know from read_html.
            # Put the most recent-looking surface rows into both last52 and career if empty, then later model can use status/depth.
            for row in records:
                split = str(row.get("Split") or "").strip()
                rec = record_from_row(row)
                if not split or not rec:
                    continue
                split_key = split.lower().replace(" ", "_")
                if split.lower() in SURFACE_KEYS:
                    surface = SURFACE_KEYS[split.lower()]
                    # Prefer filling last52 surface first. If already filled, keep alternate in career.
                    if not data["last52"]["surface"].get(surface):
                        data["last52"]["surface"][surface] = rec
                    else:
                        data["career"]["surface"][surface] = rec
                elif split_key in {"last_52", "last52", "overall"}:
                    data["last52"]["overall"] = rec
                else:
                    data["splits"][split_key] = rec

    return data


def parse_profile_text(html_text: str) -> Dict[str, Any]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
    text = re.sub(r"\s+", " ", text)
    out: Dict[str, Any] = {}

    current_rank = re.search(r"Current rank:\s*(\d+)", text, flags=re.I)
    if current_rank:
        out["current_rank"] = int(current_rank.group(1))

    elo = re.search(r"Elo rank:\s*(\d+)\s*\(\s*rating:\s*([0-9.]+)\s*\)", text, flags=re.I)
    if elo:
        out["elo_rank"] = int(float(elo.group(1)))
        out["elo_rating"] = float(elo.group(2))

    plays = re.search(r"Plays:\s*([^\(\n]+)", text, flags=re.I)
    if plays:
        out["hand"] = plays.group(1).strip()

    return out


def parse_profile(player: Dict[str, Any], html_text: str) -> Dict[str, Any]:
    tables = try_read_tables(html_text)
    table_data = parse_table_rows(tables)
    text_data = parse_profile_text(html_text)
    status = "OK" if tables else "PARTIAL_NO_TABLES"

    return {
        "player_name": player.get("player_name"),
        "player_key": player.get("player_key"),
        "tour": player.get("tour"),
        "rank": player.get("rank") or text_data.get("current_rank"),
        "profile_url": player.get("profile_url"),
        "source": "tennis_abstract",
        "updated_at": now_iso(),
        "status": status,
        "profile": text_data,
        "last52": table_data.get("last52", {}),
        "career": table_data.get("career", {}),
        "current_season": table_data.get("current_season", {}),
        "splits": table_data.get("splits", {}),
    }


def load_cache(path: Path = OUTPUT_PATH) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {"generated_at": None, "players": {}}


def save_cache(payload: Dict[str, Any], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def build_profiles(limit: int = DEFAULT_LIMIT, force_refresh: bool = False) -> Dict[str, Any]:
    players = build_player_index(limit=limit)
    cache = load_cache()
    existing_players = cache.get("players") if isinstance(cache.get("players"), dict) else {}
    if not isinstance(existing_players, dict):
        existing_players = {}

    result_players: Dict[str, Any] = dict(existing_players)
    stats = {"requested": len(players), "updated": 0, "skipped": 0, "failed": 0}

    for idx, player in enumerate(players, 1):
        key = compact_name(player.get("player_name")) or compact_name(player.get("player_key"))
        if not key:
            continue
        if not force_refresh and key in result_players and result_players[key].get("status") == "OK":
            stats["skipped"] += 1
            continue
        url = str(player.get("profile_url") or "")
        try:
            print(f"[TA] {idx}/{len(players)} fetch {player.get('player_name')} {url}")
            html_text = fetch_url(url)
            result_players[key] = parse_profile(player, html_text)
            stats["updated"] += 1
            time.sleep(REQUEST_DELAY_SECONDS)
        except Exception as exc:
            stats["failed"] += 1
            result_players[key] = {
                "player_name": player.get("player_name"),
                "player_key": player.get("player_key"),
                "tour": player.get("tour"),
                "profile_url": url,
                "source": "tennis_abstract",
                "updated_at": now_iso(),
                "status": "FETCH_FAILED",
                "error": str(exc)[:500],
            }
            time.sleep(REQUEST_DELAY_SECONDS)

    payload = {
        "generated_at": now_iso(),
        "source": "tennis_abstract_player_profiles",
        "ranking_source": str(RANKINGS_PATH),
        "profile_count": len(result_players),
        "stats": stats,
        "players": result_players,
    }
    save_cache(payload)
    print(f"[TA] wrote {OUTPUT_PATH} profiles={len(result_players)} stats={stats}")
    return payload


def lookup_profile(name: str, cache_path: Path = OUTPUT_PATH) -> Optional[Dict[str, Any]]:
    cache = load_cache(cache_path)
    players = cache.get("players") if isinstance(cache.get("players"), dict) else {}
    key = compact_name(name)
    if key in players:
        return players[key]
    # Try loose key against player_name/player_key.
    for rec in players.values():
        if not isinstance(rec, dict):
            continue
        if compact_name(rec.get("player_name")) == key or compact_name(rec.get("player_key")) == key:
            return rec
    return None


def build_match_ta_context(pick: str, opponent: str, surface: str = "") -> Dict[str, Any]:
    pick_profile = lookup_profile(pick)
    opp_profile = lookup_profile(opponent)
    surface_key = str(surface or "").strip().lower()
    surface_key = SURFACE_KEYS.get(surface_key, surface_key)

    def surface_stats(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not profile:
            return {}
        last52 = profile.get("last52") if isinstance(profile.get("last52"), dict) else {}
        surf = last52.get("surface") if isinstance(last52.get("surface"), dict) else {}
        if surface_key and isinstance(surf, dict) and surf.get(surface_key):
            return surf.get(surface_key) or {}
        overall = last52.get("overall") if isinstance(last52.get("overall"), dict) else {}
        return overall or {}

    p_stats = surface_stats(pick_profile)
    o_stats = surface_stats(opp_profile)

    return {
        "ta_status": "OK" if pick_profile or opp_profile else "N/A",
        "ta_pick_status": (pick_profile or {}).get("status") if pick_profile else "N/A",
        "ta_opp_status": (opp_profile or {}).get("status") if opp_profile else "N/A",
        "ta_pick_set_pct": p_stats.get("set_pct"),
        "ta_opp_set_pct": o_stats.get("set_pct"),
        "ta_pick_game_pct": p_stats.get("game_pct"),
        "ta_opp_game_pct": o_stats.get("game_pct"),
        "ta_pick_tb_split": p_stats.get("tb_wl"),
        "ta_opp_tb_split": o_stats.get("tb_wl"),
        "ta_pick_ace_pct": p_stats.get("ace_pct"),
        "ta_opp_ace_pct": o_stats.get("ace_pct"),
        "ta_pick_surface_dr": p_stats.get("dominance_ratio"),
        "ta_opp_surface_dr": o_stats.get("dominance_ratio"),
        "ta_pick_rpw_pct": p_stats.get("return_points_won_pct"),
        "ta_opp_rpw_pct": o_stats.get("return_points_won_pct"),
        "ta_pick_depth": ta_depth_from_stats(p_stats),
        "ta_opp_depth": ta_depth_from_stats(o_stats),
        "pick_aces_line": None,
        "opponent_aces_line": None,
        "total_aces_line": None,
        "aces_status": "N/A",
    }


def ta_depth_from_stats(stats: Dict[str, Any]) -> Optional[float]:
    if not stats:
        return None
    score = 0.0
    matches = to_float(stats.get("matches")) or 0.0
    score += min(matches / 25.0, 1.0) * 35.0
    for key in ("set_pct", "game_pct", "ace_pct", "return_points_won_pct", "dominance_ratio"):
        if stats.get(key) is not None:
            score += 13.0
    return round(min(score, 100.0), 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Tennis Abstract player profile cache")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    build_profiles(limit=args.limit, force_refresh=args.force_refresh)


if __name__ == "__main__":
    main()
