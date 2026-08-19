from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from thinq.loaders.h2h_loader import build_h2h_context, load_h2h_cache

H2H_DATA_DIR = Path("thinq/data/h2h")
H2H_CACHE_PATH = H2H_DATA_DIR / "h2h_cache.json"
H2H_MANIFEST_PATH = H2H_DATA_DIR / "h2h_manifest.json"
H2H_MATCHUPS_PATH = H2H_DATA_DIR / "h2h_matchups.json"
RUNTIME_H2H_DIR = Path("runtime/h2h")
RUNTIME_REPORT_PATH = RUNTIME_H2H_DIR / "h2h_coverage_report.json"
PLAYER_REGISTRY_PATH = Path("thinq/data/players/player_registry.json")
ELO_UNIVERSE_PATH = Path("thinq/data/players/elo_player_universe.json")
CACHE_VERSION = "TENNISAPI_PRO_H2H_LAZY_CACHE_V1"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=json_default), encoding="utf-8")


def ensure_cache_file() -> None:
    H2H_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if H2H_CACHE_PATH.exists():
        return
    payload = {
        "version": CACHE_VERSION,
        "source": "TENNISAPI_PRO_H2H",
        "generated_at": now_iso(),
        "updated_at": now_iso(),
        "pairs": {},
        "empty_cache_reason": "created_by_update_h2h_data_no_pairs_yet",
    }
    write_json(H2H_CACHE_PATH, payload)


def rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "items", "all", "top7", "picks", "records", "data", "matches"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def load_rows(path: Path) -> List[Dict[str, Any]]:
    try:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return rows_from_payload(payload)
    except Exception as exc:
        print(f"[h2h] failed reading {path}: {exc}")
        return []


def first(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "N/A", "-", "None"):
            return value
    return None


def as_number(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "N/A", "-", "None"):
            return None
        number = float(str(value).replace(",", "."))
        return number
    except Exception:
        return None


def has_elo_fields(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    paired_keys = (
        ("pick_elo", "opponent_elo"),
        ("pick_elo_rating", "opponent_elo_rating"),
        ("thinq_pick_elo", "thinq_opponent_elo"),
        ("elo_pick", "elo_opponent"),
        ("p1_elo", "p2_elo"),
        ("player1_elo", "player2_elo"),
        ("elo_player1", "elo_player2"),
        ("ta_pick_elo", "ta_opp_elo"),
        ("ta_player1_elo", "ta_player2_elo"),
        ("pick_elo_score", "opponent_elo_score"),
    )
    for left_key, right_key in paired_keys:
        left = as_number(row.get(left_key))
        right = as_number(row.get(right_key))
        if left is not None and right is not None:
            return True, f"{left_key}+{right_key}"

    status = str(first(row, ("elo_status", "ta_elo_status", "thinq_elo_status")) or "").upper()
    if status in {"OK", "AVAILABLE", "READY", "VALID"}:
        return True, "elo_status"

    if row.get("elo_available") is True or row.get("ta_elo_available") is True:
        return True, "elo_available_flag"

    return False, None


def match_identity(row: Dict[str, Any]) -> Dict[str, Any]:
    custom_id = str(first(row, ("event_custom_id", "custom_id", "customId")) or "").strip()
    event_id = first(row, ("event_id", "match_id", "id"))
    if not custom_id and event_id not in (None, "") and not str(event_id).isdigit():
        custom_id = str(event_id).strip()
    pick = str(first(row, ("pick", "top7_pick", "cloq_pick", "player", "player1", "home_name")) or "").strip()
    opponent = str(first(row, ("opponent", "opp", "player2", "away_name")) or "").strip()
    surface = first(row, ("surface", "surface_raw", "groundType", "court"))
    pick_id = first(row, ("thinq_pick_player_id", "pick_player_id", "player1_id", "home_id", "home_player_id"))
    opponent_id = first(row, ("thinq_opponent_player_id", "opponent_player_id", "player2_id", "away_id", "away_player_id"))
    return {
        "custom_id": custom_id,
        "event_id": event_id or custom_id,
        "pick": pick,
        "opponent": opponent,
        "surface": surface,
        "pick_id": pick_id,
        "opponent_id": opponent_id,
    }


def get_source_files(outputs_dir: Path) -> List[Path]:
    return [
        outputs_dir / "latest_all.json",
        outputs_dir / "latest_top7.json",
        outputs_dir / "latest_cloq.json",
        outputs_dir / "cloq" / "latest_cloq.json",
    ]


def normalize_name(value: Any) -> str:
    import re
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact_key(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def load_player_universe(registry_path: Path = PLAYER_REGISTRY_PATH, universe_path: Path = ELO_UNIVERSE_PATH) -> Dict[str, Any]:
    result = {
        "loaded": False,
        "source": None,
        "player_count": 0,
        "ids": set(),
        "names": set(),
        "compact": set(),
    }

    payload = None
    source = None
    for path in (universe_path, registry_path):
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                source = str(path)
                break
        except Exception as exc:
            print(f"[h2h] failed reading player universe {path}: {exc}")

    if payload is None:
        return result

    rows = []
    if isinstance(payload, dict):
        if isinstance(payload.get("players"), list):
            rows = [x for x in payload.get("players") if isinstance(x, dict)]
        elif isinstance(payload.get("players"), dict):
            rows = [x for x in payload.get("players").values() if isinstance(x, dict)]
    elif isinstance(payload, list):
        rows = [x for x in payload if isinstance(x, dict)]

    for player in rows:
        if player.get("elo_available") is False and player.get("h2h_eligible") is not True:
            continue
        pid = first(player, ("player_id", "team_id", "id"))
        if pid not in (None, ""):
            try:
                result["ids"].add(int(float(str(pid))))
            except Exception:
                pass
        name = first(player, ("name", "player", "player_name"))
        if name:
            result["names"].add(normalize_name(name))
            result["compact"].add(compact_key(name))
        for key in ("normalized_name", "elo_name_key"):
            value = player.get(key)
            if value:
                result["names"].add(normalize_name(value))
        for key in ("compact_key", "elo_compact_key"):
            value = player.get(key)
            if value:
                result["compact"].add(compact_key(value))

    result["loaded"] = True
    result["source"] = source
    result["player_count"] = len(rows)
    return result


def player_in_universe(player_id: Any, player_name: Any, universe: Dict[str, Any]) -> bool:
    if not universe.get("loaded"):
        return False
    pid = first({"id": player_id}, ("id",))
    if pid not in (None, ""):
        try:
            if int(float(str(pid))) in universe.get("ids", set()):
                return True
        except Exception:
            pass
    name = str(player_name or "").strip()
    if name:
        if normalize_name(name) in universe.get("names", set()):
            return True
        if compact_key(name) in universe.get("compact", set()):
            return True
    return False


def h2h_allowed_by_player_universe(identity: Dict[str, Any], universe: Dict[str, Any]) -> Tuple[bool, str]:
    pick_ok = player_in_universe(identity.get("pick_id"), identity.get("pick"), universe)
    opponent_ok = player_in_universe(identity.get("opponent_id"), identity.get("opponent"), universe)
    if pick_ok and opponent_ok:
        return True, "both_players_in_elo_universe"
    if not pick_ok and not opponent_ok:
        return False, "both_players_missing_from_elo_universe"
    if not pick_ok:
        return False, "pick_missing_from_elo_universe"
    return False, "opponent_missing_from_elo_universe"


def build_work_queue(outputs_dir: Path, require_elo: bool, universe: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    seen = set()
    work: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    reject_counts: Dict[str, int] = {
        "missing_identity": 0,
        "missing_h2h_key": 0,
        "missing_elo_universe": 0,
        "pick_missing_from_elo_universe": 0,
        "opponent_missing_from_elo_universe": 0,
        "both_players_missing_from_elo_universe": 0,
        "duplicate": 0,
    }
    allowed_reason_hits: Dict[str, int] = {}

    for path in get_source_files(outputs_dir):
        rows = load_rows(path)
        source_counts[str(path)] = len(rows)
        print(f"[h2h] source={path} rows={len(rows)}")
        for row in rows:
            ident = match_identity(row)
            if not ident["pick"] or not ident["opponent"]:
                reject_counts["missing_identity"] += 1
                continue
            if not ident["custom_id"]:
                reject_counts["missing_h2h_key"] += 1
                continue
            row_has_elo_fields, row_elo_reason = has_elo_fields(row)
            allowed, allowed_reason = h2h_allowed_by_player_universe(ident, universe)
            if require_elo and not allowed:
                reject_counts[allowed_reason] = reject_counts.get(allowed_reason, 0) + 1
                reject_counts["missing_elo_universe"] += 1
                continue
            allowed_reason_hits[allowed_reason] = allowed_reason_hits.get(allowed_reason, 0) + 1
            sig = (str(ident["custom_id"]).lower(), ident["pick"].lower(), ident["opponent"].lower())
            if sig in seen:
                reject_counts["duplicate"] += 1
                continue
            seen.add(sig)
            work.append({"row": row, "identity": ident, "source_file": str(path), "elo_reason": allowed_reason, "row_elo_reason": row_elo_reason, "row_has_elo_fields": row_has_elo_fields})

    meta = {
        "source_counts": source_counts,
        "reject_counts": reject_counts,
        "allowed_reason_hits": allowed_reason_hits,
        "player_universe_loaded": universe.get("loaded"),
        "player_universe_source": universe.get("source"),
        "player_universe_count": universe.get("player_count"),
    }
    return work, meta


def h2h_model_status(ctx: Dict[str, Any]) -> str:
    """Return model-facing H2H status.

    Distinguishes API fetch success from usable historical H2H. A payload that
    contains only the current scheduled event is NO_PREVIOUS_H2H, not OK.
    """
    history_status = str(ctx.get("history_status") or "").strip().upper()
    if history_status == "OK":
        return "OK"
    if history_status in {"NO_PREVIOUS_H2H", "API_NO_DATA", "API_ERROR"}:
        return history_status
    api_error = str(ctx.get("api_error") or "").strip().lower()
    api_status = ctx.get("api_status_code")
    if api_error:
        if api_error.startswith("empty_status_") or api_error in {"empty_response_text", "missing_custom_id"}:
            return "API_NO_DATA"
        return "API_ERROR"
    if api_status in (204, 404):
        return "API_NO_DATA"
    if int(ctx.get("oriented_finished_event_count") or 0) > 0:
        return "OK"
    if int(ctx.get("api_event_count") or ctx.get("h2h_payload_event_count") or 0) > 0:
        return "NO_PREVIOUS_H2H"
    return "API_NO_DATA"


def cache_pair_count() -> int:
    try:
        payload = load_h2h_cache()
        pairs = payload.get("pairs") if isinstance(payload.get("pairs"), dict) else {}
        return len(pairs)
    except Exception:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prewarm ThinQ H2H cache for ELO-eligible current match rows")
    parser.add_argument("--outputs-dir", default=os.getenv("OUTPUTS_DIR", "outputs"))
    parser.add_argument("--max-requests", type=int, default=int(os.getenv("MAX_REQUESTS", "60") or 60))
    parser.add_argument("--require-elo", choices=("true", "false"), default=os.getenv("H2H_REQUIRE_ELO", "true"))
    parser.add_argument("--player-registry", default=os.getenv("PLAYER_REGISTRY_PATH", str(PLAYER_REGISTRY_PATH)))
    parser.add_argument("--elo-universe", default=os.getenv("ELO_UNIVERSE_PATH", str(ELO_UNIVERSE_PATH)))
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    require_elo = str(args.require_elo).lower() == "true"
    max_requests = max(int(args.max_requests or 0), 0)

    started_at = now_iso()
    ensure_cache_file()
    before_count = cache_pair_count()
    universe = load_player_universe(Path(args.player_registry), Path(args.elo_universe))
    work, meta = build_work_queue(outputs_dir, require_elo=require_elo, universe=universe)

    attempted = 0
    ok = 0
    no_data = 0
    errors = 0
    history_status_counts: Dict[str, int] = {}
    results: List[Dict[str, Any]] = []
    matchups: Dict[str, Dict[str, Any]] = {}

    for item in work:
        if attempted >= max_requests:
            print(f"[h2h] max_requests reached: {max_requests}")
            break
        ident = item["identity"]
        attempted += 1
        try:
            ctx = build_h2h_context(
                event_id=ident["event_id"],
                event_custom_id=ident["custom_id"],
                pick=ident["pick"],
                opponent=ident["opponent"],
                surface=ident["surface"],
                player1_id=ident["pick_id"],
                player2_id=ident["opponent_id"],
            )
            raw_status = ctx.get("status")
            model_status = h2h_model_status(ctx)
            history_status_counts[model_status] = history_status_counts.get(model_status, 0) + 1
            if model_status == "OK":
                ok += 1
            elif model_status == "API_ERROR":
                errors += 1
            else:
                no_data += 1
            result = {
                "custom_id": ident["custom_id"],
                "event_id": ident["event_id"],
                "pick": ident["pick"],
                "opponent": ident["opponent"],
                "surface": ident["surface"],
                "status": model_status,
                "raw_status": raw_status,
                "history_status": ctx.get("history_status"),
                "total_matches": ctx.get("total_matches"),
                "same_surface_matches": ctx.get("same_surface_matches"),
                "api_event_count": ctx.get("api_event_count"),
                "finished_event_count": ctx.get("finished_event_count"),
                "oriented_finished_event_count": ctx.get("oriented_finished_event_count"),
                "same_surface_finished_event_count": ctx.get("same_surface_finished_event_count"),
                "excluded_event_count": ctx.get("excluded_event_count"),
                "excluded_reasons": ctx.get("excluded_reasons"),
                "source": ctx.get("source"),
                "cache_key": ctx.get("cache_key"),
                "api_status_code": ctx.get("api_status_code"),
                "api_error": ctx.get("api_error"),
                "source_file": item.get("source_file"),
                "elo_reason": item.get("elo_reason"),
                "reason": ctx.get("reason"),
            }
            cache_key = result.get("cache_key") or ("custom:" + str(ident["custom_id"]))
            matchups[str(cache_key)] = {
                "custom_id": ident.get("custom_id"),
                "event_id": ident.get("event_id"),
                "h2h_cache_key": cache_key,
                "h2h_status": model_status,
                "h2h_raw_status": raw_status,
                "h2h_history_status": ctx.get("history_status"),
                "api_event_count": ctx.get("api_event_count"),
                "finished_event_count": ctx.get("finished_event_count"),
                "oriented_finished_event_count": ctx.get("oriented_finished_event_count"),
                "same_surface_finished_event_count": ctx.get("same_surface_finished_event_count"),
                "excluded_event_count": ctx.get("excluded_event_count"),
                "excluded_reasons": ctx.get("excluded_reasons"),
                "both_players_in_elo_universe": item.get("elo_reason") == "both_players_in_elo_universe",
                "player1_id": ident.get("pick_id"),
                "player1_name": ident.get("pick"),
                "player2_id": ident.get("opponent_id"),
                "player2_name": ident.get("opponent"),
                "surface": ident.get("surface"),
                "tournament": first(item.get("row") or {}, ("tournament", "category", "competition")),
                "start_time": first(item.get("row") or {}, ("start_time_utc", "match_time_utc", "start_time", "match_time", "commence_time")),
                "last_seen_at": finished_at if "finished_at" in locals() else now_iso(),
            }
            results.append(result)
            print("[h2h] " + json.dumps(result, ensure_ascii=False, sort_keys=True))
        except Exception as exc:
            errors += 1
            result = {
                "custom_id": ident.get("custom_id"),
                "pick": ident.get("pick"),
                "opponent": ident.get("opponent"),
                "status": "API_ERROR",
                "history_status": "API_ERROR",
                "error": str(exc),
                "source_file": item.get("source_file"),
            }
            history_status_counts["API_ERROR"] = history_status_counts.get("API_ERROR", 0) + 1
            results.append(result)
            print("[h2h] ERROR " + json.dumps(result, ensure_ascii=False, sort_keys=True))

    after_count = cache_pair_count()
    finished_at = now_iso()

    if require_elo and not universe.get("loaded"):
        status = "NO_ELO_UNIVERSE"
    elif len(work) == 0:
        status = "NO_ELIGIBLE_MATCHES" if require_elo else "NO_CANDIDATE_MATCHES"
    elif attempted == 0:
        status = "MAX_REQUESTS_ZERO"
    elif errors and not ok and not no_data:
        status = "ERROR"
    else:
        status = "OK"

    manifest = {
        "status": status,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "outputs_dir": str(outputs_dir),
        "require_elo": require_elo,
        "player_registry_path": str(Path(args.player_registry)),
        "elo_universe_path": str(Path(args.elo_universe)),
        "max_requests": max_requests,
        "candidate_pairs": len(work),
        "attempted": attempted,
        "ok": ok,
        "no_data": no_data,
        "errors": errors,
        "pair_count_before": before_count,
        "pair_count_after": after_count,
        "cache_path": str(H2H_CACHE_PATH),
        "manifest_path": str(H2H_MANIFEST_PATH),
        "matchups_path": str(H2H_MATCHUPS_PATH),
        "history_status_counts": history_status_counts,
        "runtime_report_path": str(RUNTIME_REPORT_PATH),
        **meta,
    }
    report = dict(manifest)
    report["results"] = results

    write_json(H2H_MANIFEST_PATH, manifest)
    write_json(H2H_MATCHUPS_PATH, {"version": CACHE_VERSION, "updated_at": finished_at, "matchups": matchups})
    write_json(RUNTIME_REPORT_PATH, report)

    print("[h2h] manifest")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
