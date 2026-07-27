from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
WEB_DIR = ROOT / "corq" / "web"
SITE_DIR = ROOT / "corq" / "site"
ASSET_SRC = WEB_DIR / "assets" / "tbt_ai_goat_icon.png"
ASSET_DIR = SITE_DIR / "assets"
LOGS_DIR = SITE_DIR / "logs"

try:
    from corq.web.paths import (
        TOP7_PATH,
        CLOQ_PATH,
        ALL_PATH,
        RESULTS_PATH,
        THINQ_PATH,
        CORQ_RSS_PATH,
        CLOQ_RSS_PATH,
        THINQ_RSS_PATH,
        NAV_ITEMS,
    )
except Exception:
    TOP7_PATH = "h4v34n1c3d4y180"
    CLOQ_PATH = "h4v34n1c3d4y181"
    ALL_PATH = "h4v34n1c3d4y182"
    RESULTS_PATH = "h4v34n1c3d4y183"
    CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
    CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"
    THINQ_PATH = "h4v34n1c3d4y186"
    THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"
    NAV_ITEMS = [("CorQ", TOP7_PATH), ("All", ALL_PATH), ("Results", RESULTS_PATH), ("CloQ", CLOQ_PATH), ("TG RSS", CORQ_RSS_PATH)]

try:
    from corq.messages import public_flag_labels as _messages_public_flag_labels
except Exception:
    _messages_public_flag_labels = None


def public_flag_labels(flags: Iterable[str], limit: Optional[int] = None) -> List[str]:
    if _messages_public_flag_labels is not None:
        try:
            labels = _messages_public_flag_labels(flags)
        except TypeError:
            try:
                labels = _messages_public_flag_labels(flags, limit)
            except TypeError:
                labels = []
    else:
        labels = []
        for flag in flags or []:
            if flag:
                labels.append(str(flag).replace("_", " ").strip().title())
    if labels is None:
        labels = []
    if isinstance(labels, str):
        labels = [labels]
    out: List[str] = []
    seen = set()
    for item in labels:
        text = str(item).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out[:limit] if limit is not None else out



_INFO_CACHE: Optional[Dict[str, Any]] = None

def load_explanations() -> Dict[str, Any]:
    global _INFO_CACHE
    if _INFO_CACHE is not None:
        return _INFO_CACHE
    data = read_json(WEB_DIR / "explanations.json", {})
    if not isinstance(data, dict):
        data = {}
    _INFO_CACHE = data
    return data

def explanation_text(key: str) -> str:
    data = load_explanations()
    aliases = {
        "corq": "corq_box",
        "thinq": "thinq_box",
        "ta": "ta_box",
        "ta_set_game": "ta_set_game",
        "ta_tiebreak": "ta_tiebreak",
        "ta_surface_dr": "ta_surface_dr",
        "ta_depth": "ta_depth",
        "aces": "aces",
        "h2h": "h2h",
        "s_h2h": "s_h2h",
        "stat_data_depth": "pick_data_depth",
        "form_data_depth": "form_data_depth",
    }
    lookup_keys = [key, aliases.get(key, "")]
    for lookup in lookup_keys:
        if not lookup:
            continue
        item = data.get(lookup)
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            text = str(item.get("text") or item.get("description") or "").strip()
            if title and text:
                return f"{title}: {text}"
            if text:
                return text
            if title:
                return title
        elif isinstance(item, str) and item.strip():
            return item.strip()
    defaults = {
        "corq": "CorQ is the final win probability for the displayed pick.",
        "thinq": "ThinQ is the overall data quality for the match, not win probability.",
        "ta": "TA contains Tennis Abstract player-profile stats prepared for set, game and serve/return analysis.",
        "ta_set_game": "Set and game win percentages for pick and opponent from the relevant Tennis Abstract sample when available.",
        "ta_tiebreak": "Tiebreak win-loss split from the relevant Tennis Abstract sample when available.",
        "ta_surface_dr": "Dominance ratio on the relevant surface. Values above 1.00 indicate stronger performance.",
        "ta_depth": "Internal confidence score for Tennis Abstract coverage and sample quality.",
        "aces": "Projected aces for pick, opponent and total. Currently N/A until the set and game model is completed.",
        "stat_data_depth": "S Data Depth shows the statistical support for the current pick.",
        "form_data_depth": "F Data Depth shows the reliability of recent form, surface form and opponent-quality data.",
    }
    return defaults.get(key, key)

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[render] failed to read {path}: {exc}")
    return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "picks", "cloq", "records", "results", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def as_pct(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.{digits}f}%"



def pct_pair(left: Any, right: Any, digits: int = 1) -> str:
    return f"{as_pct(left, digits)} / {as_pct(right, digits)}"

def value_pair(left: Any, right: Any, digits: int = 2) -> str:
    l = as_float(left)
    r = as_float(right)
    lt = "—" if l is None else f"{l:.{digits}f}"
    rt = "—" if r is None else f"{r:.{digits}f}"
    return f"{lt} / {rt}"

def wl_text(value: Any) -> str:
    if isinstance(value, dict):
        w = value.get("wins") if value.get("wins") is not None else value.get("w")
        l = value.get("losses") if value.get("losses") is not None else value.get("l")
        if w is not None or l is not None:
            return f"{fmt_int(w, '0')}-{fmt_int(l, '0')}"
    if isinstance(value, str) and value.strip():
        return esc(value.strip())
    return "—"

def ta_depth_display(row: Dict[str, Any]) -> str:
    return pct_pair(row.get("ta_pick_depth"), row.get("ta_opp_depth"), 0)

def aces_display(row: Dict[str, Any]) -> str:
    p = as_float(row.get("pick_aces_line"))
    o = as_float(row.get("opponent_aces_line"))
    t = as_float(row.get("total_aces_line"))
    if p is None and o is None and t is None:
        return "N/A / N/A / N/A"
    def one(x: Optional[float]) -> str:
        return "N/A" if x is None else f"{x:.1f}"
    return f"{one(p)} / {one(o)} / {one(t)}"

def signed_pct(value: Any, digits: int = 1) -> str:
    num = as_float(value, 0.0) or 0.0
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:+.{digits}f}%"


def fmt_odds(value: Any) -> str:
    num = as_float(value)
    if num is None or num <= 0:
        return "—"
    return f"{num:.2f}"


def fmt_int(value: Any, default: str = "—") -> str:
    try:
        if value is None or value == "":
            return default
        return str(int(float(value)))
    except Exception:
        return default


def normal_status(row: Dict[str, Any]) -> str:
    return str(row.get("status") or row.get("match_status") or row.get("event_status") or "").lower()


def compact_record_label(record: str) -> Tuple[Optional[int], Optional[int]]:
    txt = str(record or "").strip()
    m = re.search(r"(\d+)\D+(\d+)", txt)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def surface_name(row: Dict[str, Any]) -> str:
    return str(row.get("surface") or "Surface").strip() or "Surface"


def card_insights(row: Dict[str, Any], notes: Optional[List[str]] = None, limit: int = 2) -> List[str]:
    """Return max two compact, time/context-aware match insights for the pick card.

    The renderer is deliberately conservative: it shows only unusually strong
    context, and never turns raw stats into a table. Existing precomputed
    insight fields are preferred when available.
    """
    candidates: List[Tuple[int, str]] = []

    def add(priority: int, text: Any) -> None:
        t = str(text or "").strip()
        if t:
            candidates.append((priority, t))

    # Prefer already prepared intelligence outputs from THINQ/CORQ if present.
    for key in ("card_insights", "thinq_insights", "match_insights", "public_insights"):
        val = row.get(key)
        items: List[Any] = []
        if isinstance(val, list):
            items = val
        elif isinstance(val, str) and val.strip():
            items = [x.strip() for x in re.split(r"[|;]", val) if x.strip()]
        for item in items:
            if isinstance(item, dict):
                text = item.get("label") or item.get("text") or item.get("display")
                pr = int(as_float(item.get("priority"), 70) or 70)
                add(pr, text)
            else:
                add(70, item)

    # H2H, only when it is meaningful and clearly one-sided.
    hp, ho = h2h_record(row)
    if hp is not None and ho is not None and (hp + ho) >= 3 and max(hp, ho) >= 3:
        if hp == 0 or ho == 0 or abs(hp - ho) >= 3:
            add(96, f"⚔ H2H: {hp}-{ho}")

    shp, sho = surface_h2h_record(row)
    if shp is not None and sho is not None and (shp + sho) >= 3 and max(shp, sho) >= 3:
        if shp == 0 or sho == 0 or abs(shp - sho) >= 3:
            add(94, f"⚔ {surface_name(row)} H2H: {shp}-{sho}")

    # Last 10 records, only strong positive/negative cases.
    pf, psf = form_records(row, "pick")
    of, osf = form_records(row, "opponent")
    for priority, label, rec in (
        (88, "Pick Last 10", pf),
        (84, "Opp Last 10", of),
    ):
        w, l = compact_record_label(rec)
        if w is not None and l is not None and (w + l) >= 8 and (w >= 8 or l >= 7):
            icon = "🔥" if w >= 8 else "⚠"
            add(priority, f"{icon} {label}: {w}-{l}")

    surf = surface_name(row)
    for priority, label, rec in (
        (92, f"Pick {surf} Last 10", psf),
        (86, f"Opp {surf} Last 10", osf),
    ):
        w, l = compact_record_label(rec)
        if w is not None and l is not None and (w + l) >= 8 and (w >= 8 or l >= 7):
            icon = "🔥" if w >= 8 else "⚠"
            add(priority, f"{icon} {label}: {w}-{l}")

    # Optional absence fields if THINQ starts publishing them.
    for side, label, priority in (("pick", "Pick", 90), ("opponent", "Opp", 82)):
        weeks = None
        for key in (
            f"{side}_surface_absence_weeks",
            f"{side}_weeks_since_surface_match",
            f"{side}_surface_weeks_since_last_match",
        ):
            weeks = as_float(row.get(key))
            if weeks is not None:
                break
        if weeks is not None and weeks >= 26:
            add(priority, f"⚠ {label}: No {surf} match {int(round(weeks))}w")

    # Last resort: public notes, but still limited to two rows.
    for n in notes or []:
        add(30, n)

    out: List[str] = []
    seen = set()
    for _, txt in sorted(candidates, key=lambda kv: (-kv[0], kv[1])):
        clean = re.sub(r"\s+", " ", txt).strip()
        if clean and clean not in seen:
            out.append(clean)
            seen.add(clean)
        if len(out) >= limit:
            break
    return out


def card_insights_html(row: Dict[str, Any], notes: Optional[List[str]] = None) -> str:
    insights = card_insights(row, notes, limit=2)
    if not insights:
        return '<div class="card-insights empty-insights"><span>—</span></div>'
    return '<div class="card-insights">' + ''.join(f'<div>{esc(x)}</div>' for x in insights[:2]) + '</div>'

def player_rank_display(row: Dict[str, Any], side: str) -> str:
    keys = [f"{side}_ta_rank_display", f"{side}_rank_display", f"{side}_ta_rank", f"{side}_rank"]
    for key in keys:
        val = row.get(key)
        if val is None or val == "":
            continue
        txt = str(val).strip()
        if txt.startswith("(") and txt.endswith(")"):
            return txt
        try:
            return f"({int(float(txt))})"
        except Exception:
            if txt and txt.lower() != "none":
                return f"({txt})"
    return "(X)"


def add_rank(name: Any, row: Dict[str, Any], side: str) -> str:
    return f'{esc(name or "—")} <span class="rank">{esc(player_rank_display(row, side))}</span>'


def pick_name(row: Dict[str, Any]) -> str:
    return str(row.get("pick") or row.get("cloq_pick") or row.get("player") or row.get("player1") or row.get("home") or "—")


def opponent_name(row: Dict[str, Any]) -> str:
    return str(row.get("opponent") or row.get("opp") or row.get("player2") or row.get("away") or "—")


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "cloq_pick_odds", "selected_odds", "odds_decimal", "decimal_odds"):
        val = as_float(row.get(key))
        if val and val > 0:
            return val
    val = as_float(row.get("odds"))
    if val and val > 0:
        return val
    return None


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("opponent_odds", "opp_odds", "cloq_opponent_odds", "opponent_price"):
        val = as_float(row.get(key))
        if val and val > 0:
            return val
    return None


def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability", "cloq_probability"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def thinq_conf(row: Dict[str, Any]) -> Optional[float]:
    for key in ("thinq_confidence", "thinq_overall_confidence", "thinq_probability_confidence", "data_confidence"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    layer = row.get("thinq_probability_layer")
    if isinstance(layer, dict):
        return as_float(layer.get("confidence"))
    return None


def stat_depth(row: Dict[str, Any]) -> Optional[float]:
    for key in ("stat_data_depth", "pick_data_depth", "data_depth", "top7_pick_data_depth"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return thinq_conf(row)


def form_depth(row: Dict[str, Any]) -> Optional[float]:
    for key in ("form_data_depth", "form_confidence", "recent_form_confidence"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def pick_edge(row: Dict[str, Any]) -> float:
    for key in ("pick_thinq_edge", "thinq_edge", "thinq_total_edge", "top7_pick_thinq_edge"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    layer = row.get("thinq_probability_layer")
    if isinstance(layer, dict):
        val = as_float(layer.get("edge"))
        if val is not None:
            return val
    p = probability(row)
    if p is None:
        return 0.0
    if p > 1:
        p /= 100.0
    return p - 0.5


def sign_class(value: Any, mode: str = "pick") -> str:
    num = as_float(value, 0.0) or 0.0
    if abs(num) <= 1.0:
        num *= 100.0
    if abs(num) < 0.05:
        return "neutral"
    if mode == "opp":
        return "bad" if num > 0 else "good"
    return "good" if num > 0 else "bad"


def h2h_record(row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    for a, b in (("h2h_pick_wins", "h2h_opponent_wins"), ("thinq_h2h_pick_wins", "thinq_h2h_opponent_wins")):
        if row.get(a) is not None or row.get(b) is not None:
            return int(as_float(row.get(a), 0) or 0), int(as_float(row.get(b), 0) or 0)
    txt = str(row.get("h2h_record") or row.get("thinq_h2h_record") or "")
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def surface_h2h_record(row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    for a, b in (("surface_h2h_pick_wins", "surface_h2h_opponent_wins"), ("thinq_surface_h2h_pick_wins", "thinq_surface_h2h_opponent_wins")):
        if row.get(a) is not None or row.get(b) is not None:
            return int(as_float(row.get(a), 0) or 0), int(as_float(row.get(b), 0) or 0)
    txt = str(row.get("surface_h2h_record") or row.get("s_h2h_record") or "")
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def h2h_display(row: Dict[str, Any]) -> str:
    status = str(row.get("h2h_status") or row.get("thinq_h2h_status") or "").upper()
    if "NO_PREVIOUS" in status or str(row.get("h2h_display") or "").lower().startswith("no previous"):
        return "No previous matches"
    p, o = h2h_record(row)
    edge = as_float(row.get("h2h_edge") or row.get("thinq_h2h_edge"))
    if p is None or o is None:
        return "No previous matches" if status in {"NO_DATA", "NO_MATCHES"} else "No data"
    if edge is None:
        return f"{p}W-{o}L"
    return f"{p}W-{o}L · {signed_pct(edge)}"


def h2h_class(row: Dict[str, Any]) -> str:
    p, o = h2h_record(row)
    edge = as_float(row.get("h2h_edge") or row.get("thinq_h2h_edge"), 0.0) or 0.0
    if p is None or o is None:
        return "neutral"
    if p > o or edge > 0:
        return "good"
    if p < o or edge < 0:
        return "bad"
    return "neutral"


def surface_h2h_display(row: Dict[str, Any]) -> str:
    p, o = surface_h2h_record(row)
    if p is None or o is None or (p == 0 and o == 0):
        return "No data"
    return f"{p}W-{o}L"


def surface_h2h_class(row: Dict[str, Any]) -> str:
    p, o = surface_h2h_record(row)
    if p is None or o is None:
        return "neutral"
    if p > o:
        return "good"
    if p < o:
        return "bad"
    return "neutral"


def record_display(record: Any) -> str:
    if isinstance(record, dict):
        w = record.get("wins") or record.get("w") or record.get("win") or 0
        l = record.get("losses") or record.get("l") or record.get("loss") or 0
        return f"{fmt_int(w, '0')}W-{fmt_int(l, '0')}L"
    txt = str(record or "")
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        return f"{m.group(1)}W-{m.group(2)}L"
    return "0W-0L" if not txt else esc(txt)


def form_records(row: Dict[str, Any], side: str) -> Tuple[str, str]:
    prefix = "pick" if side == "pick" else "opponent"
    form = row.get(f"{prefix}_last10_record") or row.get(f"{prefix}_form_record") or row.get(f"{prefix}_recent_record")
    sform = row.get(f"{prefix}_surface_record") or row.get(f"{prefix}_surface_last10_record")
    rf = row.get("recent_form")
    if isinstance(rf, dict):
        form = form or rf.get(f"{prefix}_last10_record") or rf.get(f"{prefix}_record")
        sform = sform or rf.get(f"{prefix}_surface_record")
    return record_display(form), record_display(sform)


def notes_for_row(row: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    for key in ("corq_warning_flags", "risk_flags", "reject_reasons", "top7_quality_reject_reasons", "top7_risk_tags", "flags"):
        val = row.get(key)
        if isinstance(val, list):
            flags.extend(str(x) for x in val if x)
        elif isinstance(val, str) and val:
            flags.append(val)
    if not row.get("odds_pair_available") or pick_odds(row) is None or opponent_odds(row) is None:
        flags.append("MISSING_ODDS")
    h2h_txt = h2h_display(row).lower()
    if h2h_txt.startswith("no previous"):
        flags.append("H2H_NO_PREVIOUS_MATCHES")
    if row.get("recent_form_status") in {"NO_DATA", "PENDING"} or str(row.get("recent_form_status") or "").upper().endswith("PENDING"):
        flags.append("RECENT_FORM_NO_DATA")
    return public_flag_labels(flags, limit=None)


def slugify(value: Any) -> str:
    text = str(value or "match").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "match"


def match_key(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_id", "match_id", "custom_id", "customId", "id"):
        val = row.get(key)
        if val:
            return slugify(val)
    return slugify(f"{pick_name(row)}-{opponent_name(row)}-{row.get('start_time') or row.get('match_time') or ''}")


def row_match_identity(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_id", "match_id", "custom_id", "customId", "id"):
        val = row.get(key)
        if val:
            return str(val)
    names = sorted([pick_name(row).lower(), opponent_name(row).lower()])
    return "|".join(names) + "|" + str(row.get("start_time") or row.get("match_time") or "")


def better_all_row(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    def score(r: Dict[str, Any]) -> Tuple[float, float, float, float, float, float]:
        publish = 1.0 if r.get("top7_publishable") or r.get("eligible_for_top7") else 0.0
        return (
            publish,
            as_float(probability(r), 0.0) or 0.0,
            as_float(stat_depth(r), 0.0) or 0.0,
            as_float(pick_edge(r), 0.0) or 0.0,
            as_float(form_depth(r), 0.0) or 0.0,
            as_float(pick_odds(r), 0.0) or 0.0,
        )
    return a if score(a) >= score(b) else b


def dedupe_matches(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        key = row_match_identity(row)
        if key not in by_key:
            by_key[key] = row
            order.append(key)
        else:
            by_key[key] = better_all_row(by_key[key], row)
    return [by_key[k] for k in order]


def bar_html(value: Any) -> str:
    pct = as_float(value, 0.0) or 0.0
    if pct <= 1.0:
        pct *= 100.0
    pct = max(0.0, min(100.0, pct))
    cls = "bar-good" if pct >= 70 else "bar-mid" if pct >= 40 else "bar-bad"
    return f'<span class="depth-wrap"><span class="depth-number">{pct:.0f}%</span><span class="depth-bar"><span class="{cls}" style="width:{pct:.0f}%"></span></span></span>'


def metric_row(label: str, value: str, cls: str = "") -> str:
    return f'<div class="metric-row {esc(cls)}"><span>{esc(label)}</span><b>{value}</b></div>'


def info_icon(key: str) -> str:
    tip = explanation_text(key)
    return f'<span class="info" tabindex="0" role="button" aria-label="{esc(tip)}" data-tip="{esc(tip)}">i</span>'


def start_time(row: Dict[str, Any]) -> str:
    raw = row.get("start_time_display") or row.get("match_time_display") or row.get("start_time") or row.get("start_time_utc") or row.get("match_time") or ""
    if not raw:
        return "—"
    txt = str(raw)
    m = re.search(r"(\d{1,2}:\d{2})", txt)
    return m.group(1) if m else txt[:16]


def meta_line(row: Dict[str, Any]) -> str:
    bits = []
    for key in ("tournament", "category", "surface", "best_of"):
        val = row.get(key)
        if val:
            bits.append(str(val))
    return " · ".join(bits) if bits else "—"


def log_link(row: Dict[str, Any]) -> str:
    return f'../logs/{esc(match_key(row))}/index.html'


def ensure_logs(rows: List[Dict[str, Any]]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        key = match_key(row)
        path = LOGS_DIR / key
        path.mkdir(parents=True, exist_ok=True)
        data = json.dumps(row, ensure_ascii=False, indent=2, default=str)
        write_text(path / "thinq-log.json", data)
        html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Calculation log</title><style>body{{background:#08111f;color:#dbeafe;font-family:Consolas,monospace;padding:24px}}pre{{white-space:pre-wrap;background:#0f1b2d;border:1px solid #23344d;border-radius:14px;padding:18px}}</style></head><body><h1>Calculation log</h1><pre>{esc(data)}</pre></body></html>"""
        write_text(path / "index.html", html_doc)


def render_card(row: Dict[str, Any], rank: Optional[int] = None, page: str = "corq") -> str:
    p = pick_name(row)
    o = opponent_name(row)
    p_odds = pick_odds(row)
    o_odds = opponent_odds(row)
    prob = probability(row)
    pe = pick_edge(row)
    pe_txt = signed_pct(pe)
    pe_state = "Support" if pe > 0.0005 else "Against" if pe < -0.0005 else "Neutral"
    pe_cls = "good" if pe > 0 else "bad" if pe < 0 else "neutral"
    pick_form, pick_sform = form_records(row, "pick")
    opp_form, opp_sform = form_records(row, "opponent")
    notes = notes_for_row(row)
    data_tags = "|".join(notes)
    rank_badge = f'<div class="rank-num">#{rank}</div>' if rank else ""
    note_html = "".join(f'<span class="note" data-note="{esc(n)}">{esc(n)}</span>' for n in notes[:8])
    odds_gap = as_float(row.get("odds_gap_pct") or row.get("cloq_odds_gap_pct"))
    odds_gap_txt = as_pct(odds_gap, 1) if odds_gap is not None else "—"
    cloq_extra = metric_row("Odds Gap", odds_gap_txt) if page == "cloq" else ""
    html_parts = [
        f'<article class="pick-card" data-tags="{esc(data_tags)}">',
        '<section class="pick-main">',
        f'<h2>{add_rank(p, row, "pick")}</h2>',
        f'<div class="odds-line">Pick @ <b>{fmt_odds(p_odds)}</b></div>',
        '<div class="to-beat">to beat</div>',
        f'<h3>{add_rank(o, row, "opponent")}</h3>',
        f'<div class="odds-line muted">Opp @ <b>{fmt_odds(o_odds)}</b></div>',
        f'<div class="time-line">{esc(start_time(row))} · {esc(meta_line(row))}</div>',
        f'<div class="status-line">Status: {esc(normal_status(row) or "—")}</div>',
        f'<div class="notes">{note_html}</div>' if note_html else '',
        '<div class="card-footer-row">'
        f'<div class="card-footer-tools">{rank_badge}<a class="brain" href="{log_link(row)}" title="Open calculation log">🧠</a></div>'
        f'{card_insights_html(row, notes)}'
        '</div>',
        '</section>',
        '<section class="metric-box">',
        f'<div class="box-head"><span>CorQ {info_icon("corq")}</span><b>{as_pct(prob, 1)}</b></div>',
        metric_row("P EL / S-E", f'{signed_pct(row.get("elo_edge") or row.get("pick_elo_edge"))} / {signed_pct(row.get("surface_elo_edge") or row.get("pick_surface_elo_edge"))}', sign_class(row.get("elo_edge") or row.get("pick_elo_edge"))),
        metric_row("O EL / S-E", f'{signed_pct(-(as_float(row.get("elo_edge") or row.get("pick_elo_edge"), 0) or 0))} / {signed_pct(-(as_float(row.get("surface_elo_edge") or row.get("pick_surface_elo_edge"), 0) or 0))}', "good"),
        metric_row("H2H P-O", esc(h2h_display(row)), h2h_class(row)),
        metric_row("S-H2H P-O", esc(surface_h2h_display(row)), surface_h2h_class(row)),
        metric_row("P ThinQ Edge", esc(f"{pe_txt} / {pe_state}"), pe_cls),
        metric_row("S Data Depth", bar_html(stat_depth(row))),
        '</section>',
        '<section class="metric-box">',
        f'<div class="box-head"><span>ThinQ {info_icon("thinq")}</span><b>{as_pct(thinq_conf(row), 1)}</b></div>',
        metric_row("P F / S-F", esc(f"{pick_form} / {pick_sform}")),
        metric_row("O F / S-F", esc(f"{opp_form} / {opp_sform}")),
        metric_row("P R-Edge", signed_pct(row.get("recent_form_edge") or row.get("short_form_edge")), sign_class(row.get("recent_form_edge") or row.get("short_form_edge"))),
        metric_row("P S-Edge", signed_pct(row.get("surface_recent_form_edge")), sign_class(row.get("surface_recent_form_edge"))),
        metric_row("P F Qty", signed_pct(row.get("opponent_quality_edge")), sign_class(row.get("opponent_quality_edge"))),
        metric_row("F Data Depth", bar_html(form_depth(row))),
        '</section>',
        render_ta_box(row),
        render_sets_games_box(row),
        render_marq_box(row) if page != "cloq" else render_cloq_box(row),
        cloq_extra,
        '</article>',
    ]
    return "\n".join(x for x in html_parts if x)



def ta_first_text(row: Dict[str, Any], keys: Iterable[str], default: str = "N/A") -> str:
    for key in keys:
        val = row.get(key)
        if val is None or val == "":
            continue
        txt = str(val).strip()
        if txt and txt.lower() not in {"none", "null", "nan", "—", "-"}:
            return txt
    return default


def ta_depth_label(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_depth_label",
            "ta_data_depth_label",
            "ta_decision_depth_label",
            "ta_coverage_label",
        ),
        "",
    )
    if explicit:
        return explicit
    vals = [as_float(row.get("ta_pick_depth")), as_float(row.get("ta_opp_depth"))]
    vals = [v * 100.0 if v is not None and abs(v) <= 1.0 else v for v in vals if v is not None]
    if not vals:
        return "N/A"
    avg = sum(vals) / len(vals)
    if avg >= 70:
        return "Good"
    if avg >= 40:
        return "Thin"
    return "Weak"


def ta_winner_read(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_winner_decision",
            "ta_winner_read",
            "ta_winner_support",
            "ta_pick_support",
        ),
        "",
    )
    if explicit:
        return explicit
    pick_dr = as_float(row.get("ta_pick_surface_dr") or row.get("ta_pick_dr"))
    opp_dr = as_float(row.get("ta_opp_surface_dr") or row.get("ta_opp_dr"))
    if pick_dr is None or opp_dr is None:
        return "N/A"
    diff = pick_dr - opp_dr
    if diff >= 0.08:
        return "Supports Pick"
    if diff <= -0.08:
        return "Supports Opp"
    if abs(diff) <= 0.03:
        return "Neutral"
    return "Slight Pick" if diff > 0 else "Slight Opp"


def ta_match_shape_read(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_match_shape",
            "ta_shape",
            "ta_match_type",
        ),
        "",
    )
    if explicit:
        return explicit
    pick_dr = as_float(row.get("ta_pick_surface_dr") or row.get("ta_pick_dr"))
    opp_dr = as_float(row.get("ta_opp_surface_dr") or row.get("ta_opp_dr"))
    if pick_dr is None or opp_dr is None:
        return "N/A"
    diff = abs(pick_dr - opp_dr)
    if diff <= 0.03:
        return "Competitive"
    if diff >= 0.12:
        return "One-sided"
    return "Moderate Edge"


def ta_aces_input_status(row: Dict[str, Any]) -> str:
    return ta_first_text(
        row,
        (
            "ta_aces_decision",
            "ta_aces_input_status",
            "ta_aces_status",
        ),
        aces_display(row),
    )

def render_ta_box(row: Dict[str, Any]) -> str:
    """Render Tennis Abstract as decision output, not a raw stat table."""
    return "\n".join([
        '<section class="metric-box small-box">',
        f'<div class="box-head"><span>TA {info_icon("ta")}</span><b></b></div>',
        metric_row("Winner Read", esc(ta_winner_read(row))),
        metric_row(
            "Sets Read",
            esc(
                ta_first_text(
                    row,
                    (
                        "ta_sets_decision",
                        "ta_sets_read",
                        "ta_set_direction",
                        "ta_sets_direction",
                    ),
                )
            ),
        ),
        metric_row(
            "Games Read",
            esc(
                ta_first_text(
                    row,
                    (
                        "ta_games_decision",
                        "ta_games_read",
                        "ta_games_direction",
                        "ta_games_lean",
                    ),
                )
            ),
        ),
        metric_row(
            "TB Read",
            esc(
                ta_first_text(
                    row,
                    (
                        "ta_tb_decision",
                        "ta_tb_read",
                        "ta_tb_direction",
                        "ta_tb_potential",
                    ),
                )
            ),
        ),
        metric_row(
            "Serve Pattern",
            esc(
                ta_first_text(
                    row,
                    (
                        "ta_serve_return_pattern",
                        "ta_serve_pattern",
                        "ta_serve_pressure",
                        "ta_pressure_pattern",
                    ),
                )
            ),
        ),
        metric_row("Match Shape", esc(ta_match_shape_read(row))),
        metric_row("TA Depth", esc(ta_depth_label(row))),
        metric_row("Aces", esc(aces_display(row))),
        '</section>',
    ])


def render_sets_games_box(row: Dict[str, Any]) -> str:
    return "\n".join([
        '<section class="metric-box small-box">',
        '<div class="box-head"><span>Sets / Games</span><b></b></div>',
        metric_row("Sets", esc(row.get("projected_sets") or row.get("sets") or "—")),
        metric_row("Games", esc(row.get("projected_games") or row.get("games") or "—")),
        metric_row("O/U", esc(row.get("over_under_display") or row.get("ou_display") or "—")),
        metric_row("3 Sets", as_pct(row.get("three_sets_probability") or row.get("decider_probability"), 1)),
        metric_row("Score", esc(row.get("predicted_score") or row.get("score_prediction") or "—")),
        metric_row("Tie-break", as_pct(row.get("tie_break_probability") or row.get("tiebreak_probability"), 1)),
        metric_row("P / O / T Aces", esc(aces_display(row))),
        '</section>',
    ])


def render_marq_box(row: Dict[str, Any]) -> str:
    return "\n".join([
        '<section class="metric-box small-box">',
        '<div class="box-head"><span>MarQ</span><b></b></div>',
        metric_row("Market", esc(row.get("marq_status") or "Pending")),
        metric_row("Pick MarQ", esc(row.get("pick_marq") or "—")),
        metric_row("Opp MarQ", esc(row.get("opponent_marq") or "—")),
        metric_row("Move", esc(row.get("market_move") or "—")),
        metric_row("Odds Source", esc(row.get("odds_source") or "—")),
        metric_row("Direction", esc(row.get("odds_matching_direction_display") or row.get("odds_matching_direction") or "Confirmed")),
        '</section>',
    ])


def render_cloq_box(row: Dict[str, Any]) -> str:
    return "\n".join([
        '<section class="metric-box small-box">',
        '<div class="box-head"><span>CloQ</span><b></b></div>',
        metric_row("Status", esc(row.get("cloq_status") or "OK")),
        metric_row("Odds Gap", as_pct(row.get("cloq_odds_gap_pct") or row.get("odds_gap_pct"), 1)),
        metric_row("Source", "ALL"),
        metric_row("Rank", esc(row.get("cloq_rank") or "—")),
        metric_row("Filter", "Close odds"),
        metric_row("Limit", "10% gap"),
        '</section>',
    ])


def copy_assets() -> str:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    version = str(int(datetime.now(tz=timezone.utc).timestamp()))
    target = ASSET_DIR / "tbt_ai_goat_icon.png"
    try:
        if ASSET_SRC.exists():
            shutil.copyfile(ASSET_SRC, target)
    except Exception as exc:
        print(f"[render] asset copy failed: {exc}")
    return f"assets/tbt_ai_goat_icon.png?v={version}"


def css() -> str:
    return """
:root{--bg:#08111f;--panel:#111d2f;--panel2:#0e1828;--line:#24344d;--text:#e5eefc;--muted:#8ea5c2;--cyan:#38d5ff;--green:#34d399;--orange:#fb923c;--red:#f87171;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#10233d 0,#08111f 42%,#050b14 100%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}.wrap{max-width:1680px;margin:0 auto;padding:18px}.topbar{display:flex;align-items:center;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px;min-width:260px}.brand-logo{width:56px;height:56px;border-radius:999px;object-fit:contain;padding:6px;background:#071827;border:1px solid rgba(56,213,255,.65);box-shadow:0 0 22px rgba(56,213,255,.18)}.brand-title{font-weight:900;font-size:18px}.brand-sub{font-size:11px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase}.nav{display:flex;gap:10px;flex-wrap:wrap}.nav a{color:#bcd1ea;text-decoration:none;border:1px solid #22344d;background:#0d1727;padding:8px 13px;border-radius:999px;font-weight:700}.nav a.active{border-color:var(--cyan);box-shadow:0 0 0 1px rgba(56,213,255,.25),0 0 18px rgba(56,213,255,.14);color:#fff}.hero{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}.hero-panel{background:linear-gradient(180deg,rgba(17,29,47,.92),rgba(9,17,30,.92));border:1px solid #23344d;border-radius:18px;padding:14px}.hero-title{font-size:11px;color:var(--cyan);text-transform:uppercase;letter-spacing:.14em;font-weight:900}.hero-line{margin-top:4px;color:#dbeafe}.grid{display:grid;gap:14px}.pick-card{display:grid;grid-template-columns:minmax(260px,1.1fr) repeat(5,minmax(220px,1fr));gap:12px;background:rgba(10,18,32,.72);border:1px solid #20314a;border-radius:22px;padding:12px;box-shadow:0 12px 36px rgba(0,0,0,.25)}.pick-main,.metric-box{background:linear-gradient(180deg,#121f32,#0c1625);border:1px solid #283a55;border-radius:18px;padding:14px;min-width:0}.card-top{display:flex;justify-content:space-between;align-items:center}.rank-num{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;padding:0 8px;border-radius:999px;background:#13253c;border:1px solid #2d4b6f;color:var(--cyan);font-size:12px;font-weight:900}.brain{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:999px;text-decoration:none;background:#15243a;border:1px solid #334862;flex:0 0 auto}.card-footer-row{display:flex;align-items:flex-end;gap:8px;margin-top:12px}.card-footer-tools{display:flex;align-items:center;gap:6px;flex:0 0 auto}.card-insights{flex:1;min-width:0;background:#101b2c;border:1px solid rgba(51,72,98,.55);border-radius:10px;padding:5px 8px;color:#dbeafe;font-size:11px;font-weight:800;line-height:1.25;overflow:hidden}.card-insights div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.card-insights.empty-insights{color:#64748b}.pick-main h2,.pick-main h3{margin:8px 0 4px;font-size:18px;line-height:1.2}.pick-main h3{font-size:16px;color:#dbeafe}.rank{font-size:.82em;color:#7dd3fc;font-weight:800}.odds-line{display:inline-block;color:#7ee7aa;background:#07351f;border:1px solid #0d7c49;border-radius:999px;padding:3px 8px;font-weight:800}.odds-line.muted{color:#bdd7f5;background:#111d2d;border-color:#263b58}.to-beat{margin:8px 0;color:#67e8f9;font-weight:900;text-transform:uppercase;font-size:11px}.time-line,.status-line{color:var(--muted);font-size:12px;margin-top:8px}.notes{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.note,.result-tag,.tag-chip{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;background:#16243a;border:1px solid #344a68;color:#bcd1ea;font-size:11px;font-weight:800}.box-head{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:10px;font-size:13px;font-weight:900;color:#bae6fd}.box-head b{font-size:20px;color:var(--green)}.metric-row{display:flex;justify-content:space-between;gap:12px;border-top:1px solid rgba(148,163,184,.14);padding:8px 0;color:#9fb5d1}.metric-row:first-of-type{border-top:0}.metric-row b{color:#f8fafc;text-align:right}.metric-row.good b{color:#f8fafc}.metric-row.bad b{color:var(--orange)}.metric-row.neutral b{color:#b9c6d8}.small-box .metric-row{font-size:12px}.depth-wrap{display:inline-flex;align-items:center;gap:8px}.depth-number{min-width:38px;text-align:right;color:#f8fafc}.depth-bar{display:inline-block;width:74px;height:8px;background:#1e293b;border-radius:999px;overflow:hidden;border:1px solid #334155}.depth-bar span{display:block;height:100%}.bar-good{background:linear-gradient(90deg,#10b981,#67e8f9)}.bar-mid{background:linear-gradient(90deg,#facc15,#fb923c)}.bar-bad{background:linear-gradient(90deg,#ef4444,#fb923c)}.info{position:relative;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:999px;border:1px solid #4b6b8d;color:#93c5fd;font-size:10px;margin-left:4px;cursor:help}.info:hover:after,.info:focus:after{content:attr(data-tip);position:absolute;left:50%;top:22px;transform:translateX(-50%);z-index:50;width:min(320px,80vw);white-space:normal;text-align:left;background:#0b1424;color:#e5eefc;border:1px solid #34506f;border-radius:12px;padding:10px 12px;box-shadow:0 12px 30px rgba(0,0,0,.35);font-size:12px;line-height:1.35}.summary-panel,.results-panel{margin-top:16px;background:#0d1727;border:1px solid #24344d;border-radius:20px;padding:16px}.summary-title{font-size:12px;color:var(--cyan);font-weight:900;text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px}.tag-list{display:flex;flex-wrap:wrap;gap:8px}.tag-chip{cursor:pointer}.tag-chip.active{border-color:var(--cyan);color:#fff;box-shadow:0 0 16px rgba(56,213,255,.18)}.clear-filter{display:none;margin-left:8px;color:#93c5fd;cursor:pointer}.table-wrap{overflow:auto;border:1px solid #24344d;border-radius:16px}.results-table{width:100%;border-collapse:collapse;min-width:1150px;background:#0b1424}.results-table th{background:#172235;color:#9cc5e8;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:11px}.results-table td{border-top:1px solid #26354d;padding:11px;vertical-align:top}.status-won{color:#34d399;font-weight:900}.status-lost{color:#fb7185;font-weight:900}.status-pending{color:#facc15;font-weight:900}.status-void{color:#94a3b8;font-weight:900}.empty{padding:34px;text-align:center;color:#9fb5d1;background:#0d1727;border:1px dashed #334155;border-radius:20px}.footer{margin-top:26px;text-align:center;color:#6f86a4;font-size:12px}@media(max-width:1200px){.pick-card{grid-template-columns:1fr 1fr}.hero{grid-template-columns:1fr}}@media(max-width:760px){.wrap{padding:10px}.topbar{align-items:flex-start;flex-direction:column}.pick-card{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.brand-logo{width:48px;height:48px}.metric-row{font-size:13px}.pick-main h2{font-size:17px}}
"""


def nav_html(active: str) -> str:
    parts = []
    for item in NAV_ITEMS:
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
            path = item.get("path") or item.get("url") or ""
            key = item.get("key") or label
        elif isinstance(item, (list, tuple)):
            label = item[0] if len(item) > 0 else ""
            path = item[1] if len(item) > 1 else ""
            key = item[2] if len(item) > 2 else label
        else:
            continue
        label_s = str(label)
        path_s = str(path)
        key_s = str(key)
        is_xml = path_s.endswith(".xml")
        if active == "root":
            href = path_s if is_xml else f"{path_s}/"
        else:
            href = f"../{path_s}" if is_xml else f"../{path_s}/"
        active_values = {label_s.lower(), path_s.lower(), key_s.lower()}
        cls = "active" if str(active).lower() in active_values else ""
        parts.append(f'<a class="{cls}" href="{esc(href)}">{esc(label_s)}</a>')
    return "".join(parts)


def hero_html(page_label: str, manifest: Dict[str, Any]) -> str:
    updated = manifest.get("updated_at") or manifest.get("generated_at") or manifest.get("run_at") or "—"
    top7_count = manifest.get("top7_count", "—")
    all_count = manifest.get("all_count", "—")
    ranked_count = manifest.get("ranked_count", "—")
    return f"""
<div class="hero">
  <div class="hero-panel"><div class="hero-title">Snapshot</div><div class="hero-line">{esc(page_label)} · Updated {esc(updated)}</div><div class="hero-line">TOP7 {esc(top7_count)} · ALL {esc(all_count)} · Ranked {esc(ranked_count)}</div></div>
  <div class="hero-panel"><div class="hero-title">Model</div><div class="hero-line">CorQ final probability · ThinQ data quality · MarQ market view</div><div class="hero-line">Audit tags and data depth are stored for Results.</div></div>
  <div class="hero-panel"><div class="hero-title">Notice</div><div class="hero-line">This data is provided for informational and analytical purposes only.</div><div class="hero-line">Powered by BackstageTalks Statistical Engine</div></div>
</div>
"""


def page_shell(title: str, active: str, body: str, manifest: Optional[Dict[str, Any]] = None) -> str:
    manifest = manifest or {}
    logo_url = copy_assets()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title><style>{css()}</style></head>
<body><div class="wrap">
<header class="topbar">
  <div class="brand"><img class="brand-logo" src="{esc(logo_url)}" alt="BackstageTalks logo"><div><div class="brand-title">BackstageTalks</div><div class="brand-sub">Statistical Engine</div></div></div>
  <nav class="nav">{nav_html(active)}</nav>
</header>
{hero_html(title, manifest)}
{body}
<div class="footer">This data is provided for informational and analytical purposes only. Powered by BackstageTalks Statistical Engine.</div>
</div>{tag_filter_script()}</body></html>"""


def tag_filter_script() -> str:
    return """
<script>
(function(){
  function filter(tag){
    document.querySelectorAll('.tag-chip').forEach(x=>x.classList.toggle('active', x.dataset.filter===tag));
    document.querySelectorAll('.pick-card,.result-row').forEach(card=>{
      const tags=(card.getAttribute('data-tags')||'').split('|');
      card.style.display = (!tag || tags.includes(tag)) ? '' : 'none';
    });
    document.querySelectorAll('.clear-filter').forEach(x=>x.style.display=tag?'inline-flex':'none');
  }
  document.addEventListener('click', function(e){
    const chip=e.target.closest('[data-filter]');
    if(chip){filter(chip.dataset.filter);}
    if(e.target.closest('.clear-filter')){filter('');}
  });
})();
</script>"""


def render_cards_page(title: str, active: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], page: str = "corq", dedupe: bool = False) -> str:
    rows = dedupe_matches(rows) if dedupe else rows
    ensure_logs(rows)
    if not rows:
        cards = '<div class="empty">No rows available.</div>'
    else:
        cards = '<div class="grid">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
    summary = render_notes_summary(rows) if page == "all" else ""
    return page_shell(title, active, cards + summary, manifest)


def render_notes_summary(rows: List[Dict[str, Any]]) -> str:
    counts = Counter()
    missing_breakdown = Counter()
    for row in rows:
        row_notes = notes_for_row(row)
        for note in row_notes:
            counts[note] += 1
        if "Missing odds" in row_notes:
            reason = str(row.get("odds_missing_reason_group") or row.get("no_odds_reason") or "Unknown")
            reason = reason.replace("_", " ").title()
            missing_breakdown[reason] += 1
    tags = "".join(f'<span class="tag-chip" data-filter="{esc(k)}">{v} {esc(k)}</span>' for k, v in counts.most_common())
    clear = '<span class="clear-filter tag-chip">Clear filter</span>'
    breakdown = ""
    if missing_breakdown:
        items = "".join(f'<span class="note">{v} {esc(k)}</span>' for k, v in missing_breakdown.most_common())
        breakdown = f'<div class="summary-panel"><div class="summary-title">Missing odds breakdown</div><div class="tag-list">{items}</div></div>'
    return f'<div class="summary-panel"><div class="summary-title">Data notes summary</div><div class="tag-list">{tags}{clear}</div></div>{breakdown}'


def result_status(row: Dict[str, Any]) -> str:
    return str(row.get("result") or row.get("result_status") or row.get("status") or "PENDING").upper()


def res_units(value: Any) -> str:
    num = as_float(value)
    if num is None:
        return "—"
    return f"{num:+.2f}u"


def summarize_results(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = lost = pending = void = 0
    units = 0.0
    odds_vals = []
    for r in rows:
        st = result_status(r)
        if st == "WON":
            won += 1
        elif st == "LOST":
            lost += 1
        elif st == "VOID":
            void += 1
        else:
            pending += 1
        units += as_float(r.get("units"), 0.0) or 0.0
        od = pick_odds(r)
        if od:
            odds_vals.append(od)
    decided = won + lost
    winp = (won / decided * 100.0) if decided else 0.0
    roi = (units / decided * 100.0) if decided else 0.0
    avg_odds = sum(odds_vals) / len(odds_vals) if odds_vals else None
    return {"picks": len(rows), "won": won, "lost": lost, "pending": pending, "void": void, "win_pct": winp, "units": units, "roi": roi, "avg_odds": avg_odds}


def summary_cards_html(summary: Dict[str, Any], title: str) -> str:
    avg = "—" if summary.get("avg_odds") is None else f"{summary['avg_odds']:.2f}"
    return f"""
<div class="summary-panel"><div class="summary-title">{esc(title)}</div><div class="tag-list">
<span class="note">Picks {summary.get('picks',0)}</span><span class="note">W-L {summary.get('won',0)}-{summary.get('lost',0)}</span><span class="note">Pending {summary.get('pending',0)}</span><span class="note">Win {summary.get('win_pct',0):.1f}%</span><span class="note">Units {summary.get('units',0):+.2f}u</span><span class="note">ROI {summary.get('roi',0):+.1f}%</span><span class="note">Avg odds {esc(avg)}</span>
</div></div>"""


def result_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("tags", "technical_flags", "corq_warning_flags", "top7_risk_tags", "public_notes"):
        val = row.get(key)
        if isinstance(val, list):
            tags.extend(str(x) for x in val if x)
    if not tags:
        tags = notes_for_row(row)
    return public_flag_labels(tags, limit=None)


def render_results_table(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    show = rows[:limit] if limit else rows
    if not show:
        return f'<div class="results-panel"><div class="summary-title">{esc(title)}</div><div class="empty">No evaluated results yet.</div></div>'
    body = []
    for r in show:
        tags = result_tags(r)
        data_tags = "|".join(tags)
        tag_html = "".join(f'<span class="result-tag">{esc(t)}</span>' for t in tags[:5])
        st = result_status(r)
        st_cls = "status-won" if st == "WON" else "status-lost" if st == "LOST" else "status-void" if st == "VOID" else "status-pending"
        sg = render_sets_games_result_cell(r)
        body.append(
            f'<tr class="result-row" data-tags="{esc(data_tags)}">'
            f'<td>{esc(r.get("date") or r.get("snapshot_date") or "—")}</td>'
            f'<td><b>{add_rank(pick_name(r), r, "pick")}</b><br><span class="odds-line">Pick @{fmt_odds(pick_odds(r))}</span><br><small>{esc(meta_line(r))}</small></td>'
            f'<td><b>{add_rank(opponent_name(r), r, "opponent")}</b></td>'
            f'<td>{as_pct(probability(r),1)}</td>'
            f'<td>{as_pct(thinq_conf(r),1)}</td>'
            f'<td>{bar_html(stat_depth(r))}<br>{bar_html(form_depth(r))}</td>'
            f'<td>{signed_pct(pick_edge(r))}</td>'
            f'<td>{sg}</td>'
            f'<td><span class="odds-line">{fmt_odds(pick_odds(r))}</span></td>'
            f'<td class="{st_cls}">{esc(st)}</td>'
            f'<td>{esc(r.get("winner") or "—")}</td>'
            f'<td>{esc(r.get("score") or r.get("final_score") or "—")}</td>'
            f'<td>{esc(res_units(r.get("units")))}</td>'
            f'<td>{tag_html}</td>'
            f'</tr>'
        )
    return f"""
<div class="results-panel"><div class="summary-title">{esc(title)}</div><div class="table-wrap"><table class="results-table"><thead><tr>
<th>Date</th><th>Pick</th><th>Opponent</th><th>CorQ</th><th>ThinQ</th><th>Depth</th><th>Pick Edge</th><th>Sets/Games</th><th>Odds</th><th>Status</th><th>Winner</th><th>Score</th><th>Units</th><th>Tags</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div></div>"""


def render_sets_games_result_cell(row: Dict[str, Any]) -> str:
    pred_sets = row.get("projected_sets") or row.get("sets_projected") or row.get("sets")
    actual_sets = row.get("actual_sets")
    pred_games = row.get("projected_games") or row.get("games_projected") or row.get("games")
    actual_games = row.get("actual_games")
    score_pred = row.get("predicted_score") or row.get("score_prediction")
    bits = []
    if pred_sets is not None or actual_sets is not None:
        hit = row.get("sets_hit")
        tag = "HIT" if hit is True else "MISS" if hit is False else "—"
        bits.append(f'<span class="result-tag">Sets: Pred {esc(pred_sets or "—")} → Real {esc(actual_sets or "—")} · {tag}</span>')
    if pred_games is not None or actual_games is not None:
        err = row.get("games_error")
        err_txt = "" if err is None else f" · err {as_float(err,0):+.1f}"
        bits.append(f'<span class="result-tag">Games: Pred {esc(pred_games or "—")} → Real {esc(actual_games or "—")}{esc(err_txt)}</span>')
    if score_pred:
        bits.append(f'<span class="result-tag">Score pred {esc(score_pred)}</span>')
    return "<br>".join(bits) if bits else "—"


def tag_analysis(rows: List[Dict[str, Any]]) -> str:
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "won": 0, "lost": 0, "pending": 0, "units": 0.0, "odds": []})
    for r in rows:
        for t in result_tags(r):
            a = agg[t]
            a["count"] += 1
            st = result_status(r)
            if st == "WON":
                a["won"] += 1
            elif st == "LOST":
                a["lost"] += 1
            else:
                a["pending"] += 1
            a["units"] += as_float(r.get("units"), 0.0) or 0.0
            od = pick_odds(r)
            if od:
                a["odds"].append(od)
    if not agg:
        return '<div class="results-panel"><div class="summary-title">Tag Analysis</div><div class="empty">No tag data yet.</div></div>'
    body = []
    for tag, a in sorted(agg.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        decided = a["won"] + a["lost"]
        winp = a["won"] / decided * 100 if decided else 0.0
        avg = sum(a["odds"]) / len(a["odds"]) if a["odds"] else None
        avg_txt = "—" if avg is None else f"{avg:.2f}"
        body.append(
            f'<tr><td><span class="tag-chip" data-filter="{esc(tag)}">{esc(tag)}</span></td>'
            f'<td>{a["count"]}</td><td>{a["won"]}-{a["lost"]}-{a["pending"]}</td>'
            f'<td>{winp:.1f}%</td><td>{a["units"]:+.2f}u</td><td>{esc(avg_txt)}</td></tr>'
        )
    return f'<div class="results-panel"><div class="summary-title">Tag Analysis</div><div class="table-wrap"><table class="results-table"><thead><tr><th>Tag</th><th>Count</th><th>W-L-P</th><th>Win %</th><th>Units</th><th>Avg odds</th></tr></thead><tbody>{"".join(body)}</tbody></table></div><span class="clear-filter tag-chip">Clear filter</span></div>'


def bucket_label(value: Optional[float], kind: str) -> str:
    if value is None:
        return "Missing"
    v = value * 100 if value <= 1.0 and kind != "odds" else value
    if kind == "odds":
        if v < 1.5:
            return "<1.50"
        if v < 1.8:
            return "1.50-1.79"
        if v < 2.2:
            return "1.80-2.19"
        return "2.20+"
    if v < 40:
        return "0-39%"
    if v < 60:
        return "40-59%"
    if v < 80:
        return "60-79%"
    return "80-100%"


def depth_analysis(rows: List[Dict[str, Any]]) -> str:
    sections = [
        ("S Data Depth", lambda r: stat_depth(r), "pct"),
        ("F Data Depth", lambda r: form_depth(r), "pct"),
        ("CorQ Probability", lambda r: probability(r), "pct"),
        ("Odds", lambda r: pick_odds(r), "odds"),
    ]
    blocks = []
    for title, getter, kind in sections:
        agg = Counter(bucket_label(getter(r), kind) for r in rows)
        chips = "".join(f'<span class="note">{esc(k)}: {v}</span>' for k, v in sorted(agg.items()))
        blocks.append(f'<div class="summary-title">{esc(title)}</div><div class="tag-list">{chips}</div>')
    return f'<div class="results-panel"><div class="summary-title">Data Depth Analysis</div>{"".join(blocks)}</div>'


def sets_games_audit(rows: List[Dict[str, Any]]) -> str:
    with_games = [r for r in rows if as_float(r.get("actual_games")) is not None]
    sets_rows = [r for r in rows if r.get("sets_hit") is not None]
    tb_rows = [r for r in rows if r.get("actual_tiebreak") is not None or r.get("tie_break_hit") is not None]
    avg_games = sum(as_float(r.get("actual_games"), 0) or 0 for r in with_games) / len(with_games) if with_games else 0
    errors = [as_float(r.get("games_error")) for r in rows if as_float(r.get("games_error")) is not None]
    avg_err = sum(errors) / len(errors) if errors else 0
    sets_hit = sum(1 for r in sets_rows if r.get("sets_hit") is True)
    sets_pct = sets_hit / len(sets_rows) * 100 if sets_rows else 0
    tb_count = sum(1 for r in tb_rows if r.get("actual_tiebreak") is True or r.get("tie_break_hit") is True)
    tb_pct = tb_count / len(tb_rows) * 100 if tb_rows else 0
    return f"""
<div class="results-panel"><div class="summary-title">Sets/Games Audit</div><div class="tag-list">
<span class="note">Rows with games {len(with_games)}</span><span class="note">Avg actual games {avg_games:.1f}</span><span class="note">Avg games error {avg_err:+.1f}</span><span class="note">Sets hit {sets_pct:.1f}%</span><span class="note">Tie-break rate {tb_pct:.1f}%</span>
</div></div>"""


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq = json_rows(read_json(OUTPUTS / "results" / "latest_results_corq.json", []))
    cloq = json_rows(read_json(OUTPUTS / "results" / "latest_results_cloq.json", []))
    all_rows = json_rows(read_json(OUTPUTS / "results" / "latest_results_all.json", []))
    combined = corq + cloq + all_rows
    body = [
        summary_cards_html(summarize_results(corq), "CorQ TOP7 Results"),
        summary_cards_html(summarize_results(cloq), "CloQ Results"),
        summary_cards_html(summarize_results(all_rows), "ALL Results Audit"),
        render_results_table(corq, "CorQ TOP7 Results"),
        render_results_table(cloq, "CloQ Results"),
        render_results_table(all_rows, "ALL Results Audit", limit=80),
        tag_analysis(combined),
        depth_analysis(combined),
        sets_games_audit(combined),
    ]
    return page_shell("Results", RESULTS_PATH, "\n".join(body), manifest)


def rss_items(rows: List[Dict[str, Any]], title: str) -> str:
    items = []
    for i, row in enumerate(rows[:20], 1):
        name = pick_name(row)
        desc = f"{i}. {name} | {as_pct(probability(row),1)} | {fmt_odds(pick_odds(row))}"
        items.append(f"<item><title>{esc(desc)}</title><description>{esc(desc)}</description></item>")
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(title)}</title><description>AI Betting by BackstageTalks</description>{''.join(items)}</channel></rss>"""


def render_all() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(OUTPUTS / "latest_manifest.json", {})
    top7 = json_rows(read_json(OUTPUTS / "latest_top7.json", []))
    all_rows = json_rows(read_json(OUTPUTS / "latest_all.json", []))
    cloq = json_rows(read_json(OUTPUTS / "latest_cloq.json", []))
    ensure_logs(top7 + all_rows + cloq)

    write_text(SITE_DIR / "index.html", page_shell("CorQ", "root", '<script>location.href="' + esc(TOP7_PATH) + '/"</script>', manifest))
    write_text(SITE_DIR / TOP7_PATH / "index.html", render_cards_page("CorQ", TOP7_PATH, top7, manifest, page="corq"))
    write_text(SITE_DIR / ALL_PATH / "index.html", render_cards_page("ALL Audit", ALL_PATH, all_rows, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / CLOQ_PATH / "index.html", render_cards_page("CloQ", CLOQ_PATH, cloq, manifest, page="cloq"))
    write_text(SITE_DIR / THINQ_PATH / "index.html", render_cards_page("ThinQ", THINQ_PATH, all_rows, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / RESULTS_PATH / "index.html", render_results_page(manifest))
    write_text(SITE_DIR / CORQ_RSS_PATH, rss_items(top7, "CorQ TOP7"))
    write_text(SITE_DIR / CLOQ_RSS_PATH, rss_items(cloq, "CloQ"))
    write_text(SITE_DIR / THINQ_RSS_PATH, rss_items(all_rows[:20], "ThinQ"))
    render_manifest = {
        "rendered_at": datetime.now(tz=timezone.utc).isoformat(),
        "top7_count": len(top7),
        "all_count": len(all_rows),
        "cloq_count": len(cloq),
        "site_root": str(SITE_DIR),
    }
    write_text(SITE_DIR / "render_manifest.json", json.dumps(render_manifest, ensure_ascii=False, indent=2))
    print(f"Rendered site: top7={len(top7)} all={len(all_rows)} cloq={len(cloq)} root={SITE_DIR}")


def main() -> None:
    render_all()


if __name__ == "__main__":
    main()
