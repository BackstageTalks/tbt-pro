from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
CACHE_DIR = Path("data/torq_tennisabstract")
URLS = {
    "atp_elo": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta_elo": "https://tennisabstract.com/reports/wta_elo_ratings.html",
    "atp_yelo": "https://tennisabstract.com/reports/atp_season_yelo_ratings.html",
    "wta_yelo": "https://tennisabstract.com/reports/wta_season_yelo_ratings.html",
}
def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s']", " ", text.lower().replace("-", " ").replace(".", " ").replace(",", " "))
    return re.sub(r"\s+", " ", text).strip()
def _float(v):
    try: return float(v) if v not in (None, "") else None
    except Exception: return None
def _clean(df, rating_type):
    df = df.copy(); df.columns = [str(c).strip() for c in df.columns]
    pc = next((c for c in df.columns if c.lower() == "player"), None)
    rc = next((c for c in df.columns if c.lower() in {"elo", "yelo"}), None) or next((c for c in df.columns if "elo" in c.lower()), None)
    if not pc or not rc: return {}
    out = {}
    for _, row in df.iterrows():
        key = normalize_name(row.get(pc)); rating = _float(row.get(rc))
        if key and rating: out[key] = {"player": str(row.get(pc)), rating_type: rating}
    return out
def fetch_snapshot(force=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True); cache = CACHE_DIR / "snapshot.json"
    if cache.exists() and not force:
        try: return json.loads(cache.read_text(encoding="utf-8"))
        except Exception: pass
    snap = {}
    for name, url in URLS.items():
        try:
            tables = pd.read_html(url); target = None
            for table in tables:
                cols = [str(c) for c in table.columns]
                if "Player" in cols and any("Elo" in c or "yElo" in c for c in cols): target = table; break
            snap[name] = _clean(target, "yelo" if "yelo" in name else "elo") if target is not None else {}
        except Exception as exc:
            print("TA SNAPSHOT ERROR", name, exc); snap[name] = {}
    cache.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap
def _best(key, mapping):
    if key in mapping: return mapping[key]
    toks = set(key.split()); last = key.split()[-1] if key.split() else ""; best = {}; score = 0
    for ck, rec in mapping.items():
        ct = set(ck.split()); cl = ck.split()[-1] if ck.split() else ""
        if last != cl: continue
        s = len(toks & ct) / max(len(toks), len(ct), 1)
        if s > score: score = s; best = rec
    return best if score >= 0.60 else {}
def lookup_rating(snapshot, player, tour, surface="Hard"):
    tk = "wta" if str(tour or "").upper() == "WTA" else "atp"; key = normalize_name(player)
    er = _best(key, snapshot.get(f"{tk}_elo", {})); yr = _best(key, snapshot.get(f"{tk}_yelo", {}))
    return {"long_elo": _float(er.get("elo")) if er else None, "short_elo": _float(yr.get("yelo")) if yr else None, "matched_long": er.get("player") if er else None, "matched_short": yr.get("player") if yr else None}
def elo_probability(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None: return None
    return 1 / (1 + 10 ** ((b - a) / 400))
