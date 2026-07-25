from __future__ import annotations

import html, json, math, os, re
from datetime import datetime, timezone
from pathlib import Path

try:
    from corq.web.paths import ALL_PATH, CLOQ_PATH, CLOQ_RSS_PATH, CORQ_PATH, CORQ_RSS_PATH, RESULTS_PATH, THINQ_PATH, THINQ_RSS_PATH, get_base_url
except Exception:
    CORQ_PATH="h4v34n1c3d4y180"; CLOQ_PATH="h4v34n1c3d4y181"; ALL_PATH="h4v34n1c3d4y182"; RESULTS_PATH="h4v34n1c3d4y183"
    CORQ_RSS_PATH="h4v34n1c3d4y184.xml"; CLOQ_RSS_PATH="h4v34n1c3d4y185.xml"; THINQ_PATH="h4v34n1c3d4y186"; THINQ_RSS_PATH="h4v34n1c3d4y187.xml"
    def get_base_url(): return os.getenv("TBTPRO_BASE_URL", "https://backstagetalks.github.io/tbt-pro/")

try:
    from corq.messages import public_flag_labels, flag_message
except Exception:
    def public_flag_labels(flags): return [str(x).replace('_',' ').title() for x in (flags or [])]
    def flag_message(flag): return {"label": str(flag).replace('_',' ').title(), "show_public": True}

ROOT=Path.cwd(); OUTPUTS=ROOT/"outputs"; SITE=ROOT/"corq"/"site"

def esc(v): return html.escape("" if v is None else str(v), quote=True)
def read_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception: return default

def as_list(data):
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for k in ("items","rows","predictions","top7","all","results"):
            if isinstance(data.get(k), list): return data[k]
    return []

def deep_get(row,*paths,default=None):
    for path in paths:
        cur=row; ok=True
        for part in str(path).split('.'):
            if isinstance(cur,dict) and part in cur: cur=cur[part]
            else: ok=False; break
        if ok and cur is not None: return cur
    return default

def fnum(v, default=None):
    try:
        if v is None or v=="" or str(v).strip() in {"-","--","—"}: return default
        return float(v)
    except Exception: return default

def pct(v,d=1,dash="—",signed=True):
    x=fnum(v)
    if x is None or math.isnan(x): return dash
    if abs(x)<=1.5: x*=100
    s="+" if signed and x>0 else ""
    return f"{s}{x:.{d}f}%"

def pctp(v,d=1): return pct(v,d,signed=False)
def fmt(v,d=2,dash="—"):
    x=fnum(v)
    return dash if x is None or math.isnan(x) else f"{x:.{d}f}"
def odds(v):
    x=fnum(v)
    return "—" if x is None else f"{x:.2f}"
def first(row,*keys,default=None): return deep_get(row,*keys,default=default)

def prob(row): return first(row,"corq_estimated_win_probability","estimated_win_probability","corq_probability","win_probability","probability",default=None)
def thinq_prob(row): return first(row,"thinq_probability_layer.probability","thinq_probability","thinq_winner_probability","thinq.probability_layer.probability",default=prob(row))
def thinq_conf(row): return first(row,"thinq_probability_layer.confidence","thinq_probability_confidence","thinq.confidence","thinq_confidence",default=None)
def form_conf(row): return first(row,"thinq.recent_form.form_confidence","recent_form.form_confidence","form_confidence","thinq_form_confidence",default=None)

def edge(row,*keys): return first(row,*keys,default=0.0)
def pick_elo(row): return edge(row,"thinq.edges.overall_elo_edge","thinq_overall_elo_edge","overall_elo_edge","thinq.elo.overall_elo_edge","thinq.elo.edge")
def pick_selo(row): return edge(row,"thinq.edges.surface_elo_edge","thinq_surface_elo_edge","surface_elo_edge","thinq.elo.surface_elo_edge")
def h2h_edge(row): return edge(row,"thinq.h2h.edge","thinq_h2h_edge","h2h_edge","thinq.edges.h2h_edge")
def recent_edge(row): return edge(row,"thinq.recent_form.recent_form_edge","recent_form_edge","thinq.edges.recent_form_edge")
def surface_edge(row): return edge(row,"thinq.recent_form.surface_recent_form_edge","surface_recent_form_edge","thinq.edges.surface_recent_form_edge")
def quality_edge(row): return edge(row,"thinq.recent_form.opponent_quality_edge","opponent_quality_edge","thinq.edges.opponent_quality_edge")

def record(row,*keys,default="—"):
    v=first(row,*keys,default=None)
    return default if v in (None,"") else str(v)
def pick_form(row): return record(row,"thinq.recent_form.pick_last10_record","recent_form.pick_last10_record","pick_last10_record")
def opp_form(row): return record(row,"thinq.recent_form.opponent_last10_record","recent_form.opponent_last10_record","opponent_last10_record")
def pick_sform(row): return record(row,"thinq.recent_form.pick_surface_record","recent_form.pick_surface_record","pick_surface_record")
def opp_sform(row): return record(row,"thinq.recent_form.opponent_surface_record","recent_form.opponent_surface_record","opponent_surface_record")

def owner(v):
    x=fnum(v,0) or 0
    if abs(x)<0.00005: return "0.0%"
    return f"Pick {pct(abs(x))}" if x>0 else f"Opp {pct(abs(x))}"


def data_depth(row):
    conf = fnum(thinq_conf(row), 0) or 0
    if conf <= 1.5:
        conf *= 100
    signal = abs((fnum(thinq_prob(row), 0.5) or 0.5) - 0.5)
    if signal <= 1.5:
        signal *= 100
    if conf < 40 or signal < 1.5:
        return "Low"
    if conf >= 75 and signal >= 6:
        return "Strong"
    return "Medium"

def h2h_display(row):
    h2h=first(row,"thinq.h2h","h2h",default={}) or {}
    total=fnum(h2h.get('total_matches'),0) or 0
    status=str(h2h.get('status') or first(row,'thinq_h2h_status',default='')).upper()
    if total<=0 or status in {"NO_DATA","NO_PREVIOUS_MATCHES"}: return "No previous matches"
    pw=int(fnum(h2h.get('pick_wins'),0) or 0); ow=int(fnum(h2h.get('opponent_wins'),0) or 0)
    return f"Pick {pw}-{ow} · {pct(h2h_edge(row))}"

def pair(label,val): return f'<div class="metric-row"><span>{esc(label)}</span><strong>{esc(val)}</strong></div>'

def thinq_core(row):
    rows=[
        pair("Pick ELO / S-ELO", f"{pct(pick_elo(row))} / {pct(pick_selo(row))}"),
        pair("Opp ELO / S-ELO", f"{pct(-(fnum(pick_elo(row),0) or 0))} / {pct(-(fnum(pick_selo(row),0) or 0))}"),
        pair("H2H", h2h_display(row)),
        pair("ThinQ Edge", owner(first(row,"thinq_probability_layer.edge","thinq_edge",default=None) or ((fnum(thinq_prob(row),0.5) or 0.5)-0.5))),
    ]
    winner=first(row,"thinq_probability_layer.winner","thinq_winner",default=None)
    if winner: rows.append(pair("ThinQ Pick", winner))
    rows.append(pair("Data Depth", data_depth(row)))
    return f'<section class="metric-card thinq-card"><div class="metric-title"><span>ThinQ</span><strong>{esc(pctp(thinq_prob(row)))}</strong></div><div class="metric-table">{"".join(rows)}</div></section>'

def thinq_form(row):
    rows=[
        pair("Pick Form / S-Form", f"{pick_form(row)} / {pick_sform(row)}"),
        pair("Opp Form / S-Form", f"{opp_form(row)} / {opp_sform(row)}"),
        pair("Recent Edge", owner(recent_edge(row))),
        pair("Surface Edge", owner(surface_edge(row))),
        pair("Form Quality", owner(quality_edge(row))),
        pair("Form Conf.", pctp(form_conf(row))),
    ]
    return f'<section class="metric-card thinq-card"><div class="metric-title"><span>ThinQ Overall Conf.</span><strong>{esc(pctp(thinq_conf(row)))}</strong></div><div class="metric-table">{"".join(rows)}</div></section>'

def sets_box(row):
    md=first(row,"thinq.match_dynamics","match_dynamics",default={}) or {}
    ps=first(row,"thinq_projected_sets","thinq.match_dynamics.projected_sets","projected_sets",default=md.get('projected_sets'))
    pg=first(row,"thinq_projected_games","thinq.match_dynamics.projected_games","projected_games",default=md.get('projected_games'))
    three=first(row,"thinq_decider_probability","thinq.match_dynamics.decider_probability","decider_probability",default=md.get('decider_probability'))
    tb=first(row,"thinq_tiebreak_probability","thinq.match_dynamics.tiebreak_probability","tiebreak_probability",default=md.get('tiebreak_probability'))
    score=first(row,"thinq.match_dynamics.most_likely_score","most_likely_score","score_prediction",default=md.get('most_likely_score') or "—")
    line=first(row,"games_line","thinq.match_dynamics.games_line",default=22.5)
    over=first(row,"games_over_probability","thinq.match_dynamics.games_over_probability",default=md.get('games_over_probability'))
    ou="—" if over is None else f"Over {fmt(line,2)} · {pctp(over)}"
    rows=[pair("Sets",fmt(ps,2)),pair("Games",fmt(pg,1)),pair("O/U",ou),pair("3 Sets",pctp(three)),pair("Score",score),pair("Tie-break",pctp(tb))]
    return f'<section class="metric-card"><div class="metric-title"><span>Sets / Games</span></div><div class="metric-table">{"".join(rows)}</div></section>'

def direction(row):
    raw=first(row,"odds_matching_direction",default="")
    return "Confirmed" if raw in {"DIRECT_BY_NUMERIC_OUTCOME","REVERSED_BY_NUMERIC_OUTCOME"} else (flag_message(raw).get('label') if raw else "—")

def marq_box(row):
    rows=[pair("Pick MarQ",first(row,"marq_pick","pick_marq",default="—")),pair("Opp MarQ",first(row,"marq_opp","opp_marq",default="—")),pair("Move",first(row,"marq_move",default="—")),pair("Odds Source",first(row,"odds_source",default="RapidAPI PRO event odds")),pair("Direction",direction(row)),pair("Status","Market view only")]
    return f'<section class="metric-card"><div class="metric-title"><span>MarQ</span></div><div class="metric-table">{"".join(rows)}</div></section>'

def mkey(row,idx):
    key=first(row,"event_custom_id","customId","raw.customId","event_id","id",default=None)
    if not key: key=f"{idx}-{first(row,'pick',default='pick')}-vs-{first(row,'opponent',default='opp')}"
    return re.sub(r"[^A-Za-z0-9_-]+","-",str(key))

def write_log(row,idx):
    key=mkey(row,idx); folder=SITE/"logs"/key; folder.mkdir(parents=True,exist_ok=True)
    log={"match":{"rank":idx,"pick":first(row,'pick',default=''),"opponent":first(row,'opponent',default=''),"event_id":first(row,'event_id','id',default=None),"customId":first(row,'event_custom_id','customId','raw.customId',default=None)},"thinq":first(row,'thinq',default={}),"thinq_probability_layer":first(row,'thinq_probability_layer','thinq.probability_layer',default={}),"thinq_flat":{k:v for k,v in row.items() if str(k).startswith('thinq_')},"corq_components":first(row,'corq_components',default={}),"raw":first(row,'raw',default={}),"row":row}
    (folder/'thinq-log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'index.html').write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>ThinQ Log</title><style>body{{background:#05101f;color:#dbeafe;font-family:ui-monospace,Menlo,monospace;padding:24px}}pre{{white-space:pre-wrap;background:#0b1727;border:1px solid #1e3555;border-radius:14px;padding:18px}}</style></head><body><h1>ThinQ calculation log</h1><p>{esc(first(row,'pick',default=''))} vs {esc(first(row,'opponent',default=''))}</p><pre>{esc(json.dumps(log,ensure_ascii=False,indent=2))}</pre></body></html>",encoding='utf-8')
    return f"logs/{key}/"

def pick_block(row,idx):
    pick=first(row,'pick',default='—'); opp=first(row,'opponent',default='—')
    time=first(row,'match_time_display','start_time_display','time_display',default='')
    tour=first(row,'tournament','event_name','raw.tournament.name',default=''); surface=first(row,'surface','surface_raw',default=''); best=first(row,'best_of','bestOf',default='3')
    meta=' · '.join([str(x) for x in (time,tour,surface,f"BO{best}" if best else None) if x])
    status=first(row,'status_type','status.type','raw.status.type',default='')
    badges=''.join(f'<span class="badge">{esc(b)}</span>' for b in public_flag_labels(first(row,'corq_risk_flags','thinq.flags','flags',default=[]))[:2])
    return f'<aside class="pick-block"><div class="rank">#{idx}</div><div><h2>{esc(pick)}</h2><div class="pick-odds">Pick @ {esc(odds(first(row,"odds","pick_odds",default=None)))}</div><div class="pick-action">to beat</div><div class="opponent-name">{esc(opp)}</div><div class="opp-odds">Opp @ {esc(odds(first(row,"opponent_odds","opp_odds",default=None)))}</div><div class="match-meta">{esc(meta)}</div><a class="log-dot" href="{esc(write_log(row,idx))}" title="Open ThinQ calculation log">🧠</a><div class="status-line">{("Status: "+esc(status)) if status else ""}</div><div class="badges">{badges}</div></div></aside>'

def card(row,idx): return f'<article class="prediction-card">{pick_block(row,idx)}<div class="metrics-grid">{thinq_core(row)}{thinq_form(row)}{sets_box(row)}{marq_box(row)}</div></article>'
def sort_rows(rows): return sorted(rows,key=lambda r:fnum(prob(r),-999),reverse=True)
def nav(active='corq'):
    base=get_base_url().rstrip('/')+'/'
    data=[('CorQ',f'{base}{CORQ_PATH}/','corq'),('ALL',f'{base}{ALL_PATH}/','all'),('Results',f'{base}{RESULTS_PATH}/','results'),('CloQ',f'{base}{CLOQ_PATH}/','cloq'),('RSS',f'{base}{CORQ_RSS_PATH}','rss')]
    return ''.join(f'<a class="nav-link {"active" if k==active else ""}" href="{h}">{l}</a>' for l,h,k in data)

def page(title,body,active='corq'):
    css = r'''
:root{--bg:#030812;--line:#203553;--text:#e7f0ff;--muted:#86a2c4;--green:#22c55e;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#0d1b33 0,#030812 42%,#02050b 100%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;font-size:14px}.container{max-width:1880px;margin:0 auto;padding:28px 22px 60px}.header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:22px}.brand{display:flex;gap:12px;align-items:center}.logo{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#22d3ee,#22c55e)}.brand h1{margin:0;font-size:20px}.brand span{display:block;color:var(--muted);font-size:12px;margin-top:2px}.nav{display:flex;gap:8px;flex-wrap:wrap}.nav-link{text-decoration:none;color:#b7c8df;border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:#071225}.nav-link.active,.nav-link:hover{color:white;border-color:#22c55e;background:#092118}.summary{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:14px;margin-bottom:22px}.summary-card{background:rgba(8,20,38,.82);border:1px solid var(--line);border-radius:18px;padding:16px 18px}.summary-card small{color:var(--muted);text-transform:uppercase;letter-spacing:.12em;font-size:11px}.summary-card strong{display:block;font-size:28px;margin-top:7px}.rss-bar{border:1px solid var(--line);border-radius:18px;background:#061225;padding:14px 16px;margin-bottom:18px;color:#cfe4ff}.rss-bar a{color:white;border:1px solid #385071;border-radius:999px;padding:6px 10px;margin-left:10px;text-decoration:none;font-size:12px}.prediction-card{display:grid;grid-template-columns:330px minmax(0,1fr);gap:18px;align-items:stretch;border:1px solid var(--line);border-radius:22px;background:rgba(8,20,38,.74);padding:18px;margin-bottom:16px;box-shadow:0 16px 42px rgba(0,0,0,.18)}.pick-block{position:relative;display:grid;grid-template-columns:52px 1fr;gap:14px;min-height:220px}.rank{color:#38bdf8;font-weight:900;font-size:22px}.pick-block h2{margin:0 0 5px;font-size:18px;line-height:1.15}.pick-odds{color:var(--yellow);font-weight:900;margin:2px 0}.pick-action{color:var(--green);font-size:13px;font-weight:900;text-transform:lowercase}.opponent-name{font-size:16px;font-weight:800;margin-top:2px}.opp-odds{color:#c7d6eb;font-size:13px;margin-top:2px}.match-meta{color:#38bdf8;font-size:13px;margin-top:14px;line-height:1.35}.status-line{color:#b9c7dc;font-size:12px;margin-top:15px}.log-dot{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;text-decoration:none;background:#101f35;border:1px solid #335071;margin-top:8px}.badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.badge{font-size:11px;color:#cbd5e1;background:#0a1a2c;border:1px solid #29415f;border-radius:999px;padding:4px 8px}.metrics-grid{display:grid;grid-template-columns:minmax(270px,1fr) minmax(270px,1fr) minmax(250px,.9fr) minmax(245px,.88fr);gap:14px;align-items:stretch}.metric-card{border:1px solid var(--line);background:rgba(5,15,29,.72);border-radius:18px;padding:14px 15px;min-height:220px}.thinq-card{border-color:#1f6c57}.metric-title{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #18304e;padding-bottom:10px;margin-bottom:2px;color:#93aeca;text-transform:uppercase;letter-spacing:.14em;font-size:12px}.metric-title strong{font-size:18px;color:var(--green);letter-spacing:0;text-transform:none}.metric-table{display:flex;flex-direction:column}.metric-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;border-bottom:1px solid rgba(32,53,83,.75);padding:9px 0;align-items:center}.metric-row:last-child{border-bottom:0}.metric-row span{color:#9cb4d2;font-size:13px;line-height:1.25}.metric-row strong{font-size:13px;color:#f7fbff;text-align:right;line-height:1.25;white-space:nowrap}.empty{border:1px solid var(--line);border-radius:18px;padding:28px;background:#081426;color:#cbd5e1}@media(max-width:1500px){.prediction-card{grid-template-columns:300px 1fr}.metrics-grid{grid-template-columns:repeat(2,minmax(250px,1fr))}}@media(max-width:900px){.prediction-card{grid-template-columns:1fr}.metrics-grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}}
'''
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{css}</style></head><body><div class="container"><header class="header"><div class="brand"><div class="logo"></div><div><h1>AI Betting by BackstageTalks</h1><span>CorQ, ThinQ and CloQ analytics</span></div></div><nav class="nav">{nav(active)}</nav></header>{body}</div></body></html>'

def summary(manifest,top,allr):
    upd=first(manifest,'generated_at','updated_at','run_at',default=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    return f'<section class="summary"><div class="summary-card"><small>ALL</small><strong>{len(allr)}</strong></div><div class="summary-card"><small>TOP7</small><strong>{len(top)}</strong></div><div class="summary-card"><small>Ranked</small><strong>{first(manifest,"ranked_count",default=len(top))}</strong></div><div class="summary-card"><small>Updated</small><strong style="font-size:18px">{esc(upd)}</strong></div></section>'

def render_corq(top,allr,manifest):
    rows=sort_rows(top)[:7]; cards=''.join(card(r,i) for i,r in enumerate(rows,1)) or '<div class="empty">No Top7 rows available.</div>'
    base=get_base_url().rstrip('/')+'/'; body=summary(manifest,rows,allr)+f'<div class="rss-bar">Telegram RSS feed <a href="{esc(base+CORQ_RSS_PATH)}">Open RSS</a></div>'+cards
    return page('CorQ TOP7',body,'corq')

def render_all(allr,manifest):
    rows=sort_rows(allr)
    return page('ALL audit',summary(manifest,rows[:7],allr)+(''.join(card(r,i) for i,r in enumerate(rows,1)) or '<div class="empty">No ALL rows available.</div>'),'all')

def rss_items(rows):
    base=get_base_url().rstrip('/')+'/'; now=datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'); out=[]
    for r in sort_rows(rows)[:7]:
        pick=first(r,'pick',default='Pick'); opp=first(r,'opponent',default='Opponent'); time=first(r,'match_time_display','start_time_display','time_display',default='')
        title=f"{time} | {pick} to beat {opp}" if time else f"{pick} to beat {opp}"
        desc=f"Pick: {pick} Opponent: {opp} Win probability: {pctp(prob(r))} ThinQ: {pctp(thinq_prob(r))} Odds: {odds(first(r,'odds','pick_odds',default=None))} Powered by BackstageTalks Statistical Engine"
        out.append(f"<item><title>{esc(title)}</title><link>{esc(base)}</link><description>{esc(desc)}</description><pubDate>{now}</pubDate></item>")
    return '\n'.join(out)

def write_rss(rows):
    xml=f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>AI Betting by BackstageTalks</title><link>{esc(get_base_url())}</link><description>CorQ TOP7 feed</description>{rss_items(rows)}</channel></rss>'
    for p in (CORQ_RSS_PATH, THINQ_RSS_PATH, CLOQ_RSS_PATH): (SITE/p).write_text(xml,encoding='utf-8')

def write_page(rel,content):
    target=SITE/rel
    if target.suffix: target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content,encoding='utf-8')
    else: target.mkdir(parents=True,exist_ok=True); (target/'index.html').write_text(content,encoding='utf-8')

def render_site():
    SITE.mkdir(parents=True,exist_ok=True)
    top=as_list(read_json(OUTPUTS/'latest_top7.json',[])); allr=as_list(read_json(OUTPUTS/'latest_all.json',[])); manifest=read_json(OUTPUTS/'latest_manifest.json',{})
    write_page('index.html',f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={CORQ_PATH}/"><a href="{CORQ_PATH}/">Open CorQ</a>')
    write_page(CORQ_PATH,render_corq(top,allr,manifest)); write_page(ALL_PATH,render_all(allr or top,manifest))
    write_page(RESULTS_PATH,page('Results','<div class="empty"><h2>Results</h2><p>Results page is ready for the Results workflow output.</p></div>','results'))
    write_page(CLOQ_PATH,page('CloQ','<div class="empty"><h2>CloQ</h2><p>CloQ selection will be enabled after ThinQ probability stabilizes.</p></div>','cloq'))
    write_page(THINQ_PATH,page('ThinQ','<div class="empty"><h2>ThinQ</h2><p>ThinQ is displayed inside every CorQ card.</p></div>','corq'))
    write_rss(top); print(f"TBT PRO site rendered: top7={len(top)} all={len(allr)} root={SITE}")

def main(): render_site()
if __name__=='__main__': main()
