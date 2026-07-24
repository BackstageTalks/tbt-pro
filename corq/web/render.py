
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from corq.web.paths import ALL_PATH, CLOQ_PATH, CLOQ_RSS_PATH, CORQ_PATH, CORQ_RSS_PATH, RESULTS_PATH, THINQ_PATH, THINQ_RSS_PATH, NAV_ITEMS, page_file

OUTPUT_ROOT = Path("outputs")
SITE_ROOT = Path("corq/site")

CSS = ":root{--bg:#070b12;--panel:#0d1422;--panel2:#111b2d;--line:#22314a;--text:#f8fafc;--muted:#94a3b8;--blue:#38bdf8;--green:#22c55e;--yellow:#facc15}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#15223a 0,#070b12 38%,#05070d 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}.page{max-width:1440px;margin:0 auto;padding:28px}header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}.brand h1{margin:0;font-size:30px;letter-spacing:-.04em}.brand p{margin:6px 0 0;color:var(--muted)}nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}nav a{color:#cbd5e1;text-decoration:none;border:1px solid var(--line);padding:8px 11px;border-radius:999px;font-size:12px;background:rgba(13,20,34,.72)}nav a.active{color:#07110b;background:var(--green);border-color:var(--green);font-weight:800}.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0 22px}.summary{background:linear-gradient(180deg,rgba(17,27,45,.96),rgba(13,20,34,.96));border:1px solid var(--line);border-radius:18px;padding:16px}.summary .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.summary .value{font-size:26px;font-weight:900;margin-top:4px}.notice{border:1px solid #92400e;background:rgba(120,53,15,.25);color:#fed7aa;padding:14px 16px;border-radius:16px;margin:16px 0}.match-list{display:flex;flex-direction:column;gap:14px}.match-card{display:grid;grid-template-columns:52px minmax(270px,1.35fr) 115px minmax(520px,2fr);gap:14px;align-items:stretch;background:rgba(13,20,34,.9);border:1px solid var(--line);border-radius:22px;padding:14px}.rank{font-size:18px;font-weight:900;color:var(--blue)}.pick-name{font-size:16px;font-weight:900}.pick-odds{margin-top:3px;color:var(--yellow);font-size:12px;font-weight:900}.pick-action{margin-top:5px;color:var(--green);font-size:11px;font-weight:900;text-transform:lowercase;letter-spacing:.05em}.opponent-name{margin-top:2px;color:#cbd5e1;font-size:13px;font-weight:700}.opponent-odds{color:var(--muted);font-size:11px;margin-top:1px}.match-meta{color:var(--blue);font-size:11px;margin-top:6px}.status-line{color:var(--muted);font-size:10px;margin-top:6px}.chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.chip{font-size:9px;border:1px solid var(--line);color:#cbd5e1;border-radius:999px;padding:3px 6px;background:#08101d}.score-box{background:var(--panel2);border:1px solid var(--line);border-radius:16px;padding:13px 10px;text-align:center}.score-label{color:var(--muted);font-size:10px;letter-spacing:.08em}.score-main{font-size:25px;font-weight:950;margin-top:3px}.score-sub{color:var(--muted);font-size:11px;margin-top:3px}.intel-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.intel-card{background:linear-gradient(180deg,#111b2d,#0b1220);border:1px solid var(--line);border-radius:16px;padding:12px;min-height:142px}.intel-title{color:var(--green);font-size:11px;font-weight:950;letter-spacing:.09em;margin-bottom:8px}.kv{display:flex;justify-content:space-between;gap:10px;font-size:11px;padding:4px 0;border-bottom:1px solid rgba(34,49,74,.55)}.kv span{color:var(--muted)}.kv strong{color:#e2e8f0;text-align:right}.mini-audit{margin-top:8px;color:#64748b;font-size:9px}.blockers{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:10px}.blockers span{color:#fecdd3;background:rgba(190,18,60,.18);border:1px solid rgba(251,113,133,.4);border-radius:999px;padding:4px 8px;font-size:10px}.empty{padding:40px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:22px;background:rgba(13,20,34,.6)}footer{margin:30px 0 8px;color:#64748b;font-size:11px}@media(max-width:1100px){.match-card{grid-template-columns:42px 1fr}.score-box,.intel-grid{grid-column:1/-1}.cards{grid-template-columns:repeat(2,1fr)}header{display:block}nav{justify-content:flex-start;margin-top:14px}}"


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def pct(value: Any, signed: bool = False) -> str:
    try:
        number = float(value) * 100.0
    except Exception:
        return "—"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.1f}%"


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "—"


def flags(row: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for key in ("corq_warning_flags", "corq_risk_flags", "corq_reject_reasons", "thinq_flags"):
        value = row.get(key)
        if isinstance(value, list):
            result.extend(str(item) for item in value)
    thinq = row.get("thinq") if isinstance(row.get("thinq"), dict) else {}
    value = thinq.get("flags")
    if isinstance(value, list):
        result.extend(str(item) for item in value)
    return sorted(set(result))


def status_code(row: Dict[str, Any]) -> Optional[int]:
    try:
        value = row.get("status_code")
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def web_publish_blockers(row: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    stype = str(row.get("status_type") or "unknown").lower()
    scode = status_code(row)
    if stype not in {"notstarted", "not started", "scheduled", "unknown"}:
        blockers.append("WEB_BLOCK_NOT_NOTSTARTED")
    if scode not in (None, 0):
        blockers.append("WEB_BLOCK_STATUS_NOT_OPEN")
    side_audit = row.get("side_audit") if isinstance(row.get("side_audit"), dict) else {}
    thinq_side = row.get("thinq_side") if isinstance(row.get("thinq_side"), dict) else {}
    if side_audit.get("side_valid") is False or thinq_side.get("side_valid") is False:
        blockers.append("WEB_BLOCK_SIDE_INVALID")
    row_flags = set(flags(row))
    try:
        score = float(row.get("corq_score"))
    except Exception:
        score = None
    try:
        odds = float(row.get("odds") or row.get("pick_odds"))
    except Exception:
        odds = None
    if "DEFAULT_SCORE_VALUE_TRAP" in row_flags or "WARN_DEFAULT_SCORE_VALUE_TRAP" in row_flags:
        blockers.append("WEB_BLOCK_DEFAULT_SCORE_VALUE_TRAP")
    if score is not None and abs(score - 0.5) < 0.0001 and odds is not None and odds >= 3.0:
        blockers.append("WEB_BLOCK_NO_DATA_OUTSIDER")
    if "MISSING_ELO" in row_flags and "RECENT_FORM_NO_DATA" in row_flags and odds is not None and odds >= 3.0:
        blockers.append("WEB_BLOCK_NO_INTELLIGENCE_OUTSIDER")
    if odds is None:
        blockers.append("WEB_BLOCK_MISSING_ODDS")
    return sorted(set(blockers))


def edge_label(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "Neutral"
    if number > 0:
        return f"Pick {pct(number, signed=True)}"
    if number < 0:
        return f"Opp {pct(abs(number), signed=True)}"
    return "Neutral"


def meta(row: Dict[str, Any]) -> str:
    parts = [row.get("tournament"), row.get("surface"), row.get("level"), f"BO{row.get('best_of') or 3}"]
    return " · ".join(str(x) for x in parts if x not in (None, "", []))


def thinq_block(row: Dict[str, Any]) -> str:
    thinq = row.get("thinq") if isinstance(row.get("thinq"), dict) else {}
    recent = thinq.get("recent_form") if isinstance(thinq.get("recent_form"), dict) else {}
    edges = thinq.get("edges") if isinstance(thinq.get("edges"), dict) else row.get("thinq_edges") if isinstance(row.get("thinq_edges"), dict) else {}
    h2h = thinq.get("h2h") if isinstance(thinq.get("h2h"), dict) else {}
    side = row.get("thinq_side") if isinstance(row.get("thinq_side"), dict) else thinq.get("thinq_side") if isinstance(thinq.get("thinq_side"), dict) else {}
    side_text = side.get("orientation") or row.get("side_orientation") or "side n/a"
    last5 = "—"
    if recent.get("pick_last5_matches") is not None:
        last5 = f"{recent.get('pick_last5_wins', 0)}/{recent.get('pick_last5_matches', 0)} vs {recent.get('opponent_last5_wins', 0)}/{recent.get('opponent_last5_matches', 0)}"
    return "<div class='intel-card'><div class='intel-title'>THINQ</div>" + \
           f"<div class='kv'><span>ELO</span><strong>{esc(edge_label(edges.get('elo_edge')))}</strong></div>" + \
           f"<div class='kv'><span>Recent Form</span><strong>{esc(edge_label(edges.get('recent_form_edge')))}</strong></div>" + \
           f"<div class='kv'><span>Last 5</span><strong>{esc(last5)}</strong></div>" + \
           f"<div class='kv'><span>Surface Form</span><strong>{esc(edge_label(edges.get('surface_recent_form_edge')))}</strong></div>" + \
           f"<div class='kv'><span>H2H</span><strong>{esc(h2h.get('status') or 'NO_DATA')}</strong></div>" + \
           f"<div class='kv'><span>Confidence</span><strong>{esc(pct(row.get('thinq_confidence') or thinq.get('confidence')))}</strong></div>" + \
           f"<div class='mini-audit'>{esc(side_text)}</div></div>"


def sets_games_block() -> str:
    return "<div class='intel-card'><div class='intel-title'>SETS / GAMES</div><div class='kv'><span>Status</span><strong>Planned</strong></div><div class='kv'><span>Expected Sets</span><strong>Coming soon</strong></div><div class='kv'><span>Games Model</span><strong>Coming soon</strong></div></div>"


def marq_block(row: Dict[str, Any]) -> str:
    return "<div class='intel-card'><div class='intel-title'>MARQ</div>" + f"<div class='kv'><span>Status</span><strong>Planned</strong></div><div class='kv'><span>Odds Source</span><strong>{esc(row.get('odds_source') or '—')}</strong></div><div class='kv'><span>Direction</span><strong>{esc(row.get('odds_matching_direction') or '—')}</strong></div><div class='kv'><span>Market Quality</span><strong>Pending</strong></div></div>"


def pick_block(row: Dict[str, Any]) -> str:
    chip_html = "".join(f"<span class='chip'>{esc(flag)}</span>" for flag in flags(row)[:5])
    return f"<div class='pick-block'><div class='pick-name'>{esc(row.get('pick'))}</div><div class='pick-odds'>Pick @ {esc(money(row.get('odds') or row.get('pick_odds')))}</div><div class='pick-action'>to beat</div><div class='opponent-name'>{esc(row.get('opponent'))}</div><div class='opponent-odds'>Opp @ {esc(money(row.get('opponent_odds')))}</div><div class='match-meta'>{esc(meta(row))}</div><div class='status-line'>Status: {esc(row.get('status_type') or 'unknown')} · Side: {esc(row.get('side_orientation') or '—')}</div><div class='chips'>{chip_html}</div></div>"


def row_card(row: Dict[str, Any], rank: int, audit: bool = False) -> str:
    score = row.get("corq_adjusted_score") or row.get("corq_score")
    blockers = row.get("web_publish_blockers") or web_publish_blockers(row)
    blocker_html = ""
    if audit and blockers:
        blocker_html = "<div class='blockers'>" + "".join(f"<span>{esc(b)}</span>" for b in blockers) + "</div>"
    return f"<article class='match-card'><div class='rank'>#{rank}</div>{pick_block(row)}<div class='score-box'><div class='score-label'>CORQ</div><div class='score-main'>{esc(pct(score))}</div><div class='score-sub'>Edge {esc(pct(row.get('corq_edge'), signed=True))}</div><div class='score-sub'>Odds {esc(money(row.get('odds') or row.get('pick_odds')))}</div></div><div class='intel-grid'>{thinq_block(row)}{sets_games_block()}{marq_block(row)}</div>{blocker_html}</article>"


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
    cards = [("Candidates", summary.get("candidate_count", "—")), ("ALL", summary.get("all_count", "—")), ("Ranked", summary.get("ranked_count", "—")), ("TOP7", summary.get("top7_count", "—")), ("Updated", updated[:16].replace("T", " "))]
    cards_html = "".join(f"<div class='summary'><div class='label'>{esc(label)}</div><div class='value'>{esc(value)}</div></div>" for label, value in cards)
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/><title>{esc(title)}</title><style>{CSS}</style></head><body><div class='page'><header><div class='brand'><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>{nav(active)}</header><section class='cards'>{cards_html}</section>{body}<footer>TBT PRO · CORQ runtime · THINQ → SETS/GAMES → MARQ · Web render is display-only.</footer></div></body></html>"


def write_page(path_key: str, content: str) -> None:
    target = SITE_ROOT / page_file(path_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def publish_safe_top7(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    safe = []
    for row in rows:
        blockers = web_publish_blockers(row)
        copy = dict(row)
        copy["web_publish_blockers"] = blockers
        if not blockers:
            safe.append(copy)
    return safe[:7]


def rss_xml(rows: List[Dict[str, Any]]) -> str:
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = []
    for row in rows[:7]:
        title = f"{row.get('pick')} @ {money(row.get('odds') or row.get('pick_odds'))} to beat {row.get('opponent')}"
        desc = f"CORQ {pct(row.get('corq_adjusted_score') or row.get('corq_score'))}; Edge {pct(row.get('corq_edge'), signed=True)}"
        items.append(f"<item><title>{esc(title)}</title><description>{esc(desc)}</description><pubDate>{now}</pubDate></item>")
    return "<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>TBT PRO CORQ RSS</title>" + "".join(items) + "</channel></rss>"


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
    safe_top7 = publish_safe_top7(top7_raw)
    blocked = [dict(row, web_publish_blockers=web_publish_blockers(row)) for row in top7_raw if web_publish_blockers(row)]
    summary = {"candidate_count": manifest.get("candidate_count", "—"), "all_count": manifest.get("all_count", len(all_raw)), "ranked_count": manifest.get("ranked_count", len(top7_raw)), "top7_count": len(safe_top7), "updated": manifest.get("finished_at_utc") or datetime.now(timezone.utc).isoformat()}
    top_body = ("<div class='match-list'>" + "".join(row_card(row, idx + 1) for idx, row in enumerate(safe_top7)) + "</div>") if safe_top7 else "<div class='notice'>No publication-safe TOP7 picks after web guard. ALL audit still contains all runtime rows.</div>"
    if blocked:
        top_body += "<h2>Blocked from Corq page</h2><div class='match-list'>" + "".join(row_card(row, idx + 1, audit=True) for idx, row in enumerate(blocked[:10])) + "</div>"
    all_rows = all_raw if all_raw else top7_raw
    all_body = ("<div class='match-list'>" + "".join(row_card(dict(row, web_publish_blockers=web_publish_blockers(row)), idx + 1, audit=True) for idx, row in enumerate(all_rows)) + "</div>") if all_rows else "<div class='empty'>No ALL rows available.</div>"
    write_page(CORQ_PATH, html_page("corq", "TBT PRO · Corq", "TOP7 publication-safe view", top_body, summary))
    write_page(ALL_PATH, html_page("all", "TBT PRO · All", "Broad audit view with side, THINQ and market warnings", all_body, summary))
    write_page(CLOQ_PATH, html_page("cloq", "TBT PRO · Cloq", "Close-odds specialist planned", "<div class='empty'>CLOQ page planned.</div>", summary))
    write_page(THINQ_PATH, html_page("thinq", "TBT PRO · Thinq", "THINQ intelligence overview planned", "<div class='empty'>THINQ standalone page planned. THINQ cards are already visible on Corq and All.</div>", summary))
    write_page(RESULTS_PATH, html_page("results", "TBT PRO · Results", "Results tracking planned", "<div class='empty'>Results page planned.</div>", summary))
    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    (SITE_ROOT / "index.html").write_text(f"<meta http-equiv='refresh' content='0; url={CORQ_PATH}/'><a href='{CORQ_PATH}/'>TBT PRO Corq</a>", encoding="utf-8")
    (SITE_ROOT / CORQ_RSS_PATH).write_text(rss_xml(safe_top7), encoding="utf-8")
    (SITE_ROOT / CLOQ_RSS_PATH).write_text("<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>TBT PRO CLOQ RSS</title></channel></rss>", encoding="utf-8")
    (SITE_ROOT / THINQ_RSS_PATH).write_text("<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>TBT PRO THINQ RSS</title></channel></rss>", encoding="utf-8")
    render_manifest = {"rendered_at_utc": datetime.now(timezone.utc).isoformat(), "safe_top7_count": len(safe_top7), "blocked_top7_count": len(blocked), "site_root": str(SITE_ROOT)}
    (SITE_ROOT / "render_manifest.json").write_text(json.dumps(render_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TBT PRO site rendered: safe_top7={len(safe_top7)} blocked={len(blocked)} root={SITE_ROOT}")
    return render_manifest


def main() -> None:
    render()


if __name__ == "__main__":
    main()
