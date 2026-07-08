from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

CACHE_DIR = Path("data/torq_tennisabstract")
RAW_DIR = Path("data/elo/raw")

URLS = {
    "atp_elo": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta_elo": "https://tennisabstract.com/reports/wta_elo_ratings.html",
    "atp_yelo": "https://tennisabstract.com/reports/atp_season_yelo_ratings.html",
    "wta_yelo": "https://tennisabstract.com/reports/wta_season_yelo_ratings.html",
}

LOCAL_FILES = {
    "atp_elo": RAW_DIR / "atp_elo.html",
    "wta_elo": RAW_DIR / "wta_elo.html",
    "atp_yelo": RAW_DIR / "atp_yelo.html",
    "wta_yelo": RAW_DIR / "wta_yelo.html",
}


def normalize_name(value: Any) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("-", " ").replace(".", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_variants(value: Any) -> list[str]:
    base = normalize_name(value)
    variants = [base]
    parts = base.split()
    if len(parts) >= 2:
        variants.append(" ".join(parts[::-1]))
        variants.append(parts[-1])
        variants.append(parts[0] + " " + parts[-1])
    return [v for v in dict.fromkeys(variants) if v]


def _float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = []
    for col in df.columns:
        if isinstance(col, tuple):
            text = " ".join(str(x) for x in col if str(x) != "nan")
        else:
            text = str(col)
        cols.append(text.strip())
    df.columns = cols
    return df


def _find_col(df: pd.DataFrame, exact: set[str], contains: list[str]) -> Optional[str]:
    for col in df.columns:
        low = str(col).lower().strip()
        if low in exact:
            return col
    for col in df.columns:
        low = str(col).lower().strip()
        if any(token in low for token in contains):
            return col
    return None


def _clean_table(df: pd.DataFrame, rating_type: str) -> Dict[str, Dict[str, Any]]:
    df = _flatten_columns(df)
    player_col = _find_col(df, {"player", "name"}, ["player"])
    rating_col = _find_col(df, {rating_type, rating_type.lower()}, [rating_type.lower()])
    if rating_col is None:
        rating_col = _find_col(df, {"elo", "yelo"}, ["elo"])
    if not player_col or not rating_col:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        player = row.get(player_col)
        rating = _float(row.get(rating_col))
        if not player or rating is None:
            continue
        rec = {"player": str(player), rating_type: rating}
        for key in name_variants(player):
            out[key] = rec
    return out


def _read_tables(name: str) -> list[pd.DataFrame]:
    local = LOCAL_FILES.get(name)
    if local and local.exists():
        try:
            return pd.read_html(str(local))
        except Exception as exc:
            print("TA LOCAL READ ERROR", name, exc)
    return pd.read_html(URLS[name])


def fetch_snapshot(force: bool = False) -> Dict[str, Dict[str, Dict[str, Any]]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "snapshot.json"
    if cache_path.exists() and not force:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    snapshot: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for name in URLS:
        rating_type = "yelo" if "yelo" in name else "elo"
        try:
            tables = _read_tables(name)
            target = None
            for table in tables:
                candidate = _flatten_columns(table)
                cols = [str(c).lower() for c in candidate.columns]
                has_player = any(c == "player" or "player" in c for c in cols)
                has_elo = any("elo" in c for c in cols)
                if has_player and has_elo:
                    target = candidate
                    break
            snapshot[name] = _clean_table(target, rating_type) if target is not None else {}
            print("TA SNAPSHOT", name, "players", len(snapshot[name]))
        except Exception as exc:
            print("TA SNAPSHOT ERROR", name, exc)
            snapshot[name] = {}

    cache_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def _best_match(player: str, mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    for variant in name_variants(player):
        if variant in mapping:
            return mapping[variant]

    query = normalize_name(player)
    q_tokens = set(query.split())
    q_last = query.split()[-1] if query.split() else ""
    best_score = 0.0
    best_rec: Dict[str, Any] = {}

    for key, rec in mapping.items():
        k_tokens = set(key.split())
        k_last = key.split()[-1] if key.split() else ""
        if q_last and k_last and q_last != k_last:
            continue
        score = len(q_tokens & k_tokens) / max(len(q_tokens), len(k_tokens), 1)
        if score > best_score:
            best_score = score
            best_rec = rec

    return best_rec if best_score >= 0.55 else {}


def _tour_order(tour: Optional[str]) -> list[str]:
    text = str(tour or "").upper()
    if text == "WTA":
        return ["wta", "atp"]
    if text == "ATP":
        return ["atp", "wta"]
    # Critical fallback: TennisApi category/gender is often missing or generic.
    # Try WTA first because many displayed misses are WTA singles, then ATP.
    return ["wta", "atp"]


def lookup_rating(snapshot: Dict[str, Dict[str, Dict[str, Any]]], player: str, tour: Optional[str], surface: str = "Hard") -> Dict[str, Any]:
    best_long: Dict[str, Any] = {}
    best_short: Dict[str, Any] = {}
    used_tour_long = None
    used_tour_short = None

    for tour_key in _tour_order(tour):
        if not best_long:
            candidate = _best_match(player, snapshot.get(f"{tour_key}_elo", {}))
            if candidate:
                best_long = candidate
                used_tour_long = tour_key.upper()
        if not best_short:
            candidate = _best_match(player, snapshot.get(f"{tour_key}_yelo", {}))
            if candidate:
                best_short = candidate
                used_tour_short = tour_key.upper()
        if best_long and best_short:
            break

    long_elo = _float(best_long.get("elo")) if best_long else None
    short_elo = _float(best_short.get("yelo")) if best_short else None

    return {
        "found_long": long_elo is not None,
        "found_short": short_elo is not None,
        "long_elo": long_elo,
        "short_elo": short_elo,
        "matched_long": best_long.get("player") if best_long else None,
        "matched_short": best_short.get("player") if best_short else None,
        "tour_long": used_tour_long,
        "tour_short": used_tour_short,
    }


def elo_probability(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return 1.0 / (1.0 + 10.0 ** ((b - a) / 400.0))
