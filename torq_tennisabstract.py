from __future__ import annotations

import json
import re
import unicodedata
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

import pandas as pd

CACHE_DIR = Path("data/torq_tennisabstract")
PRIMARY_RAW_DIR = Path("data/torq_tennisabstract/raw")
LEGACY_RAW_DIR = Path("data/elo/raw")
USER_AGENT = "Mozilla/5.0 (compatible; tbt-pro-torq/1.8; +https://github.com/BackstageTalks/tbt-pro)"

URLS = {
    "atp_elo": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta_elo": "https://tennisabstract.com/reports/wta_elo_ratings.html",
    "atp_yelo": "https://tennisabstract.com/reports/atp_season_yelo_ratings.html",
    "wta_yelo": "https://tennisabstract.com/reports/wta_season_yelo_ratings.html",
}

RAW_FILENAMES = {
    "atp_elo": "atp_elo.html",
    "wta_elo": "wta_elo.html",
    "atp_yelo": "atp_yelo.html",
    "wta_yelo": "wta_yelo.html",
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
    parts = base.split()
    variants = [base]
    if len(parts) >= 2:
        variants.extend([
            " ".join(parts[::-1]),
            parts[-1],
            parts[0] + " " + parts[-1],
            parts[-1] + " " + parts[0],
        ])
    return [v for v in dict.fromkeys(variants) if v]


def _float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _valid_ta_html(text: str) -> bool:
    lower = text.lower()
    if "challenge-platform" in lower or "/cdn-cgi/challenge-platform" in lower or "window._cf_chl" in lower:
        return False
    return "tennis abstract" in lower and "player" in lower and "elo" in lower


def _read_raw_html(name: str) -> Optional[str]:
    filename = RAW_FILENAMES[name]
    candidate_paths = [PRIMARY_RAW_DIR / filename, LEGACY_RAW_DIR / filename, CACHE_DIR / f"{name}.html"]
    for path in candidate_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if _valid_ta_html(text):
            print("TA HTML SOURCE", name, "file", path, "bytes", len(text.encode("utf-8", errors="replace")))
            return text
        print("TA HTML SKIP", name, "invalid_or_challenge", path)
    return None


def _download_html(name: str) -> str:
    cached_or_raw = _read_raw_html(name)
    if cached_or_raw:
        return cached_or_raw

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request = Request(
        URLS[name],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=45) as response:
        raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    if not _valid_ta_html(text):
        # Do not cache Cloudflare/error pages as source data.
        rejected = CACHE_DIR / f"{name}.rejected.html"
        rejected.write_text(text[:5000], encoding="utf-8")
        print("TA HTML LIVE INVALID", name, "saved", rejected)
        return ""
    (CACHE_DIR / f"{name}.html").write_text(text, encoding="utf-8")
    print("TA HTML SOURCE", name, "live", URLS[name], "bytes", len(text.encode("utf-8", errors="replace")))
    return text


def _read_tables(name: str) -> list[pd.DataFrame]:
    html = _download_html(name)
    if not html:
        return []
    return pd.read_html(StringIO(html))


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = []
    for col in df.columns:
        if isinstance(col, tuple):
            text = " ".join(str(part) for part in col if str(part) != "nan")
        else:
            text = str(col)
        cols.append(text.strip())
    df.columns = cols
    return df


def _find_player_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        low = str(col).lower().strip()
        if low == "player" or low.endswith(" player") or "player" in low:
            return col
    return None


def _find_rating_column(df: pd.DataFrame, rating_type: str) -> Optional[str]:
    desired = rating_type.lower()
    for col in df.columns:
        low = str(col).lower().strip()
        if low == desired or desired in low:
            return col
    for col in df.columns:
        low = str(col).lower().strip()
        if "elo" in low and "rank" not in low:
            return col
    return None


def _clean_table(df: pd.DataFrame, rating_type: str) -> Dict[str, Dict[str, Any]]:
    df = _flatten_columns(df)
    player_col = _find_player_column(df)
    rating_col = _find_rating_column(df, rating_type)
    if not player_col or not rating_col:
        print("TA TABLE SKIP", rating_type, "columns", list(df.columns)[:12])
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        player = row.get(player_col)
        rating = _float(row.get(rating_col))
        if not player or rating is None:
            continue
        rec = {"player": str(player), rating_type: rating}
        for variant in name_variants(player):
            out[variant] = rec
    return out


def fetch_snapshot(force: bool = False) -> Dict[str, Dict[str, Dict[str, Any]]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "snapshot.json"
    if cache_path.exists() and not force:
        try:
            snapshot = json.loads(cache_path.read_text(encoding="utf-8"))
            if any(len(v) > 0 for v in snapshot.values()):
                return snapshot
        except Exception:
            pass

    snapshot: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for name in URLS:
        rating_type = "yelo" if "yelo" in name else "elo"
        try:
            tables = _read_tables(name)
            print("TA TABLES", name, "count", len(tables))
            best: Dict[str, Dict[str, Any]] = {}
            for table in tables:
                cleaned = _clean_table(table, rating_type)
                if len(cleaned) > len(best):
                    best = cleaned
            snapshot[name] = best
            sample = list(best.values())[:3]
            print("TA SNAPSHOT", name, "players", len(best), "sample", sample)
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
    best_record: Dict[str, Any] = {}

    for candidate_key, record in mapping.items():
        c_tokens = set(candidate_key.split())
        c_last = candidate_key.split()[-1] if candidate_key.split() else ""
        if q_last and c_last and q_last != c_last:
            continue
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), len(c_tokens), 1)
        if overlap > best_score:
            best_score = overlap
            best_record = record
    return best_record if best_score >= 0.55 else {}


def _tour_order(tour: Optional[str]) -> list[str]:
    text = str(tour or "").upper()
    if text == "WTA":
        return ["wta", "atp"]
    if text == "ATP":
        return ["atp", "wta"]
    return ["wta", "atp"]


def lookup_rating(snapshot: Dict[str, Dict[str, Dict[str, Any]]], player: str, tour: Optional[str], surface: str = "Hard") -> Dict[str, Any]:
    best_long: Dict[str, Any] = {}
    best_short: Dict[str, Any] = {}
    used_tour_long = None
    used_tour_short = None
    for tour_key in _tour_order(tour):
        if not best_long:
            found = _best_match(player, snapshot.get(f"{tour_key}_elo", {}))
            if found:
                best_long = found
                used_tour_long = tour_key.upper()
        if not best_short:
            found = _best_match(player, snapshot.get(f"{tour_key}_yelo", {}))
            if found:
                best_short = found
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
