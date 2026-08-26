from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_REGISTRY = Path("thinq/data/players/player_registry.json")
DEFAULT_OUTPUT = Path("thinq/data/players/api_pro_player_identities.json")
DEFAULT_RANKINGS = Path("thinq/data/rankings/api_pro_player_rankings.json")
DEFAULT_ROOTS = (
    "outputs",
    "runtime",
    "data",
    "thinq/data/cache",
    "thinq/data/h2h",
)

EXCLUDED_NAMES = {
    "player_registry.json",
    "elo_player_universe.json",
    "tennis_name_alias_database.json",
    # api_pro_player_rankings.json is intentionally NOT excluded.
    # It is a canonical real-data source for API PRO team IDs.
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def as_int(value: Any) -> Optional[int]:
    try:
        if value in (None, "", 0, "0"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_name(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split())


def country_code(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = (
            value.get("alpha3")
            or value.get("alpha2")
            or value.get("code")
            or value.get("name")
        )
    text = str(value or "").strip().upper()
    return text or None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def player_name(row: Dict[str, Any]) -> str:
    for key in (
        "display_name",
        "canonical_name",
        "name",
        "player",
        "player_name",
        "fullName",
        "shortName",
    ):
        name = clean_name(row.get(key))
        if name:
            return name
    return ""


def player_id(row: Dict[str, Any]) -> Optional[int]:
    for key in (
        "api_team_id",
        "rapidapi_id",
        "player_id",
        "team_id",
        "teamId",
        "playerId",
        "id",
    ):
        pid = as_int(row.get(key))
        if pid is not None:
            return pid
    return None


def extract_country(row: Dict[str, Any]) -> Optional[str]:
    for key in (
        "country_code",
        "country_alpha3",
        "country_alpha2",
        "country",
        "nationality",
    ):
        value = country_code(row.get(key))
        if value:
            return value
    return None


def iter_registry_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("players")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(rows, dict):
        return [row for row in rows.values() if isinstance(row, dict)]
    return []


def iter_identity_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("players")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and player_id(row) is not None
        and player_name(row)
    ]


def iter_candidate_objects(
    value: Any,
    context: str = "",
) -> Iterable[Tuple[Dict[str, Any], str]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_candidate_objects(item, context)
        return
    if not isinstance(value, dict):
        return

    # A row can itself be a player/team object.
    if player_id(value) is not None and player_name(value):
        yield value, context or "row"

    for key, item in value.items():
        lowered = str(key).lower()
        next_context = lowered or context
        if isinstance(item, dict) and lowered in {
            "hometeam",
            "awayteam",
            "home",
            "away",
            "player",
            "team",
            "player1",
            "player2",
            "pick_player",
            "opponent_player",
        }:
            yield item, next_context
        yield from iter_candidate_objects(item, next_context)

    flattened = (
        (
            "pick",
            ("pick_player_id", "thinq_pick_player_id", "pick_api_team_id"),
            ("pick", "top7_pick", "cloq_pick"),
        ),
        (
            "opponent",
            (
                "opponent_player_id",
                "thinq_opponent_player_id",
                "opponent_api_team_id",
            ),
            ("opponent", "opp"),
        ),
        ("home", ("home_id", "home_player_id"), ("home_name",)),
        ("away", ("away_id", "away_player_id"), ("away_name",)),
        ("player1", ("player1_id",), ("player1",)),
        ("player2", ("player2_id",), ("player2",)),
    )
    for side, id_keys, name_keys in flattened:
        pid = next(
            (
                as_int(value.get(key))
                for key in id_keys
                if as_int(value.get(key)) is not None
            ),
            None,
        )
        name = next(
            (
                clean_name(value.get(key))
                for key in name_keys
                if clean_name(value.get(key))
            ),
            "",
        )
        if pid is not None and name:
            yield {
                "id": pid,
                "name": name,
                "country": value.get(f"{side}_country"),
            }, side


def source_files(roots: Iterable[str], extra_files: Iterable[Path]) -> Iterable[Path]:
    seen = set()

    for path in extra_files:
        resolved = path.resolve() if path.exists() else path
        if path.is_file() and resolved not in seen:
            seen.add(resolved)
            yield path

    for root_text in roots:
        root = Path(root_text)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.json")
        for path in paths:
            resolved = path.resolve()
            if (
                path.name in EXCLUDED_NAMES
                or resolved in seen
                or not path.is_file()
            ):
                continue
            seen.add(resolved)
            yield path


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def merge_sources(*values: Any) -> List[str]:
    merged: List[str] = []
    for value in values:
        for source in value if isinstance(value, list) else []:
            text = str(source).strip()
            if text and text not in merged:
                merged.append(text)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Incrementally resolve API PRO player IDs from real repository payloads"
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--rankings", default=str(DEFAULT_RANKINGS))
    parser.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    args = parser.parse_args()

    registry_path = Path(args.registry)
    output_path = Path(args.output)
    rankings_path = Path(args.rankings)

    registry_rows = iter_registry_rows(load_json(registry_path))
    previous_payload = load_json(output_path)
    previous_rows = iter_identity_rows(previous_payload)

    # Preserve every previously resolved real identity, even if the current
    # registry temporarily omits that player.
    previous_by_name: Dict[str, Dict[str, Any]] = {}
    for row in previous_rows:
        key = normalize_name(player_name(row))
        if key:
            previous_by_name.setdefault(key, row)

    universe: Dict[str, Dict[str, Any]] = {}
    for row in registry_rows:
        key = normalize_name(player_name(row))
        if key:
            universe[key] = row
    for key, row in previous_by_name.items():
        universe.setdefault(key, row)

    candidates: Dict[str, Dict[int, Dict[str, Any]]] = {}
    files_scanned = 0
    objects_scanned = 0

    roots = [part.strip() for part in args.roots.split(",") if part.strip()]
    for path in source_files(roots, (rankings_path,)):
        payload = load_json(path)
        if payload is None:
            continue
        files_scanned += 1
        for obj, context in iter_candidate_objects(payload):
            objects_scanned += 1
            pid = player_id(obj)
            name = player_name(obj)
            key = normalize_name(name)
            if pid is None or not key or key not in universe:
                continue
            country = extract_country(obj)
            entry = candidates.setdefault(key, {}).setdefault(
                pid,
                {
                    "player_id": pid,
                    "name": name,
                    "country_code": country,
                    "sources": [],
                    "occurrences": 0,
                    "contexts": [],
                },
            )
            entry["occurrences"] += 1
            if country and not entry.get("country_code"):
                entry["country_code"] = country
            if str(path) not in entry["sources"]:
                entry["sources"].append(str(path))
            if context and context not in entry["contexts"]:
                entry["contexts"].append(context)

    resolved: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    preserved = 0
    newly_resolved = 0

    for key, row in sorted(universe.items()):
        name = player_name(row)
        previous = previous_by_name.get(key)
        previous_id = player_id(previous or {})
        registry_id = player_id(row)

        # Previously resolved ID has priority and cannot be erased by a later
        # missing value, empty refresh, or temporary source failure.
        if previous_id is not None:
            resolved.append(
                {
                    "player_id": previous_id,
                    "name": name or player_name(previous or {}),
                    "country_code": (
                        extract_country(row)
                        or extract_country(previous or {})
                    ),
                    "status": "PRESERVED_EXISTING_ID",
                    "sources": merge_sources(
                        (previous or {}).get("sources"),
                        ["previous_identity_cache"],
                    ),
                }
            )
            preserved += 1
            continue

        if registry_id is not None:
            resolved.append(
                {
                    "player_id": registry_id,
                    "name": name,
                    "country_code": extract_country(row),
                    "status": "EXISTING_ID",
                    "sources": ["player_registry"],
                }
            )
            preserved += 1
            continue

        options = candidates.get(key, {})
        if len(options) == 1:
            item = dict(next(iter(options.values())))
            item["name"] = name
            item["status"] = "EXACT_NORMALIZED_NAME"
            resolved.append(item)
            newly_resolved += 1
        elif len(options) > 1:
            ambiguous.append(
                {
                    "name": name,
                    "status": "AMBIGUOUS",
                    "candidates": sorted(
                        options.values(),
                        key=lambda item: (
                            -item["occurrences"],
                            item["player_id"],
                        ),
                    ),
                }
            )
        else:
            unresolved.append({"name": name, "status": "NOT_FOUND"})

    # Hard regression guard: a successful incremental run must never reduce
    # the number of resolved identities already present in the cache.
    if len(resolved) < len(previous_rows):
        raise RuntimeError(
            "Identity regression blocked: "
            f"previous={len(previous_rows)}, new={len(resolved)}"
        )

    payload = {
        "version": "API_PRO_PLAYER_IDENTITIES_V2_INCREMENTAL",
        "generated_at": now_iso(),
        "policy": (
            "preserve_existing_real_ids_add_new_exact_matches_"
            "never_replace_with_missing_no_guesses"
        ),
        "stats": {
            "registry_players": len(registry_rows),
            "identity_universe": len(universe),
            "previous_resolved": len(previous_rows),
            "preserved": preserved,
            "newly_resolved": newly_resolved,
            "files_scanned": files_scanned,
            "objects_scanned": objects_scanned,
            "resolved": len(resolved),
            "ambiguous": len(ambiguous),
            "unresolved": len(unresolved),
        },
        "players": resolved,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
    }

    write_atomic(output_path, payload)
    print(json.dumps(payload["stats"], indent=2))
    print(f"Identity cache written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
