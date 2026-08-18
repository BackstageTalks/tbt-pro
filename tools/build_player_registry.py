from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PLAYER_DIR = Path("thinq/data/players")
REGISTRY_PATH = PLAYER_DIR / "player_registry.json"
ELO_UNIVERSE_PATH = PLAYER_DIR / "elo_player_universe.json"
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
    "thinq/data/rankings/atp_rankings.json",
    "thinq/data/rankings/wta_rankings.json",
    "thinq/data/rankings/api_rankings_atp.json",
    "thinq/data/rankings/api_rankings_wta.json",
    "data/api_pro/rankings/atp_rankings.json",
    "data/api_pro/rankings/wta_rankings.json",
    "data/rankings/atp_rankings.json",
    "data/rankings/wta_rankings.json",
)


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


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", "N/A", "-", "None"):
            return None
        return int(float(str(value).replace(",", ".")))
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
    value = as_int(pti.get("id"))
    if value is not None:
        return value
    return None


def make_player_key(player_id: Any, name: Any) -> str:
    pid = as_int(player_id)
    if pid is not None:
        return f"id:{pid}"
    return f"name:{compact_key(name)}"


def ensure_player(registry: Dict[str, Dict[str, Any]], player_id: Any, name: Any) -> Optional[Dict[str, Any]]:
    name_text = str(name or "").strip()
    pid = as_int(player_id)
    if not name_text and pid is None:
        return None
    key = make_player_key(pid, name_text)
    player = registry.get(key)
    if player is None:
        player = {
            "registry_key": key,
            "player_id": pid,
            "name": name_text,
            "normalized_name": normalize_name(name_text),
            "compact_key": compact_key(name_text),
            "sources": [],
            "updated_at": now_iso(),
        }
        registry[key] = player
    else:
        if pid is not None and player.get("player_id") is None:
            player["player_id"] = pid
        if name_text and not player.get("name"):
            player["name"] = name_text
            player["normalized_name"] = normalize_name(name_text)
            player["compact_key"] = compact_key(name_text)
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
            player = ensure_player(registry, first_value(row, ("player_id", "team_id", "id")), name)
            if player is None:
                continue
            player["elo_available"] = True
            player["h2h_eligible"] = True
            player["tour"] = str(first_value(row, ("tour", "category", "gender")) or player.get("tour") or "").upper() or None
            for src_key, dst_key in (
                ("elo", "elo"),
                ("overall_elo", "elo"),
                ("rating", "elo"),
                ("hard_elo", "hard_elo"),
                ("clay_elo", "clay_elo"),
                ("grass_elo", "grass_elo"),
                ("name_key", "elo_name_key"),
                ("compact_key", "elo_compact_key"),
            ):
                value = row.get(src_key)
                if value not in (None, ""):
                    player[dst_key] = as_float(value) if "elo" in dst_key and dst_key != "elo_name_key" and dst_key != "elo_compact_key" else value
            touch_source(player, str(path))
            stats["players_added_or_updated"] += 1
    return stats


def ranking_team(row: Dict[str, Any]) -> Dict[str, Any]:
    team = row.get("team") if isinstance(row.get("team"), dict) else {}
    if not team and any(key in row for key in ("name", "id", "ranking")):
        team = row
    return team


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
            player_id = player_id_from_team(team) or first_value(row, ("player_id", "team_id", "id"))
            player = ensure_player(registry, player_id, name)
            if player is None:
                continue
            category = team.get("gender") or row.get("tour") or row.get("category")
            if category:
                player["tour"] = str(category).upper()
            rank = as_int(row.get("ranking") or row.get("rank") or team.get("ranking"))
            if rank is not None:
                player["api_rank"] = rank
            points = as_int(row.get("points") or row.get("rankingPoints") or row.get("rank_points"))
            if points is not None:
                player["api_points"] = points
            country = team.get("country") if isinstance(team.get("country"), dict) else row.get("country")
            if isinstance(country, dict):
                player["country"] = country.get("name")
                player["country_alpha2"] = country.get("alpha2")
                player["country_alpha3"] = country.get("alpha3")
            touch_source(player, str(path))
            stats["players_updated"] += 1
    return stats


def extract_output_players(row: Dict[str, Any]) -> List[Tuple[Any, Any, str]]:
    out: List[Tuple[Any, Any, str]] = []
    sides = (
        ("pick", ("thinq_pick_player_id", "pick_player_id", "player1_id", "home_id", "home_player_id"), ("pick", "top7_pick", "cloq_pick", "player", "player1", "home_name")),
        ("opponent", ("thinq_opponent_player_id", "opponent_player_id", "player2_id", "away_id", "away_player_id"), ("opponent", "opp", "player2", "away_name")),
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
        name_key = normalize_name(player.get("name"))
        compact = compact_key(player.get("name"))
        if name_key:
            by_name.setdefault(name_key, key)
        if compact:
            by_compact.setdefault(compact, key)
        for alias_key in ("elo_name_key", "elo_compact_key"):
            alias = str(player.get(alias_key) or "")
            if alias:
                by_name.setdefault(normalize_name(alias), key)
                by_compact.setdefault(compact_key(alias), key)
    return by_name, by_compact


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified API/ELO player registry")
    parser.add_argument("--elo-files", default=",".join(DEFAULT_ELO_FILES))
    parser.add_argument("--ranking-files", default=",".join(DEFAULT_RANKING_FILES))
    parser.add_argument("--output-files", default=",".join(DEFAULT_OUTPUT_FILES))
    args = parser.parse_args()

    registry: Dict[str, Dict[str, Any]] = {}
    elo_files = [Path(x.strip()) for x in args.elo_files.split(",") if x.strip()]
    ranking_files = [Path(x.strip()) for x in args.ranking_files.split(",") if x.strip()]
    output_files = [Path(x.strip()) for x in args.output_files.split(",") if x.strip()]

    elo_stats = load_elo_cache(registry, elo_files)
    ranking_stats = load_rankings(registry, ranking_files)
    output_stats = load_outputs(registry, output_files)
    calculate_elo_ranks(registry)
    by_name, by_compact = build_name_indexes(registry)

    players_sorted = sorted(registry.values(), key=lambda p: (0 if p.get("elo_available") else 1, str(p.get("tour") or ""), as_int(p.get("elo_rank_tour")) or 999999, str(p.get("name") or "")))
    registry_payload = {
        "version": "PLAYER_REGISTRY_V1",
        "generated_at": now_iso(),
        "source": "ELO_CACHE_PLUS_API_OUTPUTS_AND_OPTIONAL_RANKINGS",
        "player_count": len(players_sorted),
        "elo_player_count": sum(1 for p in players_sorted if p.get("elo_available")),
        "api_rank_player_count": sum(1 for p in players_sorted if p.get("api_rank") is not None),
        "players": players_sorted,
        "index": {
            "by_name": by_name,
            "by_compact_key": by_compact,
        },
    }

    elo_players = [p for p in players_sorted if p.get("elo_available")]
    universe_payload = {
        "version": "ELO_PLAYER_UNIVERSE_V1",
        "generated_at": now_iso(),
        "source": "ELO_CACHE",
        "player_count": len(elo_players),
        "players": [
            {
                "registry_key": p.get("registry_key"),
                "player_id": p.get("player_id"),
                "name": p.get("name"),
                "normalized_name": p.get("normalized_name"),
                "compact_key": p.get("compact_key"),
                "tour": p.get("tour"),
                "elo": p.get("elo"),
                "hard_elo": p.get("hard_elo"),
                "clay_elo": p.get("clay_elo"),
                "grass_elo": p.get("grass_elo"),
                "elo_rank_tour": p.get("elo_rank_tour"),
                "api_rank": p.get("api_rank"),
                "api_points": p.get("api_points"),
                "h2h_eligible": True,
            }
            for p in elo_players
        ],
    }

    manifest = {
        "status": "OK" if elo_players else "NO_ELO_PLAYERS_FOUND",
        "generated_at": now_iso(),
        "registry_path": str(REGISTRY_PATH),
        "elo_universe_path": str(ELO_UNIVERSE_PATH),
        "player_count": len(players_sorted),
        "elo_player_count": len(elo_players),
        "api_rank_player_count": registry_payload["api_rank_player_count"],
        "elo_stats": elo_stats,
        "ranking_stats": ranking_stats,
        "output_stats": output_stats,
    }

    write_json(REGISTRY_PATH, registry_payload)
    write_json(ELO_UNIVERSE_PATH, universe_payload)
    write_json(MANIFEST_PATH, manifest)
    write_json(RUNTIME_REPORT_PATH, manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
