import glob
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.elo.torq_fusion import build_b_hand_candidate, build_torq_prediction, is_torq_top_candidate
from src.marq_ai.torq_market import attach_torq_market

BASE_URL = os.getenv("BASE_URL", "https://backstagetalks.github.io/tbt-pro").rstrip("/")
LOCAL_TZ = ZoneInfo("Europe/Bratislava")
PUBLIC = Path("public")


def latest_json(patterns):
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    files = [p for p in files if os.path.exists(p)]
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_json(path, default):
    try:
        if not path or not os.path.exists(path):
            return default
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print("TORQ LOAD ERROR:", path, exc)
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def esc(value):
    text = str(value or "")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "-"


def dec(value):
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "-"


def render_cards(items):
    if not items:
        return '<section class="empty">No Torq picks available.</section>'
    cards = []
    for idx, item in enumerate(items, 1):
        extra = ""
        if item.get("b_hand"):
            extra = '<div class="metric"><span>B-Hand edge</span><b>' + dec(item.get("b_hand_edge_pp")) + ' pp</b></div><div class="metric"><span>Market gap</span><b>' + dec(item.get("b_hand_market_gap_pp")) + ' pp</b></div>'
        card = "".join([
            '<article class="card"><div class="rank">#', str(idx), '</div>',
            '<h2>', esc(item.get("pick")), '</h2>',
            '<p class="match">', esc(item.get("match")), '</p><div class="grid">',
            '<div class="metric"><span>Torq AI</span><b>', pct(item.get("torq_probability") or item.get("probability")), '</b></div>',
            '<div class="metric"><span>Odds</span><b>', dec(item.get("odds")), '</b></div>',
            '<div class="metric"><span>AI Match</span><b>', dec(item.get("torq_ai_match") or item.get("ai_match")), '</b></div>',
            '<div class="metric"><span>Confidence</span><b>', dec(item.get("torq_confidence") or item.get("confidence_score")), '</b></div>',
            '<div class="metric"><span>Quality</span><b>', esc(item.get("torq_data_quality")), '</b></div>',
            '<div class="metric"><span>Align</span><b>', esc(item.get("torq_alignment")), '</b></div>',
            '<div class="metric"><span>Marq</span><b>', esc(item.get("torq_market_status") or item.get("marq_ai_signal") or "NO_DATA"), '</b></div>',
            extra,
            '</div><p class="reason">', esc(item.get("b_hand_reason") or item.get("torq_reason") or item.get("top_reason") or ""), '</p></article>'
        ])
        cards.append(card)
    return "\n".join(cards)


def render_page(title, subtitle, items, destination):
    now = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    destination.parent.mkdir(parents=True, exist_ok=True)
    css = ":root{--bg:#071013;--card:#101b20;--muted:#9fb0b7;--text:#edf7f8;--accent:#44d7b6;--line:#20343b}body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}header,main,footer{max-width:1120px;margin:auto;padding:18px}nav a{color:var(--accent);margin-right:14px;text-decoration:none;font-weight:700}h1{font-size:42px;margin:22px 0 6px}.sub,.match,.reason,.empty,footer{color:var(--muted)}main{display:grid;gap:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px}.rank{color:var(--accent);font-weight:800}h2{margin:4px 0;font-size:28px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:14px}.metric{border:1px solid var(--line);border-radius:14px;padding:10px}.metric span{display:block;color:var(--muted);font-size:12px}.metric b{display:block;margin-top:4px;font-size:18px}"
    nav = '<a href="/tbt-pro/h4v34n1c3d4y150/">Torq TOP5</a><a href="/tbt-pro/h4v34n1c3d4y151/">Torq ALL</a><a href="/tbt-pro/h4v34n1c3d4y152/">B-Hand</a><a href="/tbt-pro/h4v34n1c3d4y153/">Results</a><a href="/tbt-pro/h4v34n1c3d4y154/">Dashboard</a>'
    html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title><style>' + css + '</style></head><body><header><nav>' + nav + '</nav><h1>' + esc(title) + '</h1><p class="sub">' + esc(subtitle) + ' · Updated ' + now + ' Europe/Bratislava</p></header><main>' + render_cards(items) + '</main><footer>Torq AI is analytical model output. No result is guaranteed.</footer></body></html>'
    destination.write_text(html, encoding="utf-8")


def render_rss(title, link, items, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>', '<title>'+esc(title)+'</title>', '<link>'+esc(link)+'</link>', '<description>'+esc(title)+'</description>']
    for item in items:
        pick = esc(item.get("pick"))
        opponent = esc(item.get("opponent"))
        desc = 'Torq probability: ' + pct(item.get("torq_probability") or item.get("probability")) + '<br>Odds: ' + dec(item.get("odds"))
        if item.get("b_hand"):
            desc += '<br>B-Hand edge: ' + dec(item.get("b_hand_edge_pp")) + ' pp'
        lines += ['<item>', '<title>'+pick+' to win vs '+opponent+'</title>', '<description>'+esc(desc)+'</description>', '<link>'+esc(link)+'</link>', '</item>']
    lines.append('</channel></rss>')
    destination.write_text("\n".join(lines), encoding="utf-8")


def main():
    source = latest_json(["public/all_predictions_*.json", "public/predictions_*.json", "data/pick_history/all/*.json"])
    raw = load_json(source, [])
    if not isinstance(raw, list):
        raw = []
    all_items = [build_torq_prediction(attach_torq_market(item)) for item in raw if isinstance(item, dict)]
    all_items.sort(key=lambda x: x.get("torq_probability", x.get("probability", 0)), reverse=True)
    top = [x for x in all_items if is_torq_top_candidate(x)]
    top.sort(key=lambda x: x.get("torq_confidence", 0), reverse=True)
    top = top[: int(os.getenv("TORQ_TOP_LIMIT", "5"))]
    bhand = []
    for item in all_items:
        candidate = build_b_hand_candidate(item)
        if candidate:
            bhand.append(candidate)
    bhand.sort(key=lambda x: (x.get("b_hand_edge_pp", 0), x.get("torq_confidence", 0)), reverse=True)
    bhand = bhand[: int(os.getenv("B_HAND_TOP_LIMIT", "5"))]
    save_json(PUBLIC / "torq_predictions.json", all_items)
    save_json(PUBLIC / "torq_top5.json", top)
    save_json(PUBLIC / "torq_b_hand.json", bhand)
    render_page("Torq TOP5", "High-confidence picks selected by Torq AI", top, PUBLIC / "h4v34n1c3d4y150" / "index.html")
    render_page("Torq ALL", "All analysed matches enriched by Torq AI", all_items, PUBLIC / "h4v34n1c3d4y151" / "index.html")
    render_page("Torq B-Hand", "Balanced-market value edges selected by Torq AI", bhand, PUBLIC / "h4v34n1c3d4y152" / "index.html")
    render_page("Torq Results", "Results page placeholder. Settlement workflow will fill this in v2.", [], PUBLIC / "h4v34n1c3d4y153" / "index.html")
    render_page("Torq Dashboard", "Source: " + str(source or "none") + " · ALL " + str(len(all_items)) + " · TOP " + str(len(top)) + " · B-Hand " + str(len(bhand)), [], PUBLIC / "h4v34n1c3d4y154" / "index.html")
    render_rss("Torq TOP5 RSS", BASE_URL + "/h4v34n1c3d4y150/", top, PUBLIC / "h4v34n1c3d4y155.xml")
    render_rss("Torq B-Hand RSS", BASE_URL + "/h4v34n1c3d4y152/", bhand, PUBLIC / "h4v34n1c3d4y156.xml")
    render_rss("Torq Results RSS", BASE_URL + "/h4v34n1c3d4y153/", [], PUBLIC / "h4v34n1c3d4y157.xml")
    print("TORQ BUILD DONE", "all", len(all_items), "top", len(top), "b_hand", len(bhand))


if __name__ == "__main__":
    main()
