"""Generate the static BlinQ comparison website from dedicated ELO/H2H caches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ELO_PATH = Path("thinq/data/elo/ta_elo_ratings.json")
H2H_PATH = Path("thinq/data/h2h/h2h_cache.json")


def _num(value: Any) -> Any:
    try:
        return None if value in (None, "") else round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _players() -> List[Dict[str, Any]]:
    if not ELO_PATH.is_file():
        raise FileNotFoundError(f"Dedicated ELO cache not found: {ELO_PATH}")
    payload = json.loads(ELO_PATH.read_text(encoding="utf-8"))
    source = payload.get("players") if isinstance(payload, dict) else payload
    rows: List[Dict[str, Any]] = []
    iterable = source.items() if isinstance(source, dict) else enumerate(source or [])
    for key, raw in iterable:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("player") or raw.get("player_name") or raw.get("name") or (key if isinstance(key, str) else "")).strip()
        if name:
            rows.append({"player": name, **{field: _num(raw.get(field)) for field in ("elo", "hard_elo", "clay_elo", "grass_elo")}})
    return sorted({r["player"].casefold(): r for r in rows}.values(), key=lambda r: r["player"].casefold())


def _h2h() -> Dict[str, Any]:
    try:
        value = json.loads(H2H_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def render(output: Path) -> None:
    players = json.dumps(_players(), ensure_ascii=False, separators=(",", ":"))
    h2h = json.dumps(_h2h(), ensure_ascii=False, separators=(",", ":"))
    html = r'''<!doctype html><html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlinQ</title>
<style>:root{--bg:#07111f;--panel:#0e1b2d;--line:#29405e;--text:#eef5ff;--muted:#8fa4bd;--cyan:#38d5ff;--green:#61d6a7;--warn:#ffcc66}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#10233d,#07111f 45%,#050b14);color:var(--text);font:15px/1.45 system-ui,sans-serif;min-height:100vh}main{width:min(980px,calc(100% - 28px));margin:auto;padding:42px 0}.sub{color:var(--muted)}.card,#result{background:rgba(14,27,45,.96);border:1px solid var(--line);border-radius:22px;padding:24px;box-shadow:0 22px 70px #0006}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}label{display:block;color:#b9cbe0;font-size:12px;font-weight:800;margin-bottom:7px}.search{position:relative}input,select,button{width:100%;border-radius:13px;border:1px solid #2b4668;background:#081525;color:var(--text);padding:14px;font:inherit}input:focus{outline:none;border-color:var(--cyan)}.drop{display:none;position:absolute;z-index:20;top:54px;left:0;right:0;max-height:330px;overflow:auto;background:#091524;border:1px solid #315072;border-radius:13px;padding:6px;box-shadow:0 18px 45px #000b}.drop.open{display:block}.opt{display:block;text-align:left;border:0;background:transparent;margin:0;padding:10px;cursor:pointer}.opt:hover{background:#14263e}.opt b{display:block}.tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}.tag{font-size:10px;border:1px solid #36506d;border-radius:99px;padding:2px 6px;color:#7990aa}.tag.ok{color:#8cf0c5;border-color:#177a59;background:#073322}.controls{display:grid;grid-template-columns:220px 1fr;gap:14px;align-items:end;margin-top:18px}button{background:linear-gradient(90deg,var(--green),var(--cyan));color:#04120d;border:0;font-weight:900;cursor:pointer}button:disabled{opacity:.4;cursor:not-allowed}.help{color:var(--muted);font-size:12px}.error{color:var(--warn)}#result{display:none;margin-top:18px}.winner{font-size:28px;font-weight:900}.status{color:var(--green);font-weight:900}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:18px}.metric{padding:13px;background:#091524;border:1px solid var(--line);border-radius:12px;color:var(--muted)}.metric b{display:block;color:var(--text);font-size:18px;margin-top:4px}@media(max-width:760px){.grid,.controls,.metrics{grid-template-columns:1fr}}</style></head>
<body><main><h1>BlinQ</h1><p class="sub">Stabilné mená iba z thinq/data/elo/ta_elo_ratings.json.</p><section class="card"><div class="grid"><div><label>Player 1</label><div class="search"><input id="p1" autocomplete="off" placeholder="Začni písať meno"><div id="d1" class="drop"></div></div><div id="t1" class="tags"></div></div><div><label>Player 2</label><div class="search"><input id="p2" autocomplete="off" placeholder="Začni písať meno"><div id="d2" class="drop"></div></div><div id="t2" class="tags"></div></div></div><div class="controls"><div><label>Povrch</label><select id="surface"><option value="elo">Overall</option><option value="hard_elo">Hard</option><option value="clay_elo">Clay</option><option value="grass_elo">Grass</option></select></div><button id="run" disabled>Vypočítať predikciu</button></div><p id="help" class="help">Vyber dvoch rozdielnych hráčov.</p></section><section id="result"></section></main>
<script>const players=__PLAYERS__,h2hCache=__H2H__,fields=["elo","hard_elo","clay_elo","grass_elo"],labels={elo:"Overall",hard_elo:"Hard",clay_elo:"Clay",grass_elo:"Grass"},sel={p1:null,p2:null};const valid=v=>v!==null&&v!==""&&Number.isFinite(Number(v));const compact=v=>String(v||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]+/g,"");const tags=p=>fields.map(k=>`<span class="tag ${valid(p[k])?'ok':''}">${labels[k]} ${valid(p[k])?Math.round(p[k]):'N/A'}</span>`).join("");
function choose(id,p){sel[id]=p;document.getElementById(id).value=p.player;document.getElementById(id==='p1'?'t1':'t2').innerHTML=tags(p);document.getElementById(id==='p1'?'d1':'d2').classList.remove('open');state()}
function show(id){const q=document.getElementById(id).value.trim().toLowerCase(),other=sel[id==='p1'?'p2':'p1'],box=document.getElementById(id==='p1'?'d1':'d2'),found=players.filter(p=>(!q||p.player.toLowerCase().includes(q))&&(!other||p.player!==other.player)).slice(0,40);box.innerHTML=found.length?found.map((p,i)=>`<button class="opt" data-i="${players.indexOf(p)}"><b>${p.player} · ELO ${valid(p.elo)?Math.round(p.elo):'N/A'}</b><span class="tags">${tags(p)}</span></button>`).join(''):'<div class="help">No match found in dedicated ELO cache.</div>';box.classList.add('open');box.querySelectorAll('.opt').forEach(b=>b.onclick=()=>choose(id,players[Number(b.dataset.i)]))}
function state(){const same=sel.p1&&sel.p2&&sel.p1.player===sel.p2.player;document.getElementById('run').disabled=!sel.p1||!sel.p2||same;document.getElementById('help').innerHTML=same?'<span class="error">Rovnakého hráča nemožno vybrať dvakrát.</span>':'Vyber dvoch rozdielnych hráčov.'}
['p1','p2'].forEach(id=>{const e=document.getElementById(id);e.onfocus=()=>show(id);e.oninput=()=>{sel[id]=null;document.getElementById(id==='p1'?'t1':'t2').innerHTML='';show(id);state()}});
function h2h(a,b){const pairs=h2hCache&&h2hCache.pairs&&typeof h2hCache.pairs==='object'?h2hCache.pairs:{};const an=compact(a.player),bn=compact(b.player);for(const x of Object.values(pairs)){if(!x||typeof x!=='object')continue;const events=Array.isArray(x.events)?x.events:[];const names=[x.pick,x.opponent,x.player1,x.player2,...events.flatMap(e=>[e.home_name,e.away_name])].filter(Boolean).map(compact);if(!names.includes(an)||!names.includes(bn))continue;let aw=0,bw=0;events.forEach(e=>{const w=compact(e.winner_name||e.winner);if(w===an)aw++;else if(w===bn)bw++});return events.length?`${aw}-${bw} (${events.length})`:'No H2H data'}return 'No H2H data'}
const prob=d=>1/(1+10**(-d/400));document.getElementById('run').onclick=()=>{const a=sel.p1,b=sel.p2,k=document.getElementById('surface').value,box=document.getElementById('result');box.style.display='block';if(!a||!b){box.innerHTML='<p class="error">No match.</p>';return}const r1=valid(a[k])?Number(a[k]):null,r2=valid(b[k])?Number(b[k]):null;if(r1===null||r2===null){box.innerHTML=`<p class="error">No ELO match for ${labels[k]}.</p>`;return}const p1=prob(r1-r2),p2=1-p1,tie=p1===.5,sym=Math.abs(p1+prob(r2-r1)-1)<=1e-12,w=tie?'NO_PREDICTION':p1>.5?a.player:b.player;box.innerHTML=`<div class="status">${tie?'NO_PREDICTION':'PREDICTION'}</div><div class="winner">${w}</div><div class="metrics"><div class="metric">${a.player}<b>${(p1*100).toFixed(2)}%</b></div><div class="metric">${b.player}<b>${(p2*100).toFixed(2)}%</b></div><div class="metric">ELO ${labels[k]}<b>${Math.round(r1)} | ${Math.round(r2)}</b></div><div class="metric">ELO rozdiel<b>${(r1-r2).toFixed(0)}</b></div><div class="metric">H2H P1-P2<b>${h2h(a,b)}</b></div></div><p class="sub">A/B symmetry: ${sym?'PASS':'FAIL'} · complement ${(p1+prob(r2-r1)).toFixed(8)}</p>`};</script></body></html>'''.replace("__PLAYERS__", players).replace("__H2H__", h2h)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
