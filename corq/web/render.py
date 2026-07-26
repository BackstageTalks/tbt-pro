from __future__ import annotations

import json
import html
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

try:
    from corq.messages import public_flag_labels
except Exception:  # pragma: no cover
    def public_flag_labels(flags):
        return []

try:
    from corq.web.tooltips import tooltip_icon, tooltip_css
except Exception:  # pragma: no cover
    def tooltip_icon(key: str, css_class: str = 'info-dot') -> str:
        return ''
    def tooltip_css() -> str:
        return ''

try:
    from corq.web.paths import (
        CORQ_PATH,
        CLOQ_PATH,
        ALL_PATH,
        RESULTS_PATH,
        THINQ_PATH,
        CORQ_RSS_PATH,
        CLOQ_RSS_PATH,
        THINQ_RSS_PATH,
        site_url,
    )
except Exception:  # fallback for older repos
    CORQ_PATH = "h4v34n1c3d4y180"
    CLOQ_PATH = "h4v34n1c3d4y181"
    ALL_PATH = "h4v34n1c3d4y182"
    RESULTS_PATH = "h4v34n1c3d4y183"
    THINQ_PATH = "h4v34n1c3d4y186"
    CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
    CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"
    THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"
    def site_url(path: str = "") -> str:
        base = os.getenv("TBTPRO_BASE_URL", "https://backstagetalks.github.io/tbt-pro/")
        return base.rstrip("/") + "/" + str(path).lstrip("/")

ROOT = Path(".")
OUTPUTS = ROOT / "outputs"
SITE_ROOT = ROOT / "corq" / "site"
LOGS_ROOT = SITE_ROOT / "logs"
WEB_ASSETS_ROOT = ROOT / "corq" / "web" / "assets"
HERO_PANELS_PATH = ROOT / "corq" / "web" / "hero_panels.json"
SITE_ASSETS_ROOT = SITE_ROOT / "assets"
BRATISLAVA_TZ = "Europe/Bratislava"


def load_json_first(paths: Iterable[Path], default: Any):
    for path in paths:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def latest_data():
    top7 = load_json_first([
        OUTPUTS / "latest_top7.json",
        OUTPUTS / "top7.json",
    ], [])
    all_rows = load_json_first([
        OUTPUTS / "latest_all.json",
        OUTPUTS / "all.json",
    ], [])
    manifest = load_json_first([
        OUTPUTS / "latest_manifest.json",
        OUTPUTS / "manifest.json",
    ], {})
    results = load_json_first([
        OUTPUTS / "latest_results.json",
        OUTPUTS / "results_latest.json",
        OUTPUTS / "results" / "latest_results.json",
    ], [])
    return as_list(top7), as_list(all_rows), manifest if isinstance(manifest, dict) else {}, as_list(results)


def as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("rows", "items", "top7", "all", "results"):
            if isinstance(value.get(key), list):
                return [x for x in value[key] if isinstance(x, dict)]
    return []


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def num(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        if isinstance(value, str) and value.strip() in {"", "—", "-"}:
            return default
        v = float(value)
        if math.isnan(v):
            return default
        return v
    except Exception:
        return default


def pct(value: Any, decimals: int = 1, signed: bool = False) -> str:
    v = num(value)
    if v is None:
        return "—"
    if abs(v) <= 1.5:
        v *= 100.0
    sign = "+" if signed and v > 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def pct_plain(value: Any, decimals: int = 1) -> str:
    v = num(value)
    if v is None:
        return "—"
    if abs(v) <= 1.5:
        v *= 100.0
    return f"{v:.{decimals}f}%"


def odds_fmt(value: Any) -> str:
    v = num(value)
    return "—" if v is None else f"{v:.2f}"


def prob_value(row: Dict[str, Any]) -> Optional[float]:
    for key in ("estimated_win_pct", "win_probability_pct", "corq_probability_pct", "probability_pct"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    for key in ("corq_estimated_win_probability", "win_probability", "corq_probability", "probability", "corq_score"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    return None


def thinq_prob(row: Dict[str, Any]) -> Optional[float]:
    for key in ("thinq_probability", "thinq_winner_probability"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    layer = row.get("thinq_probability_layer") or (row.get("thinq") or {}).get("probability_layer") or {}
    if isinstance(layer, dict):
        v = num(layer.get("probability") or layer.get("probability_pct"))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    return prob_value(row)


def nested(row: Dict[str, Any], *keys: str) -> Any:
    cur: Any = row
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def edge(row: Dict[str, Any], *names: str) -> Optional[float]:
    for name in names:
        candidates = [
            row.get(name),
            nested(row, "thinq", "edges", name),
            nested(row, "thinq", "elo", name),
            nested(row, "thinq", "recent_form", name),
            nested(row, "thinq", "match_dynamics", name),
        ]
        for c in candidates:
            v = num(c)
            if v is not None:
                return v
    return None


def record_value(row: Dict[str, Any], *names: str) -> str:
    rf = nested(row, "thinq", "recent_form") or {}
    for name in names:
        v = row.get(name)
        if v is None and isinstance(rf, dict):
            v = rf.get(name)
        if v not in (None, "", "—"):
            return str(v)
    return "—"



def wl_record(value: Any) -> str:
    """Format a win-loss record as 7W-3L."""
    if value in (None, "", "—"):
        return "—"
    text = str(value).strip()
    if not text or text == "—":
        return "—"
    if "W" in text.upper() and "L" in text.upper():
        return text
    m = re.search(r"(\d+)\s*[-/]\s*(\d+)", text)
    if m:
        return f"{int(m.group(1))}W-{int(m.group(2))}L"
    return text

def confidence_value(row: Dict[str, Any]) -> Optional[float]:
    for key in ("thinq_probability_confidence", "thinq_confidence", "confidence"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    layer = row.get("thinq_probability_layer") or nested(row, "thinq", "probability_layer") or {}
    if isinstance(layer, dict):
        v = num(layer.get("confidence"))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    v = num(nested(row, "thinq", "confidence"))
    return v / 100.0 if v and v > 1.5 else v


def form_conf_value(row: Dict[str, Any]) -> Optional[float]:
    for key in ("form_confidence", "thinq_form_confidence"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    v = num(nested(row, "thinq", "recent_form", "form_confidence"))
    return v / 100.0 if v and v > 1.5 else v


def data_depth_pct(row: Dict[str, Any]) -> Optional[float]:
    # Real pick/stat data depth. This must not merely copy overall ThinQ confidence.
    # Prefer runtime-computed fields first, then compute from Pick ThinQ Edge and ThinQ confidence.
    for key in ("stat_data_depth", "pick_data_depth", "top7_pick_data_depth", "thinq_selection_confidence", "selection_confidence", "data_depth_pct"):
        v = num(row.get(key))
        if v is not None:
            return v / 100.0 if v > 1.5 else v
    layer = row.get("thinq_selection") or nested(row, "thinq", "selection") or {}
    if isinstance(layer, dict):
        for key in ("pick_data_depth", "stat_data_depth", "selection_confidence", "data_depth_pct"):
            v = num(layer.get(key))
            if v is not None:
                return v / 100.0 if v > 1.5 else v
    e = edge(row, "pick_thinq_edge", "thinq_edge", "thinq_total_edge", "thinq_probability_edge")
    if e is None:
        tp = thinq_prob(row)
        e = None if tp is None else tp - 0.5
    conf = confidence_value(row)
    if e is None or conf is None or e <= 0:
        return 0.0
    return max(0.0, min(conf * min(e / 0.10, 1.0), 1.0))


def depth_label(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if v >= 0.70:
        return "Strong"
    if v >= 0.40:
        return "Medium"
    return "Low"


def depth_bar(v: Optional[float]) -> str:
    if v is None:
        return '<span class="depth-empty">—</span>'
    pctv = max(0.0, min(1.0, v))
    return (
        f'<span class="depth-wrap"><span class="depth-num">{pctv*100:.0f}%</span>'
        f'<span class="depth-bar" aria-label="Data depth {pctv*100:.0f}%">'
        f'<span class="depth-fill" style="width:{pctv*100:.0f}%"></span></span></span>'
    )


def edge_direction(value: Optional[float], zero: str = "0.0% / Neutral") -> str:
    if value is None:
        return "—"
    if abs(value) < 0.0005:
        return zero
    label = "Support" if value > 0 else "Against"
    return f"{pct(value, signed=True)} / {label}"


def signed_pair(a: Optional[float], b: Optional[float], invert: bool = False) -> str:
    if a is None and b is None:
        return "—"
    aa = -a if invert and a is not None else a
    bb = -b if invert and b is not None else b
    return f"{pct(aa, signed=True)} / {pct(bb, signed=True)}"


def side_class_for_pick(value: Optional[float]) -> str:
    if value is None or abs(value) < 0.0005:
        return "neutral"
    return "support" if value > 0 else "against"


def side_class_from_text(text: str) -> str:
    """Generic fallback classifier for normalized Support/Against text."""
    t = str(text or "").lower()
    if "against" in t:
        return "against"
    if "support" in t:
        return "support"
    if "neutral" in t:
        return "neutral"
    return "neutral"


def h2h_record_class_from_text(text: str) -> str:
    """Color H2H/S-H2H records from the current pick perspective."""
    t = str(text or "").strip()
    low = t.lower()
    if not t or t == "—" or "no data" in low or "no previous" in low:
        return "neutral"
    match = re.search(r"(\d+)\s*W\s*-\s*(\d+)\s*L", t, re.IGNORECASE)
    if match:
        pick_wins = int(match.group(1))
        opp_wins = int(match.group(2))
        if pick_wins > opp_wins:
            return "support"
        if pick_wins < opp_wins:
            return "against"
    edge_match = re.search(r"([+-]\d+(?:\.\d+)?)\s*%", t)
    if edge_match:
        edge_value = float(edge_match.group(1))
        if edge_value > 0:
            return "support"
        if edge_value < 0:
            return "against"
    return "neutral"


def row_html(label: str, value: str, cls: str = "") -> str:
    c = f" {cls}" if cls else ""
    return f'<div class="metric-row"><span>{label}</span><strong class="{esc(c.strip())}">{value}</strong></div>'


def h2h_summary(row: Dict[str, Any]) -> str:
    h2h = nested(row, "thinq", "h2h") or {}
    status = str(h2h.get("status") or row.get("thinq_h2h_status") or "").upper()
    total = num(h2h.get("total_matches") or row.get("thinq_h2h_total_matches"), 0) or 0
    pick_w = int(num(h2h.get("pick_wins") or row.get("thinq_h2h_pick_wins"), 0) or 0)
    opp_w = int(num(h2h.get("opponent_wins") or row.get("thinq_h2h_opponent_wins"), 0) or 0)
    e = edge(row, "h2h_edge")
    if total <= 0 or status in {"NO_DATA", "NO_PREVIOUS_MATCHES"}:
        return "No previous matches"
    edge_text = "0.0%" if e is None or abs(e) < 0.0005 else pct(e, signed=True)
    return f"{pick_w}W-{opp_w}L · {edge_text}"


def surface_h2h_summary(row: Dict[str, Any]) -> str:
    h2h = nested(row, "thinq", "h2h") or {}
    matches = int(num(h2h.get("same_surface_matches") or row.get("thinq_h2h_same_surface_matches"), 0) or 0)
    pick_w = int(num(h2h.get("same_surface_pick_wins") or row.get("thinq_h2h_same_surface_pick_wins"), 0) or 0)
    if matches <= 0:
        return "No data"
    opp_w = max(matches - pick_w, 0)
    return f"{pick_w}W-{opp_w}L"


def find_time(row: Dict[str, Any]) -> str:
    for key in ("match_time_display", "start_time_display", "time_display"):
        if row.get(key):
            return str(row[key])
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    candidates = [row.get("match_start"), row.get("start_time"), row.get("startTimestamp"), raw.get("startTimestamp")]
    for value in candidates:
        if not value:
            continue
        try:
            if isinstance(value, (int, float)):
                dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            else:
                text = str(value)
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                dt = datetime.fromisoformat(text)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(timezone.utc)
            if ZoneInfo:
                dt = dt.astimezone(ZoneInfo(BRATISLAVA_TZ))
            return dt.strftime("%H:%M")
        except Exception:
            continue
    return "—"


def log_key(row: Dict[str, Any], idx: int) -> str:
    base = str(row.get("event_id") or row.get("match_id") or row.get("id") or nested(row, "raw", "customId") or f"row-{idx}")
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-")[:80]
    return base or f"row-{idx}"


def write_log(row: Dict[str, Any], idx: int) -> str:
    key = log_key(row, idx)
    root = LOGS_ROOT / key
    root.mkdir(parents=True, exist_ok=True)
    log = {
        "match": {
            "pick": row.get("pick"),
            "opponent": row.get("opponent"),
            "player1": row.get("player1"),
            "player2": row.get("player2"),
            "event_id": row.get("event_id") or row.get("match_id"),
            "custom_id": row.get("event_custom_id") or row.get("customId") or nested(row, "raw", "customId"),
        },
        "thinq": row.get("thinq"),
        "thinq_flat": {k: v for k, v in row.items() if str(k).startswith("thinq_")},
        "corq_components": row.get("corq_components"),
        "raw": row.get("raw"),
        "full_record": row,
    }
    (root / "thinq-log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    pretty = f"""<!doctype html><html><head><meta charset='utf-8'><title>ThinQ log</title><style>body{{background:#06111f;color:#dbeafe;font-family:ui-monospace,Menlo,Consolas,monospace;padding:24px}}pre{{white-space:pre-wrap;background:#081827;border:1px solid #16324c;border-radius:14px;padding:18px}}</style></head><body><h1>ThinQ calculation log</h1><p>{esc(row.get('pick'))} vs {esc(row.get('opponent'))}</p><pre>{esc(json.dumps(log, indent=2, ensure_ascii=False))}</pre></body></html>"""
    (root / "index.html").write_text(pretty, encoding="utf-8")
    return f"logs/{key}/"


def pick_block(row: Dict[str, Any], idx: int) -> str:
    pick = row.get("pick") or row.get("player") or row.get("player1") or "—"
    opponent = row.get("opponent") or row.get("player2") or "—"
    odds = row.get("odds") or row.get("pick_odds")
    opp_odds = row.get("opponent_odds") or row.get("opp_odds")
    tournament = row.get("tournament") or nested(row, "raw", "tournament", "name") or "—"
    surface = row.get("surface") or row.get("surface_raw") or "—"
    level = row.get("level") or row.get("category") or "—"
    best_of = row.get("best_of") or row.get("bestOf") or "3"
    time = find_time(row)
    log_url = write_log(row, idx)
    return f"""
    <div class="pick-block">
      <div class="rank">#{idx}</div>
      <a class="brain" href="{esc(log_url)}" title="Open ThinQ calculation log">🧠</a>
      <div class="pick-name">{esc(pick)}</div>
      <div class="pick-odds">Pick @ {esc(odds_fmt(odds))}</div>
      <div class="pick-action">to beat</div>
      <div class="opp-name">{esc(opponent)}</div>
      <div class="opp-odds">Opp @ {esc(odds_fmt(opp_odds))}</div>
      <div class="meta">{esc(time)} · {esc(tournament)} · {esc(surface)} · BO{esc(best_of)}</div>
    </div>
    """


def corq_box(row: Dict[str, Any]) -> str:
    p = prob_value(row)
    probability = pct_plain(p)
    overall = edge(row, "overall_elo_edge", "elo_edge")
    surf = edge(row, "surface_elo_edge", "surface_edge")
    thinq_e = edge(row, "thinq_edge")
    if thinq_e is None:
        tp = thinq_prob(row)
        thinq_e = None if tp is None else tp - 0.5
    depth = data_depth_pct(row)
    h2h = h2h_summary(row)
    sh2h = surface_h2h_summary(row)
    return f"""
    <section class="metric-card corq-card">
      <header><span>CorQ {tooltip_icon('corq_box')}</span><strong>{esc(probability)}</strong></header>
      {row_html('Pick ELO / S-ELO', signed_pair(overall, surf), side_class_for_pick((overall or 0) + (surf or 0)))}
      {row_html('Opp ELO / S-ELO', signed_pair(overall, surf, invert=True), side_class_for_pick((overall or 0) + (surf or 0)))}
      {row_html('H2H P-O ' + tooltip_icon('h2h'), esc(h2h), h2h_record_class_from_text(h2h))}
      {row_html('S-H2H P-O ' + tooltip_icon('s_h2h'), esc(sh2h), h2h_record_class_from_text(sh2h))}
      {row_html('Pick ThinQ Edge', esc(edge_direction(thinq_e)), side_class_for_pick(thinq_e))}
      <div class="metric-row depth-row"><span>Stat Data Depth {tooltip_icon('pick_data_depth')}</span><strong>{depth_bar(depth)}</strong></div>
    </section>
    """


def thinq_form_box(row: Dict[str, Any]) -> str:
    conf = confidence_value(row)
    form_conf = form_conf_value(row)
    pick_form = wl_record(record_value(row, "pick_last10_record", "pick_form_record"))
    pick_sform = wl_record(record_value(row, "pick_surface_record", "pick_surface_last10_record"))
    opp_form = wl_record(record_value(row, "opponent_last10_record", "opp_last10_record", "opponent_form_record"))
    opp_sform = wl_record(record_value(row, "opponent_surface_record", "opp_surface_record", "opponent_surface_last10_record"))
    recent = edge(row, "recent_form_edge", "short_form_edge")
    surface = edge(row, "surface_recent_form_edge")
    quality = edge(row, "opponent_quality_edge")
    return f"""
    <section class="metric-card thinq-card">
      <header><span>ThinQ {tooltip_icon('thinq_box')}</span><strong>{esc(pct_plain(conf))}</strong></header>
      {row_html('Pick Form / S-Form ' + tooltip_icon('pick_form_sform'), esc(f'{pick_form} / {pick_sform}'))}
      {row_html('Opp Form / S-Form ' + tooltip_icon('opp_form_sform'), esc(f'{opp_form} / {opp_sform}'))}
      {row_html('Pick R-Edge ' + tooltip_icon('recent_edge'), esc(pct(recent, signed=True)), side_class_for_pick(recent))}
      {row_html('Pick S-Edge ' + tooltip_icon('surface_edge'), esc(pct(surface, signed=True)), side_class_for_pick(surface))}
      {row_html('Pick Form Qty ' + tooltip_icon('form_quality'), esc(pct(quality, signed=True)), side_class_for_pick(quality))}
      <div class="metric-row depth-row"><span>Form Data Depth {tooltip_icon('form_data_depth')}</span><strong>{depth_bar(form_conf)}</strong></div>
    </section>
    """


def sets_games_box(row: Dict[str, Any]) -> str:
    md = nested(row, "thinq", "match_dynamics") or {}
    def first(*keys):
        for k in keys:
            v = row.get(k)
            if v is None and isinstance(md, dict):
                v = md.get(k)
            if v not in (None, "", "—"):
                return v
        return None
    sets = first("thinq_projected_sets", "projected_sets")
    games = first("thinq_projected_games", "projected_games")
    decider = first("thinq_decider_probability", "decider_probability", "three_sets_probability")
    tb = first("thinq_tiebreak_probability", "tiebreak_probability")
    score = first("most_likely_score", "thinq_most_likely_score", "likely_score") or "2-0"
    line = first("games_line", "thinq_games_line") or 22.5
    over = first("games_over_probability", "thinq_games_over_probability")
    over_text = f"Over {num(line, 22.5):.2f} · {pct_plain(over)}" if over is not None else f"Over {num(line,22.5):.2f} · —"
    return f"""
    <section class="metric-card sets-card">
      <header><span>Sets / Games {tooltip_icon('sets_games')}</span></header>
      {row_html('Sets', esc('—' if sets is None else f'{num(sets):.2f}'))}
      {row_html('Games', esc('—' if games is None else f'{num(games):.1f}'))}
      {row_html('O/U', esc(over_text))}
      {row_html('3 Sets', esc(pct_plain(decider)))}
      {row_html('Score', esc(score))}
      {row_html('Tie-break', esc(pct_plain(tb)))}
    </section>
    """


def marq_box(row: Dict[str, Any]) -> str:
    source = row.get("odds_source") or row.get("source") or "RapidAPI PRO event odds"
    direction = str(row.get("odds_matching_direction") or "")
    if direction in {"DIRECT_BY_NUMERIC_OUTCOME", "REVERSED_BY_NUMERIC_OUTCOME"}:
        direction = "Confirmed"
    elif not direction:
        direction = "Pending"
    return f"""
    <section class="metric-card marq-card">
      <header><span>MarQ {tooltip_icon('marq_box')}</span></header>
      {row_html('Pick MarQ', '—')}
      {row_html('Opp MarQ', '—')}
      {row_html('Move', '—')}
      {row_html('Odds Source', esc(source))}
      {row_html('Direction', esc(direction))}
      {row_html('Market', 'view only')}
    </section>
    """


def has_missing_odds(row: Dict[str, Any]) -> bool:
    pick_odds = num(row.get("pick_odds") or row.get("odds") or row.get("selected_odds"))
    opp_odds = num(row.get("opponent_odds") or row.get("opp_odds") or row.get("opponent_price"))
    odds_pair_available = row.get("odds_pair_available")
    odds_status = str(row.get("odds_status") or row.get("odds_status_code") or "").upper()
    no_odds_reason = str(row.get("no_odds_reason") or "").upper()
    if pick_odds is None or opp_odds is None:
        return True
    if odds_pair_available is False:
        return True
    if odds_status in {"MISSING", "NO_ODDS", "NO_RAPIDAPI_PRO_ODDS"}:
        return True
    if "NO_ODDS" in no_odds_reason or "MISSING_ODDS" in no_odds_reason:
        return True
    return False


def public_notes(row: Dict[str, Any]) -> List[str]:
    flags: List[Any] = []
    for key in (
        "corq_risk_flags",
        "thinq_flags",
        "flags",
        "top7_reject_reasons",
        "top7_quality_reject_reasons",
        "cloq_reject_reasons",
    ):
        value = row.get(key)
        if isinstance(value, list):
            flags.extend(value)
    labels = list(public_flag_labels(flags))
    if has_missing_odds(row) and "Missing odds" not in labels:
        labels.insert(0, "Missing odds")
    seen = set()
    unique: List[str] = []
    for label in labels:
        text = str(label).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def tag_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        for label in public_notes(row):
            counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def tag_summary_html(rows: List[Dict[str, Any]]) -> str:
    counts = tag_counts(rows)
    if not counts:
        return ""
    chips = []
    for label, count in list(counts.items())[:18]:
        chips.append(f'<span class="tag-count"><b>{esc(count)}</b> {esc(label)}</span>')
    return (
        '<section class="notes-panel">'
        '<h3>Data notes summary</h3>'
        '<p>Counts of public data notes in the current ALL view.</p>'
        '<div class="tag-counts">' + ''.join(chips) + '</div>'
        '</section>'
    )


def odds_missing_reason_group(row: Dict[str, Any]) -> str:
    """Summarise missing-odds cause from odds_attempts for the ALL page.

    The exact API attempts stay in JSON/logs. The public ALL page needs a compact
    diagnostic bucket so we can quickly see whether missing odds are caused by
    coverage, provider emptiness, no match-winner market, daily-feed pairing, or
    event-id issues.
    """
    if not has_missing_odds(row):
        return ""

    attempts_raw = row.get("odds_attempts") or []
    if isinstance(attempts_raw, str):
        attempts = [attempts_raw]
    elif isinstance(attempts_raw, list):
        attempts = [str(x) for x in attempts_raw]
    else:
        attempts = []

    joined = " | ".join(attempts).lower()
    no_odds_reason = str(row.get("no_odds_reason") or "").lower()

    if not attempts and no_odds_reason:
        return "Legacy no-odds path"
    if not attempts:
        return "No odds audit"
    if "missing_event_id" in joined or "event_id" in no_odds_reason:
        return "Event id missing/mismatch"
    if "events_odds_by_date_match:no_match" in joined:
        # Daily feed exists, but the current event was not matched inside it.
        return "Daily odds no match"
    if "no_winner_market" in joined or "no_match_winner" in joined:
        return "No match-winner market"
    if "no_payload" in joined:
        return "Provider/API empty"
    if "http_404" in joined or "404" in joined:
        return "Event odds 404"
    if "timeout" in joined or "request failed" in joined or "error" in joined:
        return "API request error"
    return "Unknown missing odds"


def missing_odds_breakdown_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        reason = odds_missing_reason_group(row)
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def missing_odds_breakdown_html(rows: List[Dict[str, Any]]) -> str:
    counts = missing_odds_breakdown_counts(rows)
    if not counts:
        return ""
    chips = []
    for label, count in list(counts.items())[:12]:
        chips.append(f'<span class="tag-count odds-breakdown"><b>{esc(count)}</b> {esc(label)}</span>')
    return (
        '<section class="notes-panel odds-panel">'
        '<h3>Missing odds breakdown</h3>'
        '<p>Grouped reason buckets from odds_attempts in the current ALL view.</p>'
        '<div class="tag-counts">' + ''.join(chips) + '</div>'
        '</section>'
    )

def flag_badges(row: Dict[str, Any]) -> str:
    labels = public_notes(row)
    if not labels:
        return ""
    return '<div class="badges">' + ''.join(f'<span>{esc(x)}</span>' for x in labels[:4]) + '</div>'

def card(row: Dict[str, Any], idx: int, show_notes: bool = False) -> str:
    notes = flag_badges(row) if show_notes else ""
    return f"""
    <article class="match-card">
      {pick_block(row, idx)}
      <div class="metrics-grid">
        {corq_box(row)}
        {thinq_form_box(row)}
        {sets_games_box(row)}
        {marq_box(row)}
      </div>
      {notes}
    </article>
    """



def dedupe_all_display_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return one display card per match for the ALL page.

    ALL JSON can still keep HOME/AWAY candidate rows for audit, but the web ALL
    page should show each match once. The displayed side is the strongest current
    candidate for the match, ranked by publishable status, CorQ probability,
    Stat Data Depth, Pick ThinQ Edge, Form Data Depth and odds.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for row in rows:
        key = str(row.get("match_id") or row.get("event_id") or row.get("id") or "")
        if not key:
            p1 = str(row.get("player1") or row.get("home_player") or "").strip().lower()
            p2 = str(row.get("player2") or row.get("away_player") or "").strip().lower()
            start = str(row.get("match_start") or row.get("start_time") or "")
            key = "|".join(sorted([p1, p2]) + [start])
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    def score(row: Dict[str, Any]) -> tuple:
        publishable = 1 if row.get("top7_publishable") or row.get("eligible_for_top7") else 0
        corq = prob_value(row) or 0.0
        stat_depth = num(row.get("stat_data_depth") or row.get("pick_data_depth"), 0) or 0.0
        edge_value = num(row.get("top7_pick_thinq_edge") or row.get("thinq_edge"), 0) or 0.0
        form_depth = num(row.get("form_data_depth") or row.get("thinq_form_confidence"), 0) or 0.0
        odds_value = num(row.get("pick_odds") or row.get("odds"), 0) or 0.0
        return (publishable, corq, stat_depth, edge_value, form_depth, odds_value)

    output: List[Dict[str, Any]] = []
    for key in order:
        candidates = grouped[key]
        output.append(max(candidates, key=score))
    return output

def sort_by_probability(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: (prob_value(r) is not None, prob_value(r) or 0), reverse=True)




def load_hero_config() -> Dict[str, Any]:
    default = {
        "panels": [
            {"key": "snapshot", "title": "Snapshot", "lines": ["{page_label} · Updated {updated}", "TOP7 {top7_count} · ALL {all_count} · Ranked {ranked_count}"]},
            {"key": "promo", "title": "Promo / Partner", "lines": ["Editable content slot.", "Change this text in corq/web/hero_panels.json."]},
            {"key": "legal", "title": "Notice", "align": "right", "lines": ["This data is provided for informational and analytical purposes only.", "Powered by BackstageTalks Statistical Engine"]},
        ]
    }
    try:
        if HERO_PANELS_PATH.exists():
            data = json.loads(HERO_PANELS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("panels"), list):
                return data
    except Exception:
        pass
    return default


def hero_tokens(manifest: Dict[str, Any], page_label: str = "CorQ") -> Dict[str, str]:
    updated = manifest.get("updated") or manifest.get("run_started_at") or manifest.get("run_date") or "—"
    updated_text = str(updated)[:16].replace("T", " ") if updated else "—"
    return {
        "page_label": page_label,
        "updated": updated_text,
        "all_count": str(manifest.get("all_count", "—")),
        "ranked_count": str(manifest.get("ranked_count", "—")),
        "top7_count": str(manifest.get("top7_count", manifest.get("top7", "—"))),
        "safe_top7_count": str(manifest.get("safe_top7_count", "—")),
    }


def apply_hero_tokens(text_value: Any, tokens: Dict[str, str]) -> str:
    value = "" if text_value is None else str(text_value)
    for key, replacement in tokens.items():
        value = value.replace("{" + key + "}", replacement)
    return value


def hero_panels_html(manifest: Dict[str, Any], page_label: str = "CorQ") -> str:
    config = load_hero_config()
    tokens = hero_tokens(manifest, page_label=page_label)
    panels = []
    for panel in config.get("panels", [])[:3]:
        if not isinstance(panel, dict):
            continue
        title = apply_hero_tokens(panel.get("title", ""), tokens)
        lines = panel.get("lines") or []
        if not isinstance(lines, list):
            lines = [str(lines)]
        body_parts = []
        for line in lines:
            rendered = apply_hero_tokens(line, tokens)
            if rendered:
                body_parts.append(f'<p>{esc(rendered)}</p>')
        body = "".join(body_parts)
        key = re.sub(r"[^a-z0-9_-]+", "-", str(panel.get("key", "panel")).lower()).strip("-") or "panel"
        align = " right" if str(panel.get("align", "")).lower() == "right" else ""
        panels.append(f'<section class="hero-panel hero-{esc(key)}{align}"><h3>{esc(title)}</h3>{body}</section>')
    while len(panels) < 3:
        panels.append('<section class="hero-panel"><h3>Editable</h3><p>Update corq/web/hero_panels.json.</p></section>')
    return '<div class="hero-grid">' + ''.join(panels[:3]) + '</div>'

def brand_html() -> str:
    logo = site_url("assets/tbt_ai_goat_icon.png")
    return (
        '<div class="brand">'
        f'<img class="brand-logo" src="{esc(logo)}" alt="BackstageTalks AI logo">'
        '<div><div class="brand-title">BackstageTalks</div>'
        '<div class="brand-sub">Statistical Engine</div></div></div>'
    )


def nav_html(active: str = "top7") -> str:
    items = [
        ("top7", "CorQ", site_url(CORQ_PATH + "/")),
        ("all", "All", site_url(ALL_PATH + "/")),
        ("results", "Results", site_url(RESULTS_PATH + "/")),
        ("cloq", "CloQ", site_url(CLOQ_PATH + "/")),
        ("rss", "TG RSS", site_url(CORQ_RSS_PATH)),
    ]
    links = []
    for key, label, href in items:
        cls = "active" if key == active else ""
        links.append(f'<a class="{cls}" href="{esc(href)}">{esc(label)}</a>')
    return "<nav>" + "".join(links) + "</nav>"


def hero_copy(subtitle: str = "") -> str:
    lead = subtitle or "AI Betting by BackstageTalks"
    return (
        f'<p class="hero-lead">{esc(lead)}</p>'
        '<p class="hero-note">This data is provided for informational and analytical purposes only.</p>'
        '<p class="hero-powered">Powered by BackstageTalks Statistical Engine</p>'
    )


def prepare_assets() -> None:
    SITE_ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    src = WEB_ASSETS_ROOT / "tbt_ai_goat_icon.png"
    if src.exists():
        try:
            import shutil
            shutil.copyfile(src, SITE_ASSETS_ROOT / "tbt_ai_goat_icon.png")
        except Exception:
            pass

def page(title: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], subtitle: str = "", active: str = "top7") -> str:
    show_notes = active == "all"
    cards = "\n".join(card(row, i, show_notes=show_notes) for i, row in enumerate(rows, start=1)) or '<div class="empty">No rows available.</div>'
    all_tag_summary = tag_summary_html(rows) if show_notes else ""
    all_missing_odds_breakdown = missing_odds_breakdown_html(rows) if show_notes else ""
    updated = manifest.get("updated") or manifest.get("run_started_at") or manifest.get("run_date") or datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS + tooltip_css()}</style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      {brand_html()}
      {nav_html(active)}
    </header>
    {hero_panels_html(manifest, page_label=title)}
    <section class="summary">
      <div><span>ALL</span><strong>{esc(manifest.get('all_count', '—'))}</strong></div>
      <div><span>Ranked</span><strong>{esc(manifest.get('ranked_count', '—'))}</strong></div>
      <div><span>TOP7</span><strong>{esc(len(rows))}</strong></div>
      <div><span>Updated</span><strong>{esc(str(updated)[:16].replace('T',' '))}</strong></div>
    </section>
    <main class="cards">{cards}</main>
    {all_tag_summary}
    {all_missing_odds_breakdown}
  </div>
</body></html>"""


def all_page(rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> str:
    rows = dedupe_all_display_rows(rows)
    rows = sort_by_probability(rows)
    display_manifest = dict(manifest)
    display_manifest["all_display_count"] = len(rows)
    return page("All audit", rows, display_manifest, "Broad audit view. One card per match; full HOME/AWAY candidate rows stay visible in JSON/logs.", active="all")


def rss_xml(rows: List[Dict[str, Any]]) -> str:
    items = []
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    for row in sort_by_probability(rows)[:7]:
        pick = row.get("pick") or "—"
        opp = row.get("opponent") or "—"
        time = find_time(row)
        prob = pct_plain(prob_value(row))
        odds = odds_fmt(row.get("odds") or row.get("pick_odds"))
        desc = f"Time: {time} Pick: {pick} Opponent: {opp} Win probability: {prob} Odds: {odds} This data is provided for informational and analytical purposes only Powered by BackstageTalks Statistical Engine"
        items.append(f"<item><title>{esc(time)} | {esc(pick)} to beat {esc(opp)}</title><link>{esc(site_url(CORQ_PATH + '/'))}</link><description>{esc(desc)}</description><pubDate>{now}</pubDate></item>")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\"><channel><title>AI Betting by BackstageTalks</title><link>" + esc(site_url(CORQ_PATH + '/')) + "</link><description>CorQ TOP7</description>" + "".join(items) + "</channel></rss>"


def placeholder(title: str, body: str, active: str = "results") -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title><style>{CSS + tooltip_css()}</style></head><body><div class="shell"><header class="topbar">{brand_html()}{nav_html(active)}</header>{hero_panels_html({}, page_label=title)}</div></body></html>"""


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render():
    top7, all_rows, manifest, results = latest_data()
    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    prepare_assets()
    ordered_top7 = sort_by_probability(top7)[:7]
    write(SITE_ROOT / "index.html", f"<meta http-equiv='refresh' content='0; url={CORQ_PATH}/'>")
    write(SITE_ROOT / CORQ_PATH / "index.html", page("CorQ TOP7", ordered_top7, manifest, "AI Betting by BackstageTalks", active="top7"))
    write(SITE_ROOT / ALL_PATH / "index.html", all_page(all_rows or top7, manifest))
    write(SITE_ROOT / RESULTS_PATH / "index.html", placeholder("Results", "Results runtime will evaluate saved snapshots and show Today, Last 7 days, Current month and All time.", active="results"))
    write(SITE_ROOT / CLOQ_PATH / "index.html", placeholder("CloQ", "CloQ will be enabled after ThinQ probability is stable for close-odds selection.", active="cloq"))
    write(SITE_ROOT / THINQ_PATH / "index.html", placeholder("ThinQ", "ThinQ is an intelligence layer displayed inside CorQ cards.", active="top7"))
    write(SITE_ROOT / CORQ_RSS_PATH, rss_xml(ordered_top7))
    write(SITE_ROOT / CLOQ_RSS_PATH, rss_xml([]))
    write(SITE_ROOT / THINQ_RSS_PATH, rss_xml([]))
    print(f"TBT PRO site rendered: top7={len(ordered_top7)} all={len(all_rows)} root={SITE_ROOT}")


CSS = r'''
:root{--bg:#06111f;--panel:#0b1b2b;--panel2:#081827;--line:#16324c;--text:#e5f0ff;--muted:#89a3be;--green:#25f59a;--cyan:#28d7ff;--orange:#ffb35c;--red:#ff6b6b;}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#0b2540 0,#06111f 38%,#030914 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}.shell{max-width:1800px;margin:0 auto;padding:22px}.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.brand{display:flex;gap:12px;align-items:center}.brand-logo{width:54px;height:54px;border-radius:999px;object-fit:cover;object-position:center;border:1px solid rgba(125,211,252,.9);box-shadow:0 0 0 3px rgba(40,215,255,.10),0 0 18px rgba(40,215,255,.16),0 10px 24px rgba(0,0,0,.32);background:transparent;display:block}.hero-lead{margin:6px 0 0;color:#6ee7ff;font-size:14px}.hero-note,.hero-powered{margin:4px 0 0;color:var(--muted);font-size:12px}.hero-powered{color:#9bdfff}nav a.active{border-color:var(--cyan);box-shadow:0 0 0 1px rgba(40,215,255,.55),0 0 18px rgba(40,215,255,.12);color:#fff;background:rgba(8,31,51,.95)}.brand-title{font-size:17px;font-weight:800}.brand-sub{font-size:11px;color:var(--muted);letter-spacing:.09em;text-transform:uppercase}nav{display:flex;gap:8px;flex-wrap:wrap}nav a{color:#dff8ff;text-decoration:none;border:1px solid var(--line);background:#071827;border-radius:999px;padding:8px 13px;font-size:12px}nav a:hover{border-color:var(--cyan)}.hero-grid{display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:12px;margin-bottom:14px}.hero-panel{background:rgba(8,24,39,.58);border:1px solid rgba(22,50,76,.9);border-radius:18px;padding:13px 16px;min-height:74px}.hero-panel h3{margin:0 0 6px;color:#9ddcff;font-size:11px;text-transform:uppercase;letter-spacing:.10em}.hero-panel p{margin:3px 0;color:var(--muted);font-size:12px;line-height:1.45}.hero-panel.right{text-align:right}.hero-legal p:last-child{color:#9bdfff}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.summary div{background:var(--panel2);border:1px solid var(--line);border-radius:16px;padding:12px}.summary span{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.summary strong{font-size:20px}.cards{display:grid;gap:14px}.match-card{display:grid;grid-template-columns:250px minmax(0,1fr);gap:12px;background:rgba(6,17,31,.78);border:1px solid var(--line);border-radius:22px;padding:14px;box-shadow:0 10px 25px rgba(0,0,0,.22)}.pick-block{position:relative;background:var(--panel2);border:1px solid var(--line);border-radius:18px;padding:14px;min-height:220px}.rank{color:var(--cyan);font-weight:900;font-size:13px;margin-bottom:10px}.brain{position:absolute;right:12px;top:12px;text-decoration:none;color:#d2f7ff}.pick-name{font-weight:900;font-size:17px;line-height:1.2}.pick-odds{margin-top:6px;color:#ffe98d;font-weight:800;font-size:12px}.pick-action{text-transform:lowercase;color:var(--green);font-size:11px;letter-spacing:.06em;font-weight:900;margin-top:8px}.opp-name{margin-top:3px;color:#c9d7e8;font-weight:700}.opp-odds{margin-top:2px;color:var(--muted);font-size:12px}.meta{margin-top:12px;color:#6ee7ff;font-size:12px;line-height:1.35}.metrics-grid{display:grid;grid-template-columns:repeat(4,minmax(230px,1fr));gap:10px}.metric-card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:12px;min-height:220px}.metric-card header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:9px;color:#9ddcff;text-transform:uppercase;letter-spacing:.10em;font-size:11px}.metric-card header strong{font-size:16px;color:var(--green);letter-spacing:0;text-transform:none}.metric-row{display:grid;grid-template-columns:1.1fr 1fr;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid rgba(22,50,76,.37)}.metric-row:last-child{border-bottom:0}.metric-row span{color:var(--muted);font-size:12px}.metric-row strong{font-size:12px;text-align:right;color:#f5fbff}.metric-row strong.support{color:#f5fbff}.metric-row strong.against{color:var(--orange)}.metric-row strong.neutral{color:#d5e5f6}.depth-row strong{text-align:right}.depth-wrap{display:flex;align-items:center;justify-content:flex-end;gap:8px}.depth-num{font-size:12px;color:#e5f9ff}.depth-bar{display:inline-block;width:96px;height:16px;border:1px solid #7febff;border-radius:999px;background:#10263f;overflow:hidden;vertical-align:middle;box-shadow:inset 0 0 0 1px rgba(255,255,255,.08)}.depth-fill{display:block;height:100%;background:repeating-linear-gradient(135deg,#20c7d8 0 9px,#7af7ff 9px 13px);border-radius:999px}.badges{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap;margin-top:-4px}.badges span{font-size:11px;color:#ffd89b;background:rgba(255,179,92,.12);border:1px solid rgba(255,179,92,.35);border-radius:999px;padding:4px 8px}.empty{padding:40px;text-align:center;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:18px}
.notes-panel{margin-top:16px;background:rgba(8,24,39,.62);border:1px solid rgba(22,50,76,.92);border-radius:18px;padding:14px 16px}.notes-panel h3{margin:0 0 6px;color:#9ddcff;font-size:11px;text-transform:uppercase;letter-spacing:.10em}.notes-panel p{margin:0 0 10px;color:var(--muted);font-size:12px}.tag-counts{display:flex;gap:7px;flex-wrap:wrap}.tag-count{font-size:11px;color:#ffd89b;background:rgba(255,179,92,.12);border:1px solid rgba(255,179,92,.35);border-radius:999px;padding:5px 9px}.tag-count b{color:#fff;margin-right:4px}
@media(max-width:1300px){.match-card{grid-template-columns:1fr}.metrics-grid{grid-template-columns:repeat(2,minmax(240px,1fr))}}@media(max-width:720px){.summary{grid-template-columns:repeat(2,1fr)}.metrics-grid{grid-template-columns:1fr}.topbar{align-items:flex-start;flex-direction:column;gap:12px}.hero-grid{grid-template-columns:1fr}.hero-panel.right{text-align:left}}
'''

if __name__ == "__main__":
    render()
