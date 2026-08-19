from __future__ import annotations

import argparse
import json
import os
import re
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


def has_elo_pair(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
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






def repair_mojibake_text(value: Any) -> Any:
    """Repair common UTF-8-as-Latin1 mojibake in names, e.g. MenÅ¡ik -> Menšik.

    This is intentionally conservative and only tries to repair strings that contain
    typical mojibake markers. Non-string values are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    if not value:
        return value
    markers = ("Ã", "Å", "Ä", "Â", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "")
    if not any(marker in value for marker in markers):
        return value
    candidates = []
    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding, errors="strict").decode("utf-8", errors="strict")
            candidates.append(repaired)
        except Exception:
            pass
    for repaired in candidates:
        if repaired and repaired != value and not any(marker in repaired for marker in markers[:4]):
            return repaired
    return value


def repair_mojibake_obj(value: Any) -> Any:
    if isinstance(value, str):
        return repair_mojibake_text(value)
    if isinstance(value, list):
        return [repair_mojibake_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_mojibake_obj(item) for key, item in value.items()}
    return value

def nested_first(row: Dict[str, Any], paths: Iterable[Tuple[str, ...]]) -> Any:
    for path in paths:
        value: Any = row
        ok = True
        for key in path:
            if not isinstance(value, dict):
                ok = False
                break
            value = value.get(key)
        if ok and value not in (None, "", "N/A", "-", "None"):
            return value
    return None


def custom_id_from_endpoint(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"/api/tennis/event/([^/]+)/h2h", text)
    if match:
        custom_id = match.group(1).strip()
        if custom_id and not custom_id.isdigit():
            return custom_id
    return None

def match_identity(row: Dict[str, Any]) -> Dict[str, Any]:
    custom_id = str(first(row, (
        "event_custom_id",
        "custom_id",
        "customId",
        "h2h_custom_id",
        "thinq_h2h_custom_id",
        "thinq_h2h_requested_event_custom_id",
        "requested_event_custom_id",
    )) or "").strip()

    if not custom_id:
        nested_custom = nested_first(row, (
            ("thinq", "h2h", "requested_event_custom_id"),
            ("thinq", "contexts", "h2h", "requested_event_custom_id"),
            ("thinq", "h2h", "event_custom_id"),
            ("thinq", "contexts", "h2h", "event_custom_id"),
            ("h2h", "requested_event_custom_id"),
            ("h2h", "event_custom_id"),
        ))
        custom_id = str(nested_custom or "").strip()

    if not custom_id:
        endpoint_value = first(row, ("thinq_h2h_endpoint", "h2h_endpoint", "api_h2h_endpoint"))
        endpoint_value = endpoint_value or nested_first(row, (
            ("thinq", "h2h", "endpoint"),
            ("thinq", "contexts", "h2h", "endpoint"),
            ("h2h", "endpoint"),
        ))
        custom_id = custom_id_from_endpoint(endpoint_value) or ""

    event_id = first(row, (
        "event_id",
        "match_id",
        "id",
        "thinq_h2h_requested_event_id",
        "requested_event_id",
    ))
    event_id = event_id or nested_first(row, (
        ("thinq", "h2h", "requested_event_id"),
        ("thinq", "contexts", "h2h", "requested_event_id"),
        ("h2h", "requested_event_id"),
    ))
    if not custom_id and event_id not in (None, "") and not str(event_id).isdigit():
        custom_id = str(event_id).strip()

    pick = str(repair_mojibake_text(first(row, ("pick", "top7_pick", "cloq_pick", "player", "player1", "home_name")) or "")).strip()
    opponent = str(repair_mojibake_text(first(row, ("opponent", "opp", "cloq_opponent", "player2", "away_name")) or "")).strip()
    surface = repair_mojibake_text(first(row, ("surface", "surface_raw", "groundType", "court")))
    pick_id = first(row, (
        "thinq_pick_player_id",
        "pick_player_id",
        "player1_id",
        "home_id",
        "home_player_id",
        "thinq_h2h_requested_player1_id",
    ))
    opponent_id = first(row, (
        "thinq_opponent_player_id",
        "opponent_player_id",
        "player2_id",
        "away_id",
        "away_player_id",
        "thinq_h2h_requested_player2_id",
    ))

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


def build_work_queue(outputs_dir: Path, require_elo: bool) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    seen = set()
    work: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    reject_counts: Dict[str, int] = {
        "missing_identity": 0,
        "missing_h2h_key": 0,
        "missing_elo": 0,
        "duplicate": 0,
    }
    elo_key_hits: Dict[str, int] = {}

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
            has_elo, elo_reason = has_elo_pair(row)
            if require_elo and not has_elo:
                reject_counts["missing_elo"] += 1
                continue
            if elo_reason:
                elo_key_hits[elo_reason] = elo_key_hits.get(elo_reason, 0) + 1
            sig = (str(ident["custom_id"]).lower(), ident["pick"].lower(), ident["opponent"].lower())
            if sig in seen:
                reject_counts["duplicate"] += 1
                continue
            seen.add(sig)
            work.append({"row": row, "identity": ident, "source_file": str(path), "elo_reason": elo_reason})

    meta = {
        "source_counts": source_counts,
        "reject_counts": reject_counts,
        "elo_key_hits": elo_key_hits,
    }
    return work, meta



def model_history_status(ctx: Dict[str, Any], status: Any) -> str:
    """Return a stable manifest-level H2H history status."""
    history_status = str(ctx.get("history_status") or "").strip().upper() if isinstance(ctx, dict) else ""
    if history_status:
        return history_status
    if status == "OK":
        return "OK"
    api_error = str(ctx.get("api_error") or "").strip() if isinstance(ctx, dict) else ""
    if api_error:
        return "API_ERROR"
    api_status_code = ctx.get("api_status_code") if isinstance(ctx, dict) else None
    if api_status_code in (204, 404):
        return "API_NO_DATA"
    api_event_count = ctx.get("api_event_count") or ctx.get("h2h_payload_event_count") if isinstance(ctx, dict) else 0
    try:
        if int(api_event_count or 0) > 0:
            return "NO_PREVIOUS_H2H"
    except Exception:
        pass
    return "NO_DATA"


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
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    require_elo = str(args.require_elo).lower() == "true"
    max_requests = max(int(args.max_requests or 0), 0)

    started_at = now_iso()
    ensure_cache_file()
    before_count = cache_pair_count()
    work, meta = build_work_queue(outputs_dir, require_elo=require_elo)

    attempted = 0
    ok = 0
    no_data = 0
    errors = 0
    results: List[Dict[str, Any]] = []
    matchups: Dict[str, Dict[str, Any]] = {}
    history_status_counts: Dict[str, int] = {}

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
            status = ctx.get("status")
            history_status = model_history_status(ctx, status)
            history_status_counts[history_status] = history_status_counts.get(history_status, 0) + 1
            if status == "OK":
                ok += 1
            else:
                no_data += 1
            result = {
                "custom_id": ident["custom_id"],
                "event_id": ident["event_id"],
                "pick": ident["pick"],
                "opponent": ident["opponent"],
                "surface": ident["surface"],
                "status": status,
                "total_matches": ctx.get("total_matches"),
                "same_surface_matches": ctx.get("same_surface_matches"),
                "source": ctx.get("source"),
                "cache_key": ctx.get("cache_key"),
                "api_status_code": ctx.get("api_status_code"),
                "api_error": ctx.get("api_error"),
                "source_file": item.get("source_file"),
                "elo_reason": item.get("elo_reason"),
            }
            results.append(result)
            matchup_key = str(result.get("cache_key") or ("custom:" + str(ident.get("custom_id") or "")))
            matchups[matchup_key] = {
                "h2h_cache_key": matchup_key,
                "custom_id": ident.get("custom_id"),
                "event_id": ident.get("event_id"),
                "h2h_status": status,
                "last_seen_at": finished_at if "finished_at" in locals() else now_iso(),
                "player1_id": ident.get("pick_id"),
                "player1_name": repair_mojibake_text(ident.get("pick")),
                "player2_id": ident.get("opponent_id"),
                "player2_name": repair_mojibake_text(ident.get("opponent")),
                "surface": repair_mojibake_text(ident.get("surface")),
                "source_file": item.get("source_file"),
                "source": ctx.get("source"),
                "endpoint": ctx.get("endpoint"),
                "api_status_code": ctx.get("api_status_code"),
                "api_error": ctx.get("api_error"),
                "total_matches": ctx.get("total_matches"),
                "same_surface_matches": ctx.get("same_surface_matches"),
                "pick_wins": ctx.get("pick_wins"),
                "opponent_wins": ctx.get("opponent_wins"),
                "same_surface_pick_wins": ctx.get("same_surface_pick_wins"),
                "same_surface_opponent_wins": ctx.get("same_surface_opponent_wins"),
                "history_status": history_status,
                "api_event_count": ctx.get("api_event_count") or ctx.get("h2h_payload_event_count"),
                "finished_event_count": ctx.get("finished_event_count"),
                "oriented_finished_event_count": ctx.get("oriented_finished_event_count"),
                "same_surface_finished_event_count": ctx.get("same_surface_finished_event_count"),
                "excluded_event_count": ctx.get("excluded_event_count"),
                "excluded_reasons": repair_mojibake_obj(ctx.get("excluded_reasons")),
                "reason": repair_mojibake_text(ctx.get("reason")),
            }
            print("[h2h] " + json.dumps(result, ensure_ascii=False, sort_keys=True))
        except Exception as exc:
            errors += 1
            history_status_counts["API_ERROR"] = history_status_counts.get("API_ERROR", 0) + 1
            result = {
                "custom_id": ident.get("custom_id"),
                "pick": ident.get("pick"),
                "opponent": ident.get("opponent"),
                "status": "ERROR",
                "error": repair_mojibake_text(str(exc)),
                "source_file": item.get("source_file"),
            }
            results.append(result)
            matchup_key = "custom:" + str(ident.get("custom_id") or "")
            matchups[matchup_key] = {
                "h2h_cache_key": matchup_key,
                "custom_id": ident.get("custom_id"),
                "event_id": ident.get("event_id"),
                "h2h_status": "ERROR",
                "history_status": "API_ERROR",
                "last_seen_at": finished_at if "finished_at" in locals() else now_iso(),
                "player1_id": ident.get("pick_id"),
                "player1_name": repair_mojibake_text(ident.get("pick")),
                "player2_id": ident.get("opponent_id"),
                "player2_name": repair_mojibake_text(ident.get("opponent")),
                "surface": repair_mojibake_text(ident.get("surface")),
                "source_file": item.get("source_file"),
                "error": repair_mojibake_text(str(exc)),
            }
            print("[h2h] ERROR " + json.dumps(result, ensure_ascii=False, sort_keys=True))

    after_count = cache_pair_count()
    finished_at = now_iso()

    if len(work) == 0:
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
        "max_requests": max_requests,
        "candidate_pairs": len(work),
        "attempted": attempted,
        "ok": ok,
        "no_data": no_data,
        "errors": errors,
        "history_status_counts": history_status_counts,
        "pair_count_before": before_count,
        "pair_count_after": after_count,
        "cache_path": str(H2H_CACHE_PATH),
        "manifest_path": str(H2H_MANIFEST_PATH),
        "matchups_path": str(H2H_MATCHUPS_PATH),
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
