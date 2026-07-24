from __future__ import annotations

import html
import json
import math
import os
import shutil
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from corq.web.paths import (
    ALL_PATH,
    CLOQ_PATH,
    CLOQ_RSS_PATH,
    CORQ_RSS_PATH,
    RESULTS_PATH,
    TG_RSS_PATH,
    THINQ_PATH,
    THINQ_RSS_PATH,
    TOP7_PATH,
    NAV_ITEMS,
    base_url,
    page_file,
    page_url,
)

OUTPUT_ROOT = Path("outputs")
SITE_ROOT = Path("corq/site")
ASSET_ROOT = Path("corq/web/assets")
SITE_ASSET_ROOT = SITE_ROOT / "assets"
LOGO_FILE = "tbt_ai_goat_icon.png"
RESULTS_DISPLAY_TIME_OFFSET_HOURS = int(os.getenv("RESULTS_DISPLAY_TIME_OFFSET_HOURS", "2"))
DEFAULT_GAMES_LINE = 22.5

CSS = """
:root{--bg:#070b12;--panel:#0d1422;--panel2:#111b2d;--line:#22314a;--text:#f8fafc;--muted:#94a3b8;--blue:#38bdf8;--green:#22c55e;--red:#fb7185;--yellow:#facc15;--orange:#fb923c}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% 0,#172542 0,#070b12 38%,#05070d 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}.page{max-width:1500px;margin:0 auto;padding:28px}header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}.brand h1{margin:0;font-size:32px;letter-spacing:-.045em}.brand p{margin:7px 0 0;color:var(--muted)}nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}nav a{color:#cbd5e1;text-decoration:none;border:1px solid var(--line);padding:9px 12px;border-radius:999px;font-size:12px;background:rgba(13,20,34,.72)}nav a.active{color:#07110b;background:var(--green);border-color:var(--green);font-weight:900}.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0 22px}.summary{background:linear-gradient(180deg,rgba(17,27,45,.96),rgba(13,20,34,.96));border:1px solid var(--line);border-radius:18px;padding:16px}.summary .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.summary .value{font-size:26px;font-weight:900;margin-top:4px}.notice{border:1px solid #92400e;background:rgba(120,53,15,.25);color:#fed7aa;padding:14px 16px;border-radius:16px;margin:16px 0}.match-list{display:flex;flex-direction:column;gap:14px}.match-card{display:grid;grid-template-columns:52px minmax(260px,1.25fr) 130px minmax(650px,2.45fr);gap:14px;align-items:stretch;background:rgba(13,20,34,.9);border:1px solid var(--line);border-radius:22px;padding:14px}.match-card.audit{grid-template-columns:52px minmax(260px,1.2fr) 130px minmax(760px,2.7fr)}.rank{font-size:18px;font-weight:900;color:var(--blue)}.pick-name{font-size:16px;font-weight:900}.pick-odds{margin-top:3px;color:var(--yellow);font-size:12px;font-weight:900}.pick-action{margin-top:5px;color:var(--green);font-size:11px;font-weight:900;text-transform:lowercase;letter-spacing:.05em}.opponent-name{margin-top:2px;color:#cbd5e1;font-size:13px;font-weight:700}.opponent-odds{color:var(--muted);font-size:11px;margin-top:1px}.match-meta{color:var(--blue);font-size:11px;margin-top:6px}.status-line{color:var(--muted);font-size:10px;margin-top:6px}.chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.chip{font-size:9px;border:1px solid var(--line);color:#cbd5e1;border-radius:999px;padding:3px 6px;background:#08101d}.score-box{border-radius:18px;border:1px solid var(--line);background:rgba(8,16,29,.95);padding:13px}.score-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em}.score-main{font-size:28px;margin-top:5px;font-weight:950}.score-sub{font-size:11px;color:#cbd5e1;margin-top:4px}.positive{color:var(--green)}.negative{color:var(--red)}.neutral{color:var(--muted)}.intel-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.intel-card{background:rgba(8,16,29,.86);border:1px solid var(--line);border-radius:18px;padding:12px}.intel-title{font-size:10px;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}.kv{display:flex;justify-content:space-between;gap:8px;font-size:11px;border-top:1px solid rgba(34,49,74,.55);padding-top:6px;margin-top:6px}.kv span{color:#94a3b8}.kv strong{text-align:right;color:#f8fafc}.mini-audit{margin-top:8px;color:#64748b;font-size:10px}.blockers{grid-column:1/-1;display:flex;gap:8px;flex-wrap:wrap}.blockers span{font-size:10px;border:1px solid #7f1d1d;color:#fecaca;border-radius:999px;padding:3px 7px;background:rgba(127,29,29,.35)}table{width:100%;border-collapse:collapse;background:rgba(13,20,34,.82);border:1px solid var(--line);border-radius:18px;overflow:hidden}th,td{text-align:left;padding:10px;border-bottom:1px solid rgba(34,49,74,.65);font-size:12px}th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;background:rgba(8,16,29,.9)}td{color:#e2e8f0}.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin:26px 0 12px}.section-title h2{margin:0}.rss-box{background:rgba(8,16,29,.88);border:1px solid var(--line);border-radius:18px;padding:14px;margin:16px 0;color:#cbd5e1;font-size:12px}footer{color:#64748b;font-size:11px;margin-top:28px}
.logo-brand{display:flex;align-items:center;gap:14px}.logo-brand img{width:58px;height:58px;border-radius:50%;object-fit:cover;border:1px solid rgba(56,189,248,.55);box-shadow:0 0 20px rgba(56,189,248,.18)}.brand-kicker{color:#38bdf8;font-size:12px;text-transform:uppercase;letter-spacing:.16em;font-weight:800}.brand h1.compact-title{font-size:24px;margin-top:2px}.brand p.compact-subtitle{font-size:12px;margin-top:2px}.hero-compact{align-items:center}.cards.compact-cards{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:8px}.summary:first-child.hide-candidate{display:none}.rss-box a{color:#f8fafc;text-decoration:none}.rss-pill{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:5px 9px;background:#08101d;margin-left:8px}.subtle-chip{opacity:.58}.corq-card{border-color:rgba(56,189,248,.38)}

"""


def esc(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def pct(value: Any, signed: bool = False, default: str = "—") -> str:
    val = as_float(value)
    if val is None:
        return default
    if abs(val) <= 1.0000001:
        val = val * 100
    prefix = "+" if signed and val > 0 else ""
    return f"{prefix}{val:.1f}%"


def money(value: Any) -> str:
    val = as_float(value)
    if val is None:
        return "—"
    return f"{val:.2f}".rstrip("0").rstrip(".")


def bratislava_tz():
    if ZoneInfo is not None:
        return ZoneInfo("Europe/Bratislava")
    return timezone(timedelta(hours=RESULTS_DISPLAY_TIME_OFFSET_HOURS))


def local_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(bratislava_tz())
    except Exception:
        return None


def short_time(row: Dict[str, Any]) -> str:
    raw = first_present(row.get("match_start"), row.get("start_time"), row.get("time"))
    dt = local_datetime(raw)
    if dt is not None:
        return dt.strftime("%H:%M")
    if not raw:
        return "—"
    return str(raw)[:5]


def local_today() -> str:
    return datetime.now(timezone.utc).astimezone(bratislava_tz()).strftime("%d.%m.%Y")


def pubdate(row: Optional[Dict[str, Any]] = None) -> str:
    raw = None
    if row:
        raw = first_present(row.get("published_at"), row.get("created_at"), row.get("snapshot_time"), row.get("generated_at"))
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return format_datetime(dt.astimezone(timezone.utc), usegmt=True)
    except Exception:
        return format_datetime(datetime.now(timezone.utc), usegmt=True)


def thinq(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("thinq") if isinstance(row.get("thinq"), dict) else {}


def match_dynamics(row: Dict[str, Any]) -> Dict[str, Any]:
    t = thinq(row)
    if isinstance(t.get("match_dynamics"), dict):
        return t["match_dynamics"]
    if isinstance(t.get("contexts"), dict) and isinstance(t["contexts"].get("match_dynamics"), dict):
        return t["contexts"]["match_dynamics"]
    return {}


def h2h(row: Dict[str, Any]) -> Dict[str, Any]:
    t = thinq(row)
    return t.get("h2h") if isinstance(t.get("h2h"), dict) else {}


def elo(row: Dict[str, Any]) -> Dict[str, Any]:
    t = thinq(row)
    return t.get("elo") if isinstance(t.get("elo"), dict) else {}


def edge_label(value: Any) -> str:
    val = as_float(value)
    if val is None:
        return "—"
    return pct(val, signed=True)


def value_class(value: Any) -> str:
    val = as_float(value)
    if val is None or abs(val) < 0.00001:
        return "neutral"
    return "positive" if val > 0 else "negative"


def probability_value(row: Dict[str, Any], prefix: str) -> Optional[float]:
    candidates = []
    if prefix == "corq":
        candidates = [row.get("corq_probability"), row.get("corq_estimated_win_probability"), row.get("corq_score"), row.get("estimated_win_pct")]
    elif prefix == "thinq":
        t = thinq(row)
        candidates = [row.get("thinq_probability"), row.get("thinq_ai_probability"), t.get("win_probability"), t.get("probability"), t.get("score")]
    elif prefix == "cloq":
        candidates = [row.get("cloq_probability"), row.get("cloq_ai_probability"), row.get("cloq_score")]
    elif prefix == "marq_pick":
        candidates = [row.get("marq_pick_probability"), row.get("marq_pick_marq"), row.get("marq_pick")]
    elif prefix == "marq_opponent":
        candidates = [row.get("marq_opponent_probability"), row.get("marq_opp_marq"), row.get("marq_opponent")]
    for c in candidates:
        val = as_float(c)
        if val is not None:
            return val / 100.0 if val > 1 else val
    return None


def win_probability(row: Dict[str, Any]) -> Optional[float]:
    val = first_present(row.get("win_probability"), row.get("estimated_win_pct"), row.get("corq_estimated_win_probability"), row.get("corq_score"))
    f = as_float(val)
    if f is None:
        return None
    return f / 100.0 if f > 1 else f




def display_probability(row: Dict[str, Any]) -> float:
    val = probability_value(row, "corq")
    if val is None:
        val = win_probability(row)
    return as_float(val, 0.0) or 0.0


def sort_by_probability(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=display_probability, reverse=True)

def ai_match(row: Dict[str, Any]) -> str:
    existing = first_present(row.get("ai_match"), row.get("ai_match_pct"), row.get("agreement_score"))
    if existing is not None:
        return pct(existing)
    c = probability_value(row, "corq")
    t = probability_value(row, "thinq")
    if c is None or t is None:
        return "—"
    return pct(max(0.0, 1.0 - abs(c - t)))


def ai_difference(row: Dict[str, Any]) -> str:
    existing = row.get("ai_difference")
    if existing:
        return str(existing)
    c = probability_value(row, "corq")
    t = probability_value(row, "thinq")
    if c is None or t is None:
        return "—"
    diff = c - t
    label = "Corq" if diff >= 0 else "Thinq"
    return f"{label} {pct(abs(diff), signed=True)}"


def games_line(row: Dict[str, Any]) -> float:
    return as_float(first_present(row.get("games_line"), row.get("total_games_line"), row.get("market_games_line")), DEFAULT_GAMES_LINE) or DEFAULT_GAMES_LINE


def games_over_probability(row: Dict[str, Any]) -> Optional[float]:
    md = match_dynamics(row)
    direct = first_present(row.get("games_over_probability"), row.get("over_games_probability"), md.get("games_over_probability"))
    val = as_float(direct)
    if val is not None:
        return val / 100.0 if val > 1 else val
    projected = as_float(first_present(md.get("projected_games"), row.get("thinq_projected_games")))
    if projected is None:
        return None
    # Conservative display-only estimate around the line. This is not a model signal.
    return max(0.05, min(0.95, 0.50 + (projected - games_line(row)) * 0.04))


def most_likely_score(row: Dict[str, Any]) -> str:
    existing = first_present(row.get("most_likely_score"), row.get("projected_score"))
    if existing:
        return str(existing)
    md = match_dynamics(row)
    decider = as_float(md.get("decider_probability"))
    straight = as_float(md.get("straight_sets_probability"))
    if decider is None and straight is None:
        return "—"
    if decider is not None and decider >= 0.50:
        return "2-1"
    if straight is not None and straight >= 0.50:
        return "2-0"
    return "2-1"


def meta(row: Dict[str, Any]) -> str:
    bits = [short_time(row), row.get("tournament"), row.get("surface"), f"BO{row.get('best_of') or '—'}"]
    return " · ".join(str(x) for x in bits if x not in (None, "", "—"))


def flags(row: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("corq_risk_flags", "top7_reject_reasons", "corq_reject_reasons", "thinq_flags"):
        val = row.get(key)
        if isinstance(val, list):
            out.extend(str(v) for v in val)
    t = thinq(row)
    if isinstance(t.get("flags"), list):
        out.extend(str(v) for v in t["flags"])
    return sorted(set(out))


def web_publish_blockers(row: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if str(row.get("status_type") or "").lower() not in {"notstarted", "not_started", "scheduled", "prematch", "open", "upcoming"}:
        blockers.append("WEB_BLOCK_STATUS_NOT_PREMATCH")
    if row.get("is_doubles"):
        blockers.append("WEB_BLOCK_DOUBLES")
    if not row.get("odds") and not row.get("pick_odds"):
        blockers.append("WEB_BLOCK_MISSING_ODDS")
    if not row.get("pick") or not row.get("opponent"):
        blockers.append("WEB_BLOCK_MISSING_PLAYERS")
    return blockers


def pick_block(row: Dict[str, Any]) -> str:
    visible_flags = []
    for flag in flags(row)[:6]:
        # Keep audit flags visible but less dominant on TOP7 cards.
        visible_flags.append(flag)
    chip_html = "".join(f"<span class='chip subtle-chip'>{esc(flag)}</span>" for flag in visible_flags)
    return (
        f"<div class='pick-block'><div class='pick-name'>{esc(row.get('pick'))}</div>"
        f"<div class='pick-odds'>Pick @ {esc(money(row.get('odds') or row.get('pick_odds')))}</div>"
        f"<div class='pick-action'>to beat</div><div class='opponent-name'>{esc(row.get('opponent'))}</div>"
        f"<div class='opponent-odds'>Opp @ {esc(money(row.get('opponent_odds')))}</div>"
        f"<div class='match-meta'>{esc(meta(row))}</div>"
        f"<div class='status-line'>Status: {esc(row.get('status_type') or 'unknown')} · Side: {esc(row.get('side_orientation') or '—')}</div>"
        f"<div class='chips'>{chip_html}</div></div>"
    )


def score_block(row: Dict[str, Any]) -> str:
    wp = win_probability(row)
    edge = row.get("corq_edge")
    return (
        "<div class='score-box'>"
        "<div class='score-label'>Win probability</div>"
        f"<div class='score-main'>{esc(pct(wp))}</div>"
        f"<div class='score-sub'>Odds {esc(money(row.get('odds') or row.get('pick_odds')))}</div>"
        f"<div class='score-sub'>Edge <span class='{value_class(edge)}'>{esc(edge_label(edge))}</span></div>"
        f"<div class='score-sub'>Source rank {esc(row.get('corq_source_rank') or row.get('corq_rank') or '—')}</div>"
        "</div>"
    )


def corq_block(row: Dict[str, Any]) -> str:
    edge = row.get("corq_edge")
    return (
        "<div class='intel-card corq-card'><div class='intel-title'>CORQ</div>"
        f"<div class='kv'><span>Probability</span><strong>{esc(pct(win_probability(row)))}</strong></div>"
        f"<div class='kv'><span>Corq AI</span><strong>{esc(pct(probability_value(row, 'corq')))}</strong></div>"
        f"<div class='kv'><span>Edge</span><strong class='{value_class(edge)}'>{esc(edge_label(edge))}</strong></div>"
        f"<div class='kv'><span>Odds</span><strong>{esc(money(row.get('odds') or row.get('pick_odds')))}</strong></div>"
        f"<div class='kv'><span>Source rank</span><strong>{esc(row.get('corq_source_rank') or row.get('corq_rank') or '—')}</strong></div>"
        "</div>"
    )


def thinq_block(row: Dict[str, Any]) -> str:
    e = elo(row)
    hh = h2h(row)
    t = thinq(row)
    recent = t.get("recent_form") if isinstance(t.get("recent_form"), dict) else {}
    return (
        "<div class='intel-card'><div class='intel-title'>THINQ</div>"
        f"<div class='kv'><span>ELO</span><strong>{esc(edge_label(first_present(e.get('elo_edge'), row.get('thinq_elo_edge'))))}</strong></div>"
        f"<div class='kv'><span>Surface ELO</span><strong>{esc(edge_label(first_present(e.get('surface_elo_edge'), row.get('thinq_surface_elo_edge'))))}</strong></div>"
        f"<div class='kv'><span>H2H Status</span><strong>{esc(hh.get('status') or row.get('thinq_h2h_status') or 'NO_DATA')}</strong></div>"
        f"<div class='kv'><span>H2H Edge</span><strong>{esc(edge_label(first_present(hh.get('edge'), row.get('thinq_h2h_edge'))))}</strong></div>"
        f"<div class='kv'><span>Recent Form</span><strong>{esc(recent.get('status') or 'NO_DATA')}</strong></div>"
        f"<div class='kv'><span>Confidence</span><strong>{esc(pct(row.get('thinq_confidence') or t.get('confidence')))}</strong></div>"
        "</div>"
    )


def sets_games_block(row: Dict[str, Any]) -> str:
    md = match_dynamics(row)
    return (
        "<div class='intel-card'><div class='intel-title'>SETS / GAMES</div>"
        f"<div class='kv'><span>Projected Sets</span><strong>{esc(first_present(md.get('projected_sets'), row.get('thinq_projected_sets')))}</strong></div>"
        f"<div class='kv'><span>Projected Games</span><strong>{esc(first_present(md.get('projected_games'), row.get('thinq_projected_games')))}</strong></div>"
        f"<div class='kv'><span>Match Shape</span><strong>{esc(first_present(md.get('match_shape'), row.get('thinq_match_shape')))}</strong></div>"
        f"<div class='kv'><span>3 Sets</span><strong>{esc(pct(first_present(md.get('decider_probability'), row.get('thinq_decider_probability'))))}</strong></div>"
        f"<div class='kv'><span>Most likely score</span><strong>{esc(most_likely_score(row))}</strong></div>"
        f"<div class='kv'><span>Games line</span><strong>{esc(games_line(row))}</strong></div>"
        f"<div class='kv'><span>Games over</span><strong>{esc(pct(games_over_probability(row)))}</strong></div>"
        f"<div class='kv'><span>Tie-break</span><strong>{esc(pct(first_present(md.get('tiebreak_probability'), row.get('thinq_tiebreak_probability'))))}</strong></div>"
        "</div>"
    )


def marq_block(row: Dict[str, Any]) -> str:
    move = first_present(row.get("marq_move"), row.get("marq_market_move"), row.get("market_move"), "—")
    return (
        "<div class='intel-card'><div class='intel-title'>MARQ</div>"
        f"<div class='kv'><span>Pick Marq</span><strong>{esc(pct(probability_value(row, 'marq_pick')))}</strong></div>"
        f"<div class='kv'><span>Opp Marq</span><strong>{esc(pct(probability_value(row, 'marq_opponent')))}</strong></div>"
        f"<div class='kv'><span>Move</span><strong>{esc(move)}</strong></div>"
        f"<div class='kv'><span>Odds Source</span><strong>{esc(row.get('odds_source') or '—')}</strong></div>"
        f"<div class='kv'><span>Direction</span><strong>{esc(row.get('odds_matching_direction') or '—')}</strong></div>"
        "<div class='mini-audit'>Market view only</div></div>"
    )


def row_card(row: Dict[str, Any], rank: int, audit: bool = False) -> str:
    blockers = row.get("web_publish_blockers") or (web_publish_blockers(row) if audit else [])
    blocker_html = ""
    if blockers:
        blocker_html = "<div class='blockers'>" + "".join(f"<span>{esc(b)}</span>" for b in blockers) + "</div>"
    cls = "match-card audit" if audit else "match-card"
    return f"<article class='{cls}'><div class='rank'>#{rank}</div>{pick_block(row)}{score_block(row)}<div class='intel-grid'>{corq_block(row)}{thinq_block(row)}{sets_games_block(row)}{marq_block(row)}</div>{blocker_html}</article>"


def nav(active: str) -> str:
    links = []
    for item in NAV_ITEMS:
        path = item["path"]
        href = f"../{path}" if path.endswith(".xml") else f"../{path}/"
        cls = "active" if item["key"] == active else ""
        links.append(f"<a class='{cls}' href='{href}'>{esc(item['label'])}</a>")
    return "<nav>" + "".join(links) + "</nav>"


def html_page(active: str, title: str, subtitle: str, body: str, summary: Dict[str, Any]) -> str:
    updated = str(summary.get("updated") or datetime.now(timezone.utc).isoformat())
    cards = [
        ("ALL", summary.get("all_count", "—")),
        ("Ranked", summary.get("ranked_count", "—")),
        ("TOP7", summary.get("top7_count", "—")),
        ("Updated", updated[:16].replace("T", " ")),
    ]
    cards_html = "".join(f"<div class='summary'><div class='label'>{esc(label)}</div><div class='value'>{esc(value)}</div></div>" for label, value in cards)
    logo_src = "../assets/" + LOGO_FILE
    header_title = title.replace("TBT PRO ", "")
    header = (
        "<header class='hero-compact'><div class='brand logo-brand'>"
        f"<img src='{esc(logo_src)}' alt='TBT PRO logo'/>"
        "<div><div class='brand-kicker'>BackstageTalks Statistical Engine</div>"
        f"<h1 class='compact-title'>{esc(header_title)}</h1>"
        f"<p class='compact-subtitle'>{esc(subtitle)}</p></div></div>{nav(active)}</header>"
    )
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/><title>{esc(title)}</title><style>{CSS}</style></head><body><div class='page'>{header}<section class='cards compact-cards'>{cards_html}</section>{body}<footer>This data is provided for informational and analytical purposes only · Powered by BackstageTalks Statistical Engine</footer></div></body></html>"


def write_page(path_key: str, content: str) -> None:
    target = SITE_ROOT / page_file(path_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

def write_assets() -> None:
    SITE_ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    source = ASSET_ROOT / LOGO_FILE
    if source.exists():
        shutil.copyfile(source, SITE_ASSET_ROOT / LOGO_FILE)

def write_root_index() -> None:
    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    top7_href = f"{TOP7_PATH}/"
    rss_href = TG_RSS_PATH
    content = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/><meta http-equiv='refresh' content='0; url={top7_href}'/><title>TBT PRO</title><style>{CSS}</style></head><body><div class='page'><header><div class='brand'><h1>TBT PRO</h1><p>BackstageTalks Statistical Engine</p></div></header><div class='notice'>Redirecting to TOP7. If redirect does not start, open <a href='{top7_href}'>TOP7</a>. Telegram RSS: <a href='{rss_href}'>{rss_href}</a>.</div></div></body></html>"""
    (SITE_ROOT / "index.html").write_text(content, encoding="utf-8")


def table_page(rows: List[Dict[str, Any]], title: str) -> str:
    if not rows:
        return "<div class='notice'>No rows available.</div>"
    head = "<tr><th>#</th><th>Time</th><th>Pick</th><th>Opponent</th><th>Win %</th><th>Odds</th><th>AI Match</th><th>Projected Sets</th><th>Projected Games</th><th>Status</th><th>Reject Flags</th></tr>"
    body = []
    for idx, row in enumerate(rows, 1):
        md = match_dynamics(row)
        body.append(
            "<tr>"
            f"<td>{idx}</td><td>{esc(short_time(row))}</td><td>{esc(row.get('pick'))}</td><td>{esc(row.get('opponent'))}</td>"
            f"<td>{esc(pct(win_probability(row)))}</td><td>{esc(money(row.get('odds') or row.get('pick_odds')))}</td><td>{esc(ai_match(row))}</td>"
            f"<td>{esc(first_present(md.get('projected_sets'), row.get('thinq_projected_sets')))}</td><td>{esc(first_present(md.get('projected_games'), row.get('thinq_projected_games')))}</td>"
            f"<td>{esc(row.get('status_type'))}</td><td>{esc(', '.join(flags(row)[:5]))}</td></tr>"
        )
    return f"<div class='section-title'><h2>{esc(title)}</h2><span>{len(rows)} rows</span></div><table>{head}{''.join(body)}</table>"


def load_results() -> List[Dict[str, Any]]:
    candidates = [
        OUTPUT_ROOT / "latest_results.json",
        OUTPUT_ROOT / "results_latest.json",
        OUTPUT_ROOT / "results" / str(datetime.now(timezone.utc).year) / "results_latest.json",
    ]
    for path in candidates:
        data = load_json(path, None)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
    return []


def results_body(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "<div class='notice'>Results file not found yet. This page is ready for the Results workflow and will auto-populate from outputs/latest_results.json or outputs/results/YYYY/results_latest.json.</div>"
    head = "<tr><th>Time</th><th>Pick</th><th>Opponent</th><th>Status</th><th>Winner</th><th>Score</th><th>Projected Sets</th><th>Projected Games</th><th>Units</th></tr>"
    body = []
    for row in results:
        body.append(
            "<tr>"
            f"<td>{esc(short_time(row))}</td><td>{esc(row.get('pick'))}</td><td>{esc(row.get('opponent'))}</td>"
            f"<td>{esc(row.get('result_status') or row.get('status') or row.get('bet_status'))}</td><td>{esc(row.get('winner') or row.get('actual_winner'))}</td>"
            f"<td>{esc(row.get('score') or row.get('actual_score'))}</td><td>{esc(row.get('projected_sets') or row.get('thinq_projected_sets'))}</td>"
            f"<td>{esc(row.get('projected_games') or row.get('thinq_projected_games'))}</td><td>{esc(row.get('units'))}</td></tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def rss_description(row: Dict[str, Any]) -> str:
    md = match_dynamics(row)
    e = elo(row)
    hh = h2h(row)
    t = thinq(row)
    recent = t.get("recent_form") if isinstance(t.get("recent_form"), dict) else {}
    parts = [
        f"Time: {short_time(row)}",
        f"Pick: {row.get('pick') or '—'}",
        f"Opponent: {row.get('opponent') or '—'}",
        f"Tournament: {row.get('tournament') or '—'}",
        f"Surface: {row.get('surface') or '—'}",
        f"Best of: {row.get('best_of') or '—'}",
        f"Win probability: {pct(win_probability(row))}",
        f"Odds: {money(row.get('odds') or row.get('pick_odds'))}",
        f"CorQ: {pct(probability_value(row, 'corq'))}",
        "ThinQ summary:",
        f"ELO: {edge_label(first_present(e.get('elo_edge'), row.get('thinq_elo_edge')))}",
        f"Surface ELO: {edge_label(first_present(e.get('surface_elo_edge'), row.get('thinq_surface_elo_edge')))}",
        f"H2H: {hh.get('status') or row.get('thinq_h2h_status') or 'NO_DATA'}",
        f"H2H Edge: {edge_label(first_present(hh.get('edge'), row.get('thinq_h2h_edge')))}",
        f"Form: {recent.get('status') or 'NO_DATA'}",
        f"Confidence: {pct(row.get('thinq_confidence') or t.get('confidence'))}",
        f"Expected sets: {first_present(md.get('projected_sets'), row.get('thinq_projected_sets'), '—')}",
        f"3 Sets: {pct(first_present(md.get('decider_probability'), row.get('thinq_decider_probability')))}",
        f"Most likely score: {most_likely_score(row)}",
        f"Games line: {games_line(row)}",
        f"Games over probability: {pct(games_over_probability(row))}",
        f"Tie-break probability: {pct(first_present(md.get('tiebreak_probability'), row.get('thinq_tiebreak_probability')))}",
        f"MARQ Pick Marq: {pct(probability_value(row, 'marq_pick'))}",
        f"MARQ Opp Marq: {pct(probability_value(row, 'marq_opponent'))}",
        f"MARQ Move: {first_present(row.get('marq_move'), row.get('marq_market_move'), row.get('market_move'), '—')}",
        "This data is provided for informational and analytical purposes only",
        "Powered by BackstageTalks Statistical Engine",
    ]
    return " ".join(str(p) for p in parts)


def full_link() -> str:
    return base_url()


def rss_feed(rows: List[Dict[str, Any]], title: str = "TBT PRO TOP7 Telegram RSS") -> str:
    now = pubdate()
    items = []
    for row in sort_by_probability(rows)[:20]:
        title_text = f"{short_time(row)} | {row.get('pick') or '—'} to beat {row.get('opponent') or '—'}"
        desc = rss_description(row)
        link = full_link()
        guid = str(first_present(row.get('event_id'), row.get('match_id'), row.get('id'), title_text))
        items.append(
            "<item>"
            f"<title>{esc(title_text)}</title>"
            f"<link>{esc(link)}</link>"
            f"<description>{esc(desc)}</description>"
            f"<pubDate>{pubdate(row)}</pubDate>"
            f"<guid isPermaLink='false'>{esc(guid)}</guid>"
            "</item>"
        )
    return f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>{esc(title)}</title><link>{esc(full_link())}</link><description>BackstageTalks Statistical Engine TOP7 feed for Telegram</description><lastBuildDate>{now}</lastBuildDate>{''.join(items)}</channel></rss>"


def render() -> Dict[str, Any]:
    top7_raw = load_json(OUTPUT_ROOT / "latest_top7.json", [])
    all_raw = load_json(OUTPUT_ROOT / "latest_all.json", [])
    manifest = load_json(OUTPUT_ROOT / "latest_manifest.json", {})
    if not isinstance(top7_raw, list):
        top7_raw = []
    if not isinstance(all_raw, list):
        all_raw = []
    if not isinstance(manifest, dict):
        manifest = {}

    results = load_results()
    safe_top7 = sort_by_probability([row for row in top7_raw if not web_publish_blockers(row)])
    blocked_top7 = [dict(row, web_publish_blockers=web_publish_blockers(row)) for row in top7_raw if web_publish_blockers(row)]
    all_rows = all_raw if all_raw else top7_raw

    summary = {
        "candidate_count": manifest.get("candidate_count", "—"),
        "all_count": manifest.get("all_count", len(all_rows)),
        "ranked_count": manifest.get("ranked_count", len(top7_raw)),
        "top7_count": len(safe_top7),
        "updated": manifest.get("finished_at_utc") or datetime.now(timezone.utc).isoformat(),
    }

    rss_url = page_url(TG_RSS_PATH) or f"../{TG_RSS_PATH}"
    top_body = "<div class='rss-box'>Telegram RSS feed <a class='rss-pill' href='" + esc(rss_url) + "'>Open RSS</a></div>"
    top_body += ("<div class='match-list'>" + "".join(row_card(row, idx + 1) for idx, row in enumerate(safe_top7)) + "</div>") if safe_top7 else "<div class='notice'>No publication-safe TOP7 picks.</div>"
    if blocked_top7:
        top_body += "<div class='section-title'><h2>Blocked TOP7 audit</h2></div><div class='match-list'>" + "".join(row_card(row, idx + 1, audit=True) for idx, row in enumerate(blocked_top7[:20])) + "</div>"

    all_body = table_page(all_rows, "ALL audit view")
    all_body += "<div class='match-list'>" + "".join(row_card(dict(row, web_publish_blockers=web_publish_blockers(row)), idx + 1, audit=True) for idx, row in enumerate(all_rows[:120])) + "</div>" if all_rows else ""

    thinq_body = table_page(top7_raw, "THINQ intelligence view")
    cloq_rows = sorted(all_rows, key=lambda r: abs(as_float(r.get("odds_gap_pct"), 99.0) or 99.0))[:20]
    cloq_body = table_page(cloq_rows, "CLOQ close-odds candidates")
    results_page_body = results_body(results)

    write_page(TOP7_PATH, html_page("top7", "TBT PRO TOP7", "Production picks with CORQ, THINQ, MARQ, Sets/Games and Telegram RSS fields.", top_body, summary))
    write_page(ALL_PATH, html_page("all", "TBT PRO ALL", "Broad audit view with reject flags and full intelligence display.", all_body, summary))
    write_page(RESULTS_PATH, html_page("results", "TBT PRO Results", f"Results page. Display offset: UTC{RESULTS_DISPLAY_TIME_OFFSET_HOURS:+d}.", results_page_body, summary))
    write_page(THINQ_PATH, html_page("thinq", "TBT PRO THINQ", "THINQ intelligence output read-only display.", thinq_body, summary))
    write_page(CLOQ_PATH, html_page("cloq", "TBT PRO CLOQ", "Close-odds candidate view.", cloq_body, summary))

    rss = rss_feed(safe_top7)
    write_page(TG_RSS_PATH, rss)
    write_page(CORQ_RSS_PATH, rss)
    write_page(THINQ_RSS_PATH, rss_feed(top7_raw, "TBT PRO THINQ RSS"))
    write_page(CLOQ_RSS_PATH, rss_feed(cloq_rows, "TBT PRO CLOQ RSS"))
    write_assets()
    write_root_index()

    return {"top7_count": len(safe_top7), "all_count": len(all_rows), "results_count": len(results), "site_root": str(SITE_ROOT)}


if __name__ == "__main__":
    print(json.dumps(render(), indent=2))
