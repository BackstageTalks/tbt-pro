from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PLAYER_DIR = Path("thinq/data/players")
REGISTRY_PATH = PLAYER_DIR / "player_registry.json"
ELO_UNIVERSE_PATH = PLAYER_DIR / "elo_player_universe.json"
ALIAS_DB_PATH = PLAYER_DIR / "tennis_name_alias_database.json"
MANIFEST_PATH = PLAYER_DIR / "player_registry_manifest.json"
RUNTIME_DIR = Path("runtime/players")
RUNTIME_REPORT_PATH = RUNTIME_DIR / "player_registry_report.json"

DEFAULT_OUTPUT_FILES = (
    "outputs/latest_all.json",
    "outputs/latest_top7.json",
    "outputs/latest_cloq.json",
    "outputs/cloq/latest_cloq.json",
)

DEFAULT_ELO_FILES = (
    "thinq/data/elo/ta_elo_ratings.json",
    "thinq/data/elo/elo_cache.json",
    "thinq/data/elo/elo_players_index.json",
)

DEFAULT_RANKING_FILES = (
    "thinq/data/rankings/api_pro_player_rankings.json",
    "thinq/data/rankings/atp_rankings.json",
    "thinq/data/rankings/wta_rankings.json",
    "thinq/data/rankings/api_rankings_atp.json",
    "thinq/data/rankings/api_rankings_wta.json",
    "data/api_pro/rankings/atp_rankings.json",
    "data/api_pro/rankings/wta_rankings.json",
    "data/rankings/atp_rankings.json",
    "data/rankings/wta_rankings.json",
)

SPECIAL_CHARS = {
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ß": "ss", "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i", "İ": "I",
}

MOJIBAKE_REPLACEMENTS = {
    "Ä‡": "ć", "Ä": "ć", "Ä": "č", "Ä‘": "đ", "Å¡": "š", "Å¾": "ž",
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ", "Ã§": "ç",
    "Ã¼": "ü", "Ã¶": "ö", "Ã¤": "ä", "â€™": "'", "â€˜": "'", "â€“": "-", "â€”": "-",
}

MANUAL_CANONICAL_OVERRIDES = {
    "ivajovic": "Iva Jović",
    "felixaugeraliassime": "Felix Auger-Aliassime",
    "joaofonseca": "Joao Fonseca",
    "christopheroconnell": "Christopher O'Connell",
}

MANUAL_ALIASES = {
    "ivajovic": ["Iva Jovic", "Iva Jović", "Iva JoviÄ‡"],
    "felixaugeraliassime": ["Felix Auger Aliassime", "Félix Auger-Aliassime", "Felix Auger-Aliassime"],
    "joaofonseca": ["Joao Fonseca", "João Fonseca"],
    "christopheroconnell": ["Christopher OConnell", "Christopher O'Connell", "Christopher O Connell"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[players] failed to read {path}: {exc}")
    return None


def fix_mojibake(value: Any) -> str:
    text = str(value or "").strip()
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(value: Any) -> str:
    text = fix_mojibake(value).lower()
    text = "".join(SPECIAL_CHARS.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def canonical_name(value: Any) -> str:
    fixed = fix_mojibake(value)
    key = compact_key(fixed)
    return MANUAL_CANONICAL_OVERRIDES.get(key, fixed)


def unique_names(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = fix_mojibake(value)
        key = compact_key(text)
        if text and key and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", "N/A", "-", "None"):
            return None
        text = str(value)
        if text.startswith("api:") or text.startswith("id:"):
            text = text.split(":", 1)[1]
        return int(float(text.replace(",", ".")))
    except Exception:
        return None


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "N/A", "-", "None"):
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def first_value(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "N/A", "-", "None"):
            return value
    return None


def rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("players", "rows", "items", "data", "rankings", "results", "records", "all", "top7", "picks", "matches"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict) and key == "players":
                return [dict(v, registry_key=k) for k, v in value.items() if isinstance(v, dict)]
        nested = payload.get("data")
        if isinstance(nested, dict):
            return rows_from_payload(nested)
    return []


def player_name_from_team(team: Any) -> str:
    if isinstance(team, dict):
        for key in ("name", "fullName", "displayName", "shortName", "slug"):
            value = team.get(key)
            if value:
                return str(value)
    return ""


def player_id_from_team(team: Any) -> Optional[int]:
    if not isinstance(team, dict):
        return None
    for key in ("id", "teamId", "playerId"):
        value = as_int(team.get(key))
        if value is not None:
            return value
    pti = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    return as_int(pti.get("id"))


def make_player_key(player_id: Any, name: Any) -> str:
    pid = as_int(player_id)
    if pid is not None:
        return f"api:{pid}"
    return f"name:{compact_key(name)}"


def ensure_player(registry: Dict[str, Dict[str, Any]], player_id: Any, name: Any) -> Optional[Dict[str, Any]]:
    raw_name = fix_mojibake(name)
    cname = canonical_name(raw_name)
    pid = as_int(player_id)
    if not cname and pid is None:
        return None
    key = make_player_key(pid, cname)
    player = registry.get(key)
    if player is None:
        player = {
            "registry_key": key,
            "player_id": pid,
            "api_team_id": pid,
            "rapidapi_id": pid,
            "name": cname,
            "canonical_name": cname,
            "display_name": cname,
            "normalized_name": normalize_name(cname),
            "compact_key": compact_key(cname),
            "aliases": [],
            "sources": [],
            "rank": None,
            "rank_points": None,
            "country_code": None,
            "country_name": None,
            "updated_at": now_iso(),
        }
        registry[key] = player
    else:
        if pid is not None:
            player["player_id"] = pid
            player["api_team_id"] = pid
            player["rapidapi_id"] = pid
        if cname and (not player.get("name") or player.get("name") != canonical_name(player.get("name"))):
            player["name"] = canonical_name(player.get("name") or cname)
            player["canonical_name"] = canonical_name(player.get("canonical_name") or cname)
            player["display_name"] = player["canonical_name"]
            player["normalized_name"] = normalize_name(player["canonical_name"])
            player["compact_key"] = compact_key(player["canonical_name"])
    aliases = player.setdefault("aliases", [])
    for alias in unique_names([raw_name, cname] + MANUAL_ALIASES.get(compact_key(cname), [])):
        if compact_key(alias) != compact_key(player.get("canonical_name")) and alias not in aliases:
            aliases.append(alias)
    return player


def touch_source(player: Dict[str, Any], source: str) -> None:
    sources = player.setdefault("sources", [])
    if source not in sources:
        sources.append(source)
    player["updated_at"] = now_iso()


def iter_elo_players(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        players = payload.get("players")
        if isinstance(players, dict):
            out = []
            for key, value in players.items():
                if isinstance(value, dict):
                    row = dict(value)
                    row.setdefault("player", row.get("name") or key)
                    out.append(row)
                else:
                    out.append({"player": key, "elo": value})
            return out
        if isinstance(players, list):
            return [x for x in players if isinstance(x, dict)]
    return rows_from_payload(payload)


def load_elo_cache(registry: Dict[str, Dict[str, Any]], files: Iterable[Path]) -> Dict[str, Any]:
    stats = {"files_found": 0, "rows": 0, "players_added_or_updated": 0}
    for path in files:
        payload = read_json(path)
        if payload is None:
            continue
        stats["files_found"] += 1
        rows = iter_elo_players(payload)
        stats["rows"] += len(rows)
        for row in rows:
            name = first_value(row, ("player", "name", "player_name", "full_name"))
            if not name:
                continue
            player = ensure_player(registry, first_value(row, ("api_team_id", "rapidapi_id", "player_id", "team_id", "id")), name)
            if player is None:
                continue
            player["elo_available"] = True
            player["h2h_eligible"] = True
            player["tour"] = str(first_value(row, ("tour", "category", "gender")) or player.get("tour") or "").upper() or None
            for src_key, dst_key in (
                ("elo", "elo"), ("overall_elo", "elo"), ("rating", "elo"),
                ("hard_elo", "hard_elo"), ("clay_elo", "clay_elo"), ("grass_elo", "grass_elo"),
                ("name_key", "elo_name_key"), ("compact_key", "elo_compact_key"),
            ):
                value = row.get(src_key)
                if value not in (None, ""):
                    player[dst_key] = as_float(value) if dst_key in {"elo", "hard_elo", "clay_elo", "grass_elo"} else value
            touch_source(player, str(path))
            stats["players_added_or_updated"] += 1
    return stats


def ranking_team(row: Dict[str, Any]) -> Dict[str, Any]:
    team = row.get("team") if isinstance(row.get("team"), dict) else {}
    if not team and any(key in row for key in ("name", "id", "ranking")):
        team = row
    return team


def country_fields(row: Dict[str, Any], team: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    raw = team.get("country") or row.get("country") or row.get("nationality")
    name: Optional[str] = None
    alpha2: Optional[str] = None
    alpha3: Optional[str] = None
    if isinstance(raw, dict):
        name = first_value(raw, ("name", "country_name", "displayName", "display_name"))
        alpha2 = first_value(raw, ("alpha2", "country_code", "code", "iso2"))
        alpha3 = first_value(raw, ("alpha3", "iso3"))
    elif raw not in (None, ""):
        text = str(raw).strip()
        if len(text) == 2 and text.isalpha():
            alpha2 = text
        elif len(text) == 3 and text.isalpha():
            alpha3 = text
        else:
            name = text
    alpha2 = str(alpha2).upper() if alpha2 else None
    alpha3 = str(alpha3).upper() if alpha3 else None
    return str(name).strip() if name else None, alpha2, alpha3


def apply_public_enrichment_aliases(player: Dict[str, Any]) -> None:
    rank = as_int(player.get("rank") or player.get("api_rank"))
    points = as_int(player.get("rank_points") or player.get("api_points"))
    country_name = first_value(player, ("country_name", "country"))
    country_code = first_value(player, ("country_code", "country_alpha2", "country_alpha3"))
    player["rank"] = rank
    player["rank_points"] = points
    player["country_name"] = str(country_name).strip() if country_name else None
    player["country_code"] = str(country_code).upper().strip() if country_code else None
    # Compatibility fields remain during migration; models should consume public fields above.
    player["api_rank"] = rank
    player["api_points"] = points
    if player["country_name"]:
        player["country"] = player["country_name"]


def load_rankings(registry: Dict[str, Dict[str, Any]], files: Iterable[Path]) -> Dict[str, Any]:
    stats = {"files_found": 0, "rows": 0, "players_updated": 0}
    for path in files:
        payload = read_json(path)
        if payload is None:
            continue
        stats["files_found"] += 1
        rows = rows_from_payload(payload)
        stats["rows"] += len(rows)
        for row in rows:
            team = ranking_team(row)
            name = player_name_from_team(team) or first_value(row, ("player", "name", "player_name"))
            player_id = player_id_from_team(team) or first_value(row, ("api_team_id", "player_id", "team_id", "id"))
            player = ensure_player(registry, player_id, name)
            if player is None:
                continue
            category = team.get("gender") or row.get("tour") or row.get("category")
            if category:
                player["tour"] = str(category).upper()
            rank = as_int(first_value(row, ("ranking", "rank", "position", "currentRank", "current_rank")) or team.get("ranking"))
            points = as_int(first_value(row, ("points", "rankingPoints", "ranking_points", "rank_points", "currentPoints", "current_points")))
            if rank is not None:
                player["rank"] = rank
                player["api_rank"] = rank
            if points is not None:
                player["rank_points"] = points
                player["api_points"] = points
            country_name, alpha2, alpha3 = country_fields(row, team)
            if country_name:
                player["country_name"] = country_name
                player["country"] = country_name
            if alpha2:
                player["country_code"] = alpha2
                player["country_alpha2"] = alpha2
            if alpha3:
                player["country_alpha3"] = alpha3
                if not player.get("country_code"):
                    player["country_code"] = alpha3
            apply_public_enrichment_aliases(player)
            touch_source(player, str(path))
            stats["players_updated"] += 1
    return stats


def extract_output_players(row: Dict[str, Any]) -> List[Tuple[Any, Any, str]]:
    out: List[Tuple[Any, Any, str]] = []
    sides = (
        ("pick", ("thinq_pick_player_id", "pick_player_id", "player1_id", "home_id", "home_player_id", "pick_api_team_id"), ("pick", "top7_pick", "cloq_pick", "player", "player1", "home_name")),
        ("opponent", ("thinq_opponent_player_id", "opponent_player_id", "player2_id", "away_id", "away_player_id", "opponent_api_team_id"), ("opponent", "opp", "player2", "away_name")),
    )
    for side, id_keys, name_keys in sides:
        pid = first_value(row, id_keys)
        name = first_value(row, name_keys)
        if pid is not None or name:
            out.append((pid, name, side))
    for obj_key, side in (("homeTeam", "home"), ("awayTeam", "away"), ("home", "home"), ("away", "away")):
        obj = row.get(obj_key)
        if isinstance(obj, dict):
            out.append((player_id_from_team(obj), player_name_from_team(obj), side))
    return out


def load_outputs(registry: Dict[str, Dict[str, Any]], files: Iterable[Path]) -> Dict[str, Any]:
    stats = {"files_found": 0, "rows": 0, "players_updated": 0}
    for path in files:
        rows = rows_from_payload(read_json(path))
        if not rows:
            continue
        stats["files_found"] += 1
        stats["rows"] += len(rows)
        for row in rows:
            for pid, name, side in extract_output_players(row):
                player = ensure_player(registry, pid, name)
                if player is None:
                    continue
                player["last_seen_in_outputs"] = now_iso()
                player.setdefault("seen_sides", [])
                if side not in player["seen_sides"]:
                    player["seen_sides"].append(side)
                country = first_value(row, (f"{side}_country", f"{side}_country_name"))
                if country and not player.get("country"):
                    player["country"] = country
                touch_source(player, str(path))
                stats["players_updated"] += 1
    return stats


def calculate_elo_ranks(registry: Dict[str, Dict[str, Any]]) -> None:
    for tour in ("ATP", "WTA", "M", "F", ""):
        group = [p for p in registry.values() if p.get("elo_available") and (not tour or str(p.get("tour") or "").upper() == tour)]
        if not group:
            continue
        for metric, rank_key in (("elo", "elo_rank_tour"), ("hard_elo", "hard_elo_rank_tour"), ("clay_elo", "clay_elo_rank_tour"), ("grass_elo", "grass_elo_rank_tour")):
            ranked = sorted([p for p in group if as_float(p.get(metric)) is not None], key=lambda p: float(p.get(metric)), reverse=True)
            for idx, player in enumerate(ranked, 1):
                player[rank_key] = idx


def build_name_indexes(registry: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, str]]:
    by_name: Dict[str, str] = {}
    by_compact: Dict[str, str] = {}
    for key, player in registry.items():
        names = [player.get("name"), player.get("canonical_name"), player.get("display_name"), player.get("sackmann_name")]
        names.extend(player.get("aliases") if isinstance(player.get("aliases"), list) else [])
        names.extend([player.get("elo_name_key"), player.get("elo_compact_key")])
        for name in names:
            nkey = normalize_name(name)
            ckey = compact_key(name)
            if nkey:
                by_name.setdefault(nkey, key)
            if ckey:
                by_compact.setdefault(ckey, key)
    return by_name, by_compact


def build_alias_database(registry: Dict[str, Dict[str, Any]], path: Path) -> Dict[str, Any]:
    existing = read_json(path)
    manual_players = []
    if isinstance(existing, dict) and isinstance(existing.get("players"), list):
        manual_players = [p for p in existing["players"] if isinstance(p, dict)]
    by_key = {str(p.get("registry_key") or p.get("player_id") or p.get("api_team_id") or p.get("canonical_name")): p for p in manual_players}
    for registry_key, player in registry.items():
        aliases = unique_names([player.get("name"), player.get("canonical_name"), player.get("display_name")] + list(player.get("aliases") or []))
        by_key[registry_key] = {
            "player_id": registry_key,
            "api_team_id": player.get("api_team_id"),
            "rapidapi_id": player.get("rapidapi_id"),
            "canonical_name": player.get("canonical_name") or player.get("name"),
            "display_name": player.get("display_name") or player.get("canonical_name") or player.get("name"),
            "tour": player.get("tour"),
            "country": player.get("country"),
            "aliases": aliases,
            "search_key": compact_key(player.get("canonical_name") or player.get("name")),
        }
    players = sorted(by_key.values(), key=lambda p: (str(p.get("tour") or ""), str(p.get("canonical_name") or "")))
    alias_resolution = {}
    for player in players:
        pid = player.get("player_id")
        if not pid:
            continue
        for alias in unique_names([player.get("canonical_name"), player.get("display_name")] + list(player.get("aliases") or [])):
            key = compact_key(alias)
            if key:
                alias_resolution[key] = {"status": "resolved", "resolved_player_id": pid}
    payload = {
        "version": "TENNIS_NAME_ALIAS_DATABASE_V1",
        "generated_at": now_iso(),
        "source": "tools/build_player_registry.py",
        "policy": "manual_aliases_preserved_generated_registry_aliases_added",
        "players": players,
        "alias_resolution": alias_resolution,
    }
    write_json(path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified API/ELO player registry and alias database")
    parser.add_argument("--elo-files", default=",".join(DEFAULT_ELO_FILES))
    parser.add_argument("--ranking-files", default=",".join(DEFAULT_RANKING_FILES))
    parser.add_argument("--output-files", default=",".join(DEFAULT_OUTPUT_FILES))
    parser.add_argument("--skip-alias-db", action="store_true")
    args = parser.parse_args()

    registry: Dict[str, Dict[str, Any]] = {}
    elo_files = [Path(x.strip()) for x in args.elo_files.split(",") if x.strip()]
    ranking_files = [Path(x.strip()) for x in args.ranking_files.split(",") if x.strip()]
    output_files = [Path(x.strip()) for x in args.output_files.split(",") if x.strip()]

    elo_stats = load_elo_cache(registry, elo_files)
    ranking_stats = load_rankings(registry, ranking_files)
    output_stats = load_outputs(registry, output_files)
    for player in registry.values():
        apply_public_enrichment_aliases(player)
    calculate_elo_ranks(registry)
    by_name, by_compact = build_name_indexes(registry)

    players_sorted = sorted(
        registry.values(),
        key=lambda p: (0 if p.get("elo_available") else 1, str(p.get("tour") or ""), as_int(p.get("elo_rank_tour")) or 999999, str(p.get("canonical_name") or p.get("name") or "")),
    )

    registry_payload = {
        "version": "PLAYER_REGISTRY_V2_CANONICAL_NAMES",
        "generated_at": now_iso(),
        "source": "ELO_CACHE_PLUS_API_OUTPUTS_AND_OPTIONAL_RANKINGS",
        "player_count": len(players_sorted),
        "elo_player_count": sum(1 for p in players_sorted if p.get("elo_available")),
        "api_rank_player_count": sum(1 for p in players_sorted if p.get("rank") is not None),
        "players": players_sorted,
        "index": {
            "by_name": by_name,
            "by_compact_key": by_compact,
        },
    }

    elo_players = [p for p in players_sorted if p.get("elo_available")]
    universe_payload = {
        "version": "ELO_PLAYER_UNIVERSE_V2_CANONICAL_NAMES",
        "generated_at": now_iso(),
        "source": "ELO_CACHE",
        "player_count": len(elo_players),
        "players": [
            {
                "registry_key": p.get("registry_key"),
                "player_id": p.get("player_id"),
                "api_team_id": p.get("api_team_id"),
                "name": p.get("canonical_name") or p.get("name"),
                "canonical_name": p.get("canonical_name") or p.get("name"),
                "normalized_name": p.get("normalized_name"),
                "compact_key": p.get("compact_key"),
                "tour": p.get("tour"),
                "elo": p.get("elo"),
                "hard_elo": p.get("hard_elo"),
                "clay_elo": p.get("clay_elo"),
                "grass_elo": p.get("grass_elo"),
                "elo_rank_tour": p.get("elo_rank_tour"),
                "rank": p.get("rank"),
                "rank_points": p.get("rank_points"),
                "country_code": p.get("country_code"),
                "country_name": p.get("country_name"),
                "api_rank": p.get("api_rank"),
                "api_points": p.get("api_points"),
                "h2h_eligible": True,
            }
            for p in elo_players
        ],
    }

    alias_db_stats = {"written": False, "path": str(ALIAS_DB_PATH), "players": 0, "aliases": 0}
    if not args.skip_alias_db:
        alias_payload = build_alias_database(registry, ALIAS_DB_PATH)
        alias_db_stats = {
            "written": True,
            "path": str(ALIAS_DB_PATH),
            "players": len(alias_payload.get("players") or []),
            "aliases": len(alias_payload.get("alias_resolution") or {}),
        }

    manifest = {
        "status": "OK" if elo_players else "NO_ELO_PLAYERS_FOUND",
        "generated_at": now_iso(),
        "registry_path": str(REGISTRY_PATH),
        "elo_universe_path": str(ELO_UNIVERSE_PATH),
        "alias_database_path": str(ALIAS_DB_PATH),
        "player_count": len(players_sorted),
        "elo_player_count": len(elo_players),
        "api_rank_player_count": registry_payload["api_rank_player_count"],
        "elo_stats": elo_stats,
        "ranking_stats": ranking_stats,
        "output_stats": output_stats,
        "alias_db_stats": alias_db_stats,
    }

    write_json(REGISTRY_PATH, registry_payload)
    write_json(ELO_UNIVERSE_PATH, universe_payload)
    write_json(MANIFEST_PATH, manifest)
    write_json(RUNTIME_REPORT_PATH, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
