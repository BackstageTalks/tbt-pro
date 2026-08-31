"""Build an independent BlinQ player registry from existing repository JSON files.

ThinQ files are read-only inputs. This module writes only below blinq/data/players.
Matches are accepted only by API ID or an exact, unique normalized full name.
No fuzzy, surname-only, inferred, or manually fabricated identity is permitted.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SOURCE_REGISTRY = Path("thinq/data/players/player_registry.json")
IDENTITIES_PATH = Path("thinq/data/players/api_pro_player_identities.json")
RANKINGS_PATH = Path("thinq/data/rankings/api_pro_player_rankings.json")
OUTPUT_DIR = Path("blinq/data/players")
OUTPUT_REGISTRY = OUTPUT_DIR / "player_registry.json"
UNRESOLVED_OUTPUT = OUTPUT_DIR / "unresolved_players.json"
MANIFEST_OUTPUT = OUTPUT_DIR / "manifest.json"

_TRANSLATE = str.maketrans({
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th", "ß": "ss", "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
})


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().translate(_TRANSLATE).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def _int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        text = str(value)
        if ":" in text and text.split(":", 1)[0].lower() in {"api", "id"}:
            text = text.split(":", 1)[1]
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _name(row: Dict[str, Any]) -> str:
    return str(row.get("canonical_name") or row.get("display_name") or row.get("player") or row.get("name") or "").strip()


def _rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("players", "rankings", "rows", "items", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _rows(value)
            if nested:
                return nested
    return []


def _team(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("team") if isinstance(row.get("team"), dict) else row


def _row_id(row: Dict[str, Any]) -> Optional[int]:
    team = _team(row)
    info = team.get("playerTeamInfo") if isinstance(team.get("playerTeamInfo"), dict) else {}
    for value in (
        row.get("player_id"), row.get("api_team_id"), row.get("rapidapi_id"),
        team.get("id"), team.get("teamId"), team.get("playerId"), info.get("id"),
    ):
        parsed = _int(value)
        if parsed is not None:
            return parsed
    return None


def _row_name(row: Dict[str, Any]) -> str:
    team = _team(row)
    return str(
        row.get("canonical_name") or row.get("display_name") or row.get("player")
        or team.get("name") or team.get("fullName") or team.get("displayName")
        or team.get("shortName") or ""
    ).strip()


def _country(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    team = _team(row)
    raw = team.get("country") or row.get("country") or row.get("nationality")
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("displayName") or raw.get("country_name")
        code = raw.get("alpha3") or raw.get("alpha2") or raw.get("code") or raw.get("iso3") or raw.get("iso2")
        return (str(name).strip() if name else None, str(code).upper().strip() if code else None)
    if raw:
        text = str(raw).strip()
        return (None, text.upper()) if len(text) in (2, 3) else (text, None)
    code = row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2")
    return None, str(code).upper().strip() if code else None


def _rank(row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    team = _team(row)
    rank = _int(row.get("ranking") or row.get("rank") or row.get("position") or team.get("ranking"))
    points = _int(row.get("points") or row.get("rankingPoints") or row.get("ranking_points") or row.get("rank_points"))
    return rank, points


def _exact_index(rows: Iterable[Dict[str, Any]]) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        player_id = _row_id(row)
        name_key = compact_name(_row_name(row))
        if player_id is not None:
            by_id.setdefault(player_id, row)
        if name_key:
            by_name.setdefault(name_key, []).append(row)
    return by_id, by_name


def _unique_name_match(name: str, index: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    candidates = index.get(compact_name(name), [])
    ids = {_row_id(row) for row in candidates if _row_id(row) is not None}
    if len(ids) != 1:
        return None
    player_id = next(iter(ids))
    return next((row for row in candidates if _row_id(row) == player_id), None)


def build_registry() -> Dict[str, Any]:
    source = _read(SOURCE_REGISTRY)
    source_rows = _rows(source)
    identity_rows = _rows(_read(IDENTITIES_PATH))
    ranking_rows = _rows(_read(RANKINGS_PATH))
    identity_by_id, identity_by_name = _exact_index(identity_rows)
    ranking_by_id, ranking_by_name = _exact_index(ranking_rows)

    players: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    resolved_by_exact_name = 0

    for raw in source_rows:
        row = dict(raw)
        name = _name(row)
        player_id = _int(row.get("api_team_id") or row.get("rapidapi_id") or row.get("player_id"))
        identity = identity_by_id.get(player_id) if player_id is not None else None
        ranking = ranking_by_id.get(player_id) if player_id is not None else None

        if player_id is None:
            identity = _unique_name_match(name, identity_by_name)
            ranking = _unique_name_match(name, ranking_by_name)
            candidate_id = _row_id(identity or {}) or _row_id(ranking or {})
            if candidate_id is not None:
                player_id = candidate_id
                resolved_by_exact_name += 1

        if player_id is not None:
            identity = identity or identity_by_id.get(player_id)
            ranking = ranking or ranking_by_id.get(player_id)

        rank, points = _rank(ranking or {})
        country_name, country_code = _country(ranking or identity or {})
        row.update({
            "player": name,
            "canonical_name": name,
            "display_name": name,
            "normalized_name": normalize_name(name),
            "compact_key": compact_name(name),
            "player_id": player_id,
            "api_team_id": player_id,
            "rapidapi_id": player_id,
            "registry_key": f"api:{player_id}" if player_id is not None else f"name:{compact_name(name)}",
            "rank": rank if rank is not None else _int(row.get("rank") or row.get("api_rank")),
            "rank_points": points if points is not None else _int(row.get("rank_points") or row.get("api_points")),
            "country_name": country_name or row.get("country_name") or row.get("country"),
            "country_code": country_code or row.get("country_code") or row.get("country_alpha3") or row.get("country_alpha2"),
            "elo_eligible": row.get("elo") is not None,
            "form_eligible": player_id is not None,
            "h2h_eligible": player_id is not None,
            "identity_status": "RESOLVED" if player_id is not None else "UNRESOLVED",
        })
        players.append(row)
        if player_id is None:
            unresolved.append({
                "player": name,
                "compact_key": compact_name(name),
                "reason": "NO_EXACT_UNIQUE_API_ID",
                "elo_available": row.get("elo") is not None,
            })

    players.sort(key=lambda row: str(row.get("player") or "").casefold())
    by_compact = {row["compact_key"]: row["registry_key"] for row in players if row.get("compact_key")}
    generated_at = _now()
    payload = {
        "version": "BLINQ_PLAYER_REGISTRY_V1",
        "generated_at": generated_at,
        "source_policy": "READ_ONLY_THINQ_INPUTS_EXACT_UNIQUE_MATCHES_ONLY",
        "player_count": len(players),
        "resolved_player_count": sum(1 for row in players if row.get("player_id") is not None),
        "unresolved_player_count": len(unresolved),
        "resolved_by_exact_name": resolved_by_exact_name,
        "players": players,
        "index": {"by_compact_key": by_compact},
    }
    unresolved_payload = {
        "version": "BLINQ_UNRESOLVED_PLAYERS_V1",
        "generated_at": generated_at,
        "count": len(unresolved),
        "players": unresolved,
    }
    manifest = {
        "status": "OK" if players else "NO_PLAYERS",
        "generated_at": generated_at,
        "inputs": {
            str(SOURCE_REGISTRY): SOURCE_REGISTRY.exists(),
            str(IDENTITIES_PATH): IDENTITIES_PATH.exists(),
            str(RANKINGS_PATH): RANKINGS_PATH.exists(),
        },
        "outputs": [str(OUTPUT_REGISTRY), str(UNRESOLVED_OUTPUT)],
        "player_count": len(players),
        "resolved_player_count": payload["resolved_player_count"],
        "unresolved_player_count": len(unresolved),
    }
    _write(OUTPUT_REGISTRY, payload)
    _write(UNRESOLVED_OUTPUT, unresolved_payload)
    _write(MANIFEST_OUTPUT, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build independent BlinQ player registry")
    parser.parse_args()
    manifest = build_registry()
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
