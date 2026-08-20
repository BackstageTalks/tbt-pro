from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from corq.corq_rapidapi_client import (
    RapidApiClient,
    event_players,
    extract_markets,
    fetch_daily_matches_with_odds,
    market_choices,
    choice_name,
    choice_price,
    normalize_name,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "lucq"
SNAPSHOT_DIR = OUTPUT_DIR / "snapshots"
LOCAL_TZ = ZoneInfo("Europe/Bratislava")
MODEL_VERSION = "LUCQ_API_PRO_V1"
MIN_SAMPLE = int(os.getenv("LUCQ_MIN_SAMPLE", "3") or "3")
TOP_LIMIT = int(os.getenv("LUCQ_TOP_LIMIT", "10") or "10")


def as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def betting_day(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(LOCAL_TZ)
    if now.hour < 6:
        now -= timedelta(days=1)
    return now.date().isoformat()


def tour_type(match: Dict[str, Any]) -> Optional[str]:
    text = normalize_name(" ".join(str(match.get(k) or "") for k in ("category", "level", "gender", "tournament")))
    if "wta" in text or "women" in text:
        return "wta"
    if "atp" in text or "men" in text or "challenger" in text:
        return "atp"
    return None


def poisson_cdf(k: int, mean: float) -> float:
    if mean <= 0:
        return 1.0
    term = math.exp(-mean)
    total = term
    for i in range(1, max(0, k) + 1):
        term *= mean / i
        total += term
    return max(0.0, min(1.0, total))


def selection_probability(mean: float, line: float, side: str) -> Optional[float]:
    if mean < 0 or line < 0:
        return None
    side = side.upper()
    floor_line = math.floor(line)
    if side == "OVER":
        return 1.0 - poisson_cdf(floor_line, mean)
    if side == "UNDER":
        return poisson_cdf(math.ceil(line) - 1, mean)
    return None


def market_text(market: Dict[str, Any]) -> str:
    return normalize_name(" ".join(str(market.get(k) or "") for k in ("marketName", "market_name", "name", "label", "type", "groupName")))


def line_from_choice(choice: Dict[str, Any], text: str) -> Optional[float]:
    for key in ("line", "handicap", "total", "points", "valueLine", "spread"):
        value = as_float(choice.get(key))
        if value is not None:
            return value
    match = re.search(r"(?<!\d)(\d{1,2}(?:[.,]\d+)?)", text)
    return as_float(match.group(1)) if match else None


def side_from_text(text: str) -> Optional[str]:
    norm = normalize_name(text)
    if re.search(r"\bover\b", norm) or re.search(r"\bo\s*\d", norm):
        return "OVER"
    if re.search(r"\bunder\b", norm) or re.search(r"\bu\s*\d", norm):
        return "UNDER"
    return None


def player_for_market(text: str, player1: str, player2: str) -> Optional[str]:
    p1 = normalize_name(player1)
    p2 = normalize_name(player2)
    if p1 and (p1 in text or (p1.split()[-1] in text if p1.split() else False)):
        return player1
    if p2 and (p2 in text or (p2.split()[-1] in text if p2.split() else False)):
        return player2
    return None


def classify_market(text: str, player: Optional[str]) -> Optional[str]:
    if "double fault" in text or "double faults" in text:
        return "PLAYER_DF" if player else "TOTAL_DF"
    if "ace" in text or "aces" in text:
        return "PLAYER_ACES" if player else "TOTAL_ACES"
    return None


def projections(stats: Dict[str, Any]) -> Dict[str, Optional[float]]:
    p1_aces = as_float(stats.get("player1_aces_per_match"))
    p2_aces = as_float(stats.get("player2_aces_per_match"))
    p1_df = as_float(stats.get("player1_double_faults_per_match"))
    p2_df = as_float(stats.get("player2_double_faults_per_match"))
    return {
        "PLAYER1_ACES": p1_aces,
        "PLAYER2_ACES": p2_aces,
        "TOTAL_ACES": (p1_aces + p2_aces) if p1_aces is not None and p2_aces is not None else None,
        "PLAYER1_DF": p1_df,
        "PLAYER2_DF": p2_df,
        "TOTAL_DF": (p1_df + p2_df) if p1_df is not None and p2_df is not None else None,
    }


def projection_for(market: str, player: Optional[str], player1: str, values: Dict[str, Optional[float]]) -> Optional[float]:
    if market == "TOTAL_ACES":
        return values["TOTAL_ACES"]
    if market == "TOTAL_DF":
        return values["TOTAL_DF"]
    side = "PLAYER1" if normalize_name(player) == normalize_name(player1) else "PLAYER2"
    suffix = "ACES" if market == "PLAYER_ACES" else "DF"
    return values.get(f"{side}_{suffix}")


def confidence(stats: Dict[str, Any], projection: Optional[float]) -> float:
    sample = as_float(stats.get("api_h2h_matches_count")) or 0.0
    p1_n = as_float(stats.get("player1_stat_matches_played")) or sample
    p2_n = as_float(stats.get("player2_stat_matches_played")) or sample
    depth = min(max(p1_n, p2_n), 20.0) / 20.0
    completeness = 1.0 if projection is not None else 0.0
    return round(0.75 * depth + 0.25 * completeness, 4)


def raw_prop_payload(client: RapidApiClient, event_id: Any) -> Tuple[Any, Optional[str]]:
    providers = [int(x) for x in os.getenv("TENNISAPI_ODDS_PROVIDER_IDS", "1").split(",") if x.strip().isdigit()]
    for provider in providers or [1]:
        path = f"/api/tennis/event/{event_id}/odds/{provider}/all"
        payload = client.get(path)
        if payload:
            return payload, path
    return None, None


def build_rows(match: Dict[str, Any], stats: Dict[str, Any], odds_payload: Any, odds_path: Optional[str], day: str) -> List[Dict[str, Any]]:
    player1 = str(match.get("player1") or "").strip()
    player2 = str(match.get("player2") or "").strip()
    values = projections(stats)
    rows: List[Dict[str, Any]] = []
    seen = set()
    for market in extract_markets(odds_payload):
        mtext = market_text(market)
        if not any(token in mtext for token in ("ace", "double fault")):
            continue
        for choice in market_choices(market):
            ctext_raw = " ".join(str(choice.get(k) or "") for k in ("name", "label", "choiceName", "participantName"))
            all_text = normalize_name(f"{mtext} {ctext_raw}")
            side = side_from_text(all_text)
            line = line_from_choice(choice, ctext_raw) or line_from_choice(market, mtext)
            player = player_for_market(all_text, player1, player2)
            kind = classify_market(all_text, player)
            if not side or line is None or not kind:
                continue
            projection = projection_for(kind, player, player1, values)
            probability = selection_probability(projection, line, side) if projection is not None else None
            sample = int(as_float(stats.get("api_h2h_matches_count")) or 0)
            data_confidence = confidence(stats, projection)
            status = "OK" if probability is not None and sample >= MIN_SAMPLE else "INSUFFICIENT_DATA"
            subject = player if player else f"{player1} - {player2}"
            key = (str(match.get("event_id")), kind, normalize_name(subject), side, line)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "model": "lucq",
                "model_version": MODEL_VERSION,
                "betting_day": day,
                "generated_at": datetime.now(LOCAL_TZ).isoformat(),
                "event_id": match.get("event_id") or match.get("match_id"),
                "player1": player1,
                "player2": player2,
                "subject": subject,
                "market": kind,
                "selection": f"{side.title()} {line:g} {'Aces' if 'ACES' in kind else 'DF'}",
                "side": side,
                "line": line,
                "market_odds": choice_price(choice),
                "projection": round(projection, 3) if projection is not None else None,
                "lucq_probability": round(probability, 4) if probability is not None else None,
                "lucq_data_confidence": data_confidence,
                "sample_size": sample,
                "surface": match.get("surface"),
                "tournament": match.get("tournament"),
                "category": match.get("category"),
                "start_time": match.get("start_time") or match.get("match_start"),
                "status": status,
                "result_status": "PENDING",
                "data_source": "API_PRO_H2H_STATS",
                "market_source": "API_PRO_EXACT_EVENT_ODDS_ALL",
                "market_source_path": odds_path,
                "api_stats_status": stats.get("api_serve_stats_status"),
            })
    return rows


def sort_key(row: Dict[str, Any]) -> Tuple[float, float, int, str]:
    return (
        -(as_float(row.get("lucq_probability")) or -1.0),
        -(as_float(row.get("lucq_data_confidence")) or 0.0),
        -int(as_float(row.get("sample_size")) or 0),
        str(row.get("start_time") or ""),
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run(target: Optional[str] = None) -> Dict[str, Any]:
    os.environ.setdefault("TENNISAPI_H2H_STATS_ENABLED", "1")
    os.environ.setdefault("TENNISAPI_H2H_NAME_FALLBACK_ENABLED", "1")
    target_dt = datetime.fromisoformat(target).replace(tzinfo=LOCAL_TZ) if target else None
    day = target or betting_day()
    client = RapidApiClient()
    matches = fetch_daily_matches_with_odds(target_dt)
    rows: List[Dict[str, Any]] = []
    diagnostics = {"matches": len(matches), "singles": 0, "with_h2h_stats": 0, "with_prop_markets": 0}
    for match in matches:
        if match.get("is_doubles"):
            continue
        player1, player2 = event_players(match)
        player1 = player1 or match.get("player1")
        player2 = player2 or match.get("player2")
        if not player1 or not player2:
            continue
        diagnostics["singles"] += 1
        tour = tour_type(match)
        if not tour:
            continue
        stats = client.get_h2h_stats_by_names(tour, str(player1), str(player2), surface=match.get("surface"))
        if stats.get("api_serve_stats_status") == "OK":
            diagnostics["with_h2h_stats"] += 1
        event_id = match.get("event_id") or match.get("match_id") or match.get("id")
        payload, path = raw_prop_payload(client, event_id)
        event_rows = build_rows(match, stats, payload, path, day) if payload else []
        if event_rows:
            diagnostics["with_prop_markets"] += 1
            rows.extend(event_rows)
    rows.sort(key=sort_key)
    eligible = [row for row in rows if row.get("status") == "OK" and row.get("lucq_probability") is not None]
    top10 = eligible[:TOP_LIMIT]
    top_keys = {(r["event_id"], r["market"], r["subject"], r["selection"]) for r in top10}
    for row in rows:
        row["lucq_top10"] = (row["event_id"], row["market"], row["subject"], row["selection"]) in top_keys
        row["lucq_rank"] = next((i for i, x in enumerate(top10, 1) if x is row), None)
    manifest = {
        "model": "lucq",
        "model_version": MODEL_VERSION,
        "betting_day": day,
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "rows": len(rows),
        "eligible": len(eligible),
        "top10": len(top10),
        "diagnostics": diagnostics,
        "independent_from": ["CorQ", "ThinQ", "CloQ", "MarQ", "ELO"],
    }
    write_json(OUTPUT_DIR / "latest.json", rows)
    write_json(OUTPUT_DIR / "latest_top10.json", top10)
    snapshot_path = SNAPSHOT_DIR / f"lucq_{day}.json"
    if not snapshot_path.exists() or os.getenv("LUCQ_OVERWRITE_SNAPSHOT", "0").lower() in {"1", "true", "yes"}:
        write_json(snapshot_path, top10)
    write_json(OUTPUT_DIR / "latest_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build API PRO-only LucQ predictions")
    parser.add_argument("--date", default=os.getenv("LUCQ_BETTING_DAY", ""))
    args = parser.parse_args()
    run(args.date or None)


if __name__ == "__main__":
    main()
