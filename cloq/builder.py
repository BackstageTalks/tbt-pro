#!/usr/bin/env python3
"""CloQ v1 close-odds selector from ALL.

CloQ is intentionally not a standalone model. It reads finished ALL rows with
CorQ/ThinQ fields and selects close-odds candidates.

Rules:
- source = outputs/latest_all.json
- close odds gap <= 10%
- pick odds > 1.70
- notstarted/open/scheduled/prematch/upcoming only
- valid side orientation
- CorQ >= 50%
- Pick ThinQ Edge >= 0
- Stat Data Depth >= 40%
- Form Data Depth >= 40%
- max one pick per match
- no limit on number of CloQ rows
"""
from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

BRATISLAVA_TZ = "Europe/Bratislava"
CLOQ_MAX_ODDS_GAP_PCT = 0.10
CLOQ_MIN_PICK_ODDS = 1.70
CLOQ_MIN_CORQ_PROB = 0.50
CLOQ_MIN_PICK_THINQ_EDGE = 0.0
CLOQ_MIN_STAT_DATA_DEPTH = 0.40
CLOQ_MIN_FORM_DATA_DEPTH = 0.40
PREMATCH_STATUSES = {"notstarted", "scheduled", "open", "prematch", "upcoming"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_today() -> str:
    dt = datetime.now(timezone.utc)
    if ZoneInfo is not None:
        dt = dt.astimezone(ZoneInfo(BRATISLAVA_TZ))
    return dt.date().isoformat()


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except Exception:
        return default


def as_prob(value: Any, default: float = 0.0) -> float:
    x = as_float(value, None)
    if x is None:
        return default
    if x > 1.0:
        x = x / 100.0
    return max(0.0, min(float(x), 1.0))


def get_nested(row: Dict[str, Any], *keys: str) -> Any:
    cur: Any = row
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def first(row: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def load_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "all", "items", "matches", "predictions", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def status_type(row: Dict[str, Any]) -> str:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    st = row.get("status_type") or get_nested(row, "status", "type") or get_nested(raw, "status", "type")
    return str(st or "").strip().lower()


def is_notstarted(row: Dict[str, Any]) -> bool:
    return status_type(row) in PREMATCH_STATUSES


def is_doubles(row: Dict[str, Any]) -> bool:
    for key in ("is_doubles", "doubles"):
        if bool(row.get(key)):
            return True
    category = str(row.get("category") or row.get("event_type") or row.get("match_type") or "").lower()
    return "double" in category or "doubles" in category


def side_valid(row: Dict[str, Any]) -> bool:
    audit = row.get("side_audit")
    if isinstance(audit, dict) and audit.get("side_valid") is False:
        return False
    if row.get("side_valid") is False:
        return False
    return True


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    value = first(row, ["pick_odds", "odds", "price", "decimal_odds"], None)
    x = as_float(value, None)
    if x is not None:
        return x
    side = str(row.get("pick_side") or row.get("side") or "").upper()
    if side in ("HOME", "PLAYER1", "P1"):
        return as_float(first(row, ["odds_player1", "home_odds", "p1_odds", "price1"], None), None)
    if side in ("AWAY", "PLAYER2", "P2"):
        return as_float(first(row, ["odds_player2", "away_odds", "p2_odds", "price2"], None), None)
    return as_float(first(row, ["odds_player1", "home_odds", "p1_odds", "price1"], None), None)


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    value = first(row, ["opponent_odds", "opp_odds"], None)
    x = as_float(value, None)
    if x is not None:
        return x
    side = str(row.get("pick_side") or row.get("side") or "").upper()
    if side in ("HOME", "PLAYER1", "P1"):
        return as_float(first(row, ["odds_player2", "away_odds", "p2_odds", "price2"], None), None)
    if side in ("AWAY", "PLAYER2", "P2"):
        return as_float(first(row, ["odds_player1", "home_odds", "p1_odds", "price1"], None), None)
    return as_float(first(row, ["odds_player2", "away_odds", "p2_odds", "price2"], None), None)


def odds_gap_pct(row: Dict[str, Any]) -> Optional[float]:
    existing = as_float(row.get("odds_gap_pct"), None)
    if existing is not None:
        if existing > 1.0:
            existing = existing / 100.0
        return max(0.0, existing)
    a = pick_odds(row)
    b = opponent_odds(row)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return abs(a - b) / min(a, b)


def corq_probability(row: Dict[str, Any]) -> float:
    for key in (
        "corq_estimated_win_probability",
        "corq_probability",
        "estimated_win_probability",
        "estimated_win_pct",
        "win_probability",
        "probability",
    ):
        if key in row and row.get(key) not in (None, ""):
            return as_prob(row.get(key), 0.0)
    return 0.0


def pick_thinq_edge(row: Dict[str, Any]) -> float:
    for key in ("pick_thinq_edge", "thinq_edge", "thinq_probability_edge"):
        if key in row and row.get(key) not in (None, ""):
            x = as_float(row.get(key), 0.0) or 0.0
            if abs(x) > 1.0:
                x = x / 100.0
            return float(x)
    layer = row.get("thinq_probability_layer")
    if isinstance(layer, dict):
        x = as_float(layer.get("edge"), 0.0) or 0.0
        if abs(x) > 1.0:
            x = x / 100.0
        return float(x)
    p = as_prob(first(row, ["thinq_probability", "thinq_winner_probability"], 0.5), 0.5)
    return p - 0.5


def stat_data_depth(row: Dict[str, Any]) -> float:
    for key in ("stat_data_depth", "pick_data_depth", "data_depth"):
        if key in row and row.get(key) not in (None, ""):
            return as_prob(row.get(key), 0.0)
    conf = as_prob(first(row, ["thinq_confidence", "thinq_probability_confidence"], 0.0), 0.0)
    edge = max(0.0, pick_thinq_edge(row))
    return max(0.0, min(conf * min(edge / 0.10, 1.0), 1.0))


def form_data_depth(row: Dict[str, Any]) -> float:
    for key in ("form_data_depth", "form_confidence", "thinq_form_confidence"):
        if key in row and row.get(key) not in (None, ""):
            return as_prob(row.get(key), 0.0)
    rf = get_nested(row, "thinq", "recent_form")
    if isinstance(rf, dict):
        for key in ("form_data_depth", "form_confidence"):
            if rf.get(key) not in (None, ""):
                return as_prob(rf.get(key), 0.0)
    return 0.0


def match_key(row: Dict[str, Any]) -> str:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for key in ("event_id", "match_id", "custom_id", "customId"):
        value = row.get(key) or raw.get(key)
        if value not in (None, ""):
            return str(value)
    p1 = str(row.get("player1") or row.get("home_name") or row.get("home") or "").strip().lower()
    p2 = str(row.get("player2") or row.get("away_name") or row.get("away") or "").strip().lower()
    return "|".join(sorted([p1, p2]))


def reject_reasons(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    po = pick_odds(row)
    oo = opponent_odds(row)
    gap = odds_gap_pct(row)
    cp = corq_probability(row)
    te = pick_thinq_edge(row)
    sd = stat_data_depth(row)
    fd = form_data_depth(row)

    if not is_notstarted(row):
        reasons.append("REJECT_CLOQ_STATUS_NOT_NOTSTARTED")
    if is_doubles(row):
        reasons.append("REJECT_CLOQ_DOUBLES")
    if not side_valid(row):
        reasons.append("REJECT_CLOQ_INVALID_SIDE_ORIENTATION")
    if po is None or oo is None:
        reasons.append("REJECT_CLOQ_MISSING_ODDS")
    else:
        if po <= CLOQ_MIN_PICK_ODDS:
            reasons.append("REJECT_CLOQ_PICK_ODDS_NOT_ABOVE_1_70")
    if gap is None:
        reasons.append("REJECT_CLOQ_MISSING_ODDS_GAP")
    elif gap > CLOQ_MAX_ODDS_GAP_PCT:
        reasons.append("REJECT_CLOQ_ODDS_GAP_ABOVE_10")
    if cp < CLOQ_MIN_CORQ_PROB:
        reasons.append("REJECT_CLOQ_CORQ_BELOW_50")
    if te < CLOQ_MIN_PICK_THINQ_EDGE:
        reasons.append("REJECT_CLOQ_PICK_THINQ_EDGE_AGAINST")
    if sd < CLOQ_MIN_STAT_DATA_DEPTH:
        reasons.append("REJECT_CLOQ_LOW_STAT_DATA_DEPTH")
    if fd < CLOQ_MIN_FORM_DATA_DEPTH:
        reasons.append("REJECT_CLOQ_LOW_FORM_DATA_DEPTH")
    return reasons


def sort_key(row: Dict[str, Any]) -> Tuple[float, float, float, float, float]:
    return (
        corq_probability(row),
        stat_data_depth(row),
        pick_thinq_edge(row),
        form_data_depth(row),
        pick_odds(row) or 0.0,
    )


def build_cloq(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for source in rows:
        row = deepcopy(source)
        reasons = reject_reasons(row)
        row["cloq_candidate"] = not reasons
        row["cloq_status"] = "OK" if not reasons else "REJECTED"
        row["cloq_reject_reasons"] = reasons
        row["cloq_odds_gap_pct"] = odds_gap_pct(row)
        row["cloq_pick_odds"] = pick_odds(row)
        row["cloq_opponent_odds"] = opponent_odds(row)
        row["cloq_corq_probability"] = round(corq_probability(row), 6)
        row["cloq_pick_thinq_edge"] = round(pick_thinq_edge(row), 6)
        row["cloq_stat_data_depth"] = round(stat_data_depth(row), 6)
        row["cloq_form_data_depth"] = round(form_data_depth(row), 6)
        row["cloq_source"] = "ALL"
        if not reasons:
            candidates.append(row)

    best_by_match: Dict[str, Dict[str, Any]] = {}
    for row in candidates:
        key = match_key(row)
        current = best_by_match.get(key)
        if current is None or sort_key(row) > sort_key(current):
            best_by_match[key] = row

    selected = sorted(best_by_match.values(), key=sort_key, reverse=True)
    for idx, row in enumerate(selected, start=1):
        row["cloq_rank"] = idx
    return selected


def write_outputs(rows: List[Dict[str, Any]], output_root: Path, date_str: Optional[str] = None) -> Dict[str, Any]:
    date_str = date_str or local_today()
    year = date_str[:4]
    out_dir = output_root / "cloq" / year
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": now_utc_iso(),
        "date": date_str,
        "source": "outputs/latest_all.json",
        "model": "CloQ v1 close odds selector from ALL",
        "rules": {
            "odds_gap_pct_max": CLOQ_MAX_ODDS_GAP_PCT,
            "pick_odds_min_exclusive": CLOQ_MIN_PICK_ODDS,
            "corq_probability_min": CLOQ_MIN_CORQ_PROB,
            "pick_thinq_edge_min": CLOQ_MIN_PICK_THINQ_EDGE,
            "stat_data_depth_min": CLOQ_MIN_STAT_DATA_DEPTH,
            "form_data_depth_min": CLOQ_MIN_FORM_DATA_DEPTH,
            "limit": None,
            "max_one_pick_per_match": True,
        },
        "count": len(rows),
        "rows": rows,
    }

    snapshot = out_dir / f"cloq_{date_str}.json"
    latest = output_root / "latest_cloq.json"
    snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build CloQ close-odds selector from outputs/latest_all.json")
    parser.add_argument("--input", default="outputs/latest_all.json")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--date", default=None)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    rows = load_rows(input_path)
    selected = build_cloq(rows)
    payload = write_outputs(selected, Path(args.output_root), args.date)
    print(f"CloQ build finished: source_rows={len(rows)} cloq={payload['count']} latest={Path(args.output_root) / 'latest_cloq.json'}")
    if args.print_summary:
        for row in selected:
            print(f"#{row.get('cloq_rank')} {row.get('pick') or row.get('player')} @ {row.get('cloq_pick_odds')} gap={row.get('cloq_odds_gap_pct')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
