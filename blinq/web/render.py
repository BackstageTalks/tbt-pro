"""Generate the final BlinQ comparison website."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from blinq.service import BlinqService

H2H_PATH = Path("thinq/data/h2h/h2h_cache.json")


def _h2h() -> Dict[str, Any]:
    try:
        value = json.loads(H2H_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def render(output: Path) -> None:
    players = json.dumps(BlinqService().players(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    h2h = json.dumps(_h2h(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = r'''<!doctype html><html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlinQ</title>
<style>
:root{--bg:#07111f;--panel:#0e1b2d;--line:#29405e;--text:#eef5ff;--muted:#8fa4bd;--cyan:#38d5ff;--green:#61d6a7;--warn:#ffcc66}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#10233d,#07111f 45%,#050b14);color:var(--text);font:15px/1.45 system-ui,sans-serif;min-height:100vh}main{width:min(1020px,calc(100% - 28px));margin:auto;padding:42px 0}.sub{color:var(--muted)}.card,.result,.history{background:rgba(14,27,45,.96);border:1px solid var(--line);border-radius:22px;padding:24px;box-shadow:0 22px 70px #0006}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}label{display:block;color:#b9cbe0;font-size:12px;font-weight:800;margin-bottom:7px}.search{position:relative}input,select,button{width:100%;border-radius:13px;border:1px solid #2b4668;background:#081525;color:var(--text);padding:14px;font:inherit}input:focus{outline:none;border-color:var(--cyan)}.drop{display:none;position:absolute;z-index:20;top:54px;left:0;right:0;max-height:300px;overflow:auto;background:#091524;border:1px solid #315072;border-radius:13px;padding:6px;box-shadow:0 18px 45px #000b}.drop.open{display:block}.opt{display:block;width:100%;text-align:left;border:0;background:transparent;color:var(--text);margin:0;padding:10px;cursor:pointer}.opt:hover{background:#14263e}.opt small{display:block;color:var(--muted);margin-top:2px}.selected{min-height:24px;color:var(--green);font-size:12px;padding-top:6px}.controls{display:grid;grid-template-columns:220px 1fr;gap:14px;align-items:end;margin-top:18px}button{background:linear-gradient(90deg,var(--green),var(--cyan));color:#04120d;border:0;font-weight:900;cursor:pointer}button:disabled{opacity:.4;cursor:not-allowed}.help{color:var(--muted);font-size:12px}.error{color:var(--warn)}.result{display:none;margin-top:18px}.winner{font-size:28px;font-weight:900}.status{color:var(--green);font-weight:900}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:18px}.metric{padding:13px;background:#091524;border:1px solid var(--line);border-radius:12px;color:var(--muted)}.metric b{display:block;color:var(--text);font-size:18px;margin-top:4px}.history{margin-top:18px}.history-head{display:flex;justify-content:space-between;align-items:center}.history-head h2{font-size:16px;margin:0}.clear{width:auto;padding:8px 12px;background:transparent;color:var(--muted);border:1px solid var(--line)}.history-list{display:grid;gap:8px;margin-top:14px}.history-row{display:grid;grid-template-columns:1fr auto 1fr auto;gap:10px;align-items:center;background:#091524;border:1px solid var(--line);border-radius:12px;padding:12px}.empty{color:var(--muted)}@media(max-width:760px){.grid,.controls,.metrics,.history-row{grid-template-columns:1fr}}
</style></head><body><main><h1>BlinQ</h1><p class="sub">Porovnanie dvoch hráčov z centrálneho player registry.</p><section class="card"><div class="grid"><div><label>Player 1</label><div class="search"><input id="p1" autocomplete="off" placeholder="Začni písať meno"><div id="d1" class="drop"></div></div><div id="s1" class="selected"></div></div><div><label>Player 2</label><div class="search"><input id="p2" autocomplete="off" placeholder="Začni písať meno"><div id="d2" class="drop"></div></div><div id="s2" class="selected"></div></div></div><div class="controls"><div><label>Povrch</label><select id="surface"><option value="elo">Overall</option><option value="hard_elo">Hard</option><option value="clay_elo">Clay</option><option value="grass_elo">Grass</option></select></div><button id="run" disabled>Vypočítať predikciu</button></div><p id="help" class="help">Zadaj aspoň 2 znaky a vyber dvoch rozdielnych hráčov.</p></section><section id="result" class="result"></section><section class="history"><div class="history-head"><h2>História porovnaní</h2><button id="clear" class="clear">Vymazať</button></div><div id="history" class="history-list"></div></section></main>
<script>
const players=__PLAYERS__,h2hCache=__H2H__,labels={elo:'Overall',hard_elo:'Hard',clay_elo:'Clay',grass_elo:'Grass'},sel={p1:null,p2:null},historyKey='blinq_history_v2';const valid=v=>v!==null&&v!==''&&Number.isFinite(Number(v)),compact=v=>String(v||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,''),profile=p=>`${p.country_code?`(${p.country_code}) `:''}${p.rank?`#${p.rank}`:'(X)'}`;
function choose(id,p){sel[id]=p;document.getElementById(id).value=p.player;document.getElementById(id==='p1'?'s1':'s2').textContent=`${p.player} ${profile(p)}`;document.getElementById(id==='p1'?'d1':'d2').classList.remove('open');state()}
function show(id){const q=document.getElementById(id).value.trim().toLowerCase(),other=sel[id==='p1'?'p2':'p1'],box=document.getElementById(id==='p1'?'d1':'d2');if(q.length<2){box.innerHTML='<div class="help">Zadaj aspoň 2 znaky.</div>';box.classList.add('open');return}const found=players.filter(p=>(p.player.toLowerCase().includes(q)||String(p.country_code||'').toLowerCase()===q||String(p.rank||'')===q)&&(!other||p.player!==other.player)).slice(0,10);box.innerHTML=found.length?found.map(p=>`<button class="opt" data-i="${players.indexOf(p)}"><b>${p.player}</b><small>${profile(p)}</small></button>`).join(''):'<div class="help">No match found.</div>';box.classList.add('open');box.querySelectorAll('.opt').forEach(b=>b.onclick=()=>choose(id,players[Number(b.dataset.i)]))}
function state(){const same=sel.p1&&sel.p2&&sel.p1.player===sel.p2.player;document.getElementById('run').disabled=!sel.p1||!sel.p2||same}['p1','p2'].forEach(id=>{const e=document.getElementById(id);e.onfocus=()=>show(id);e.oninput=()=>{sel[id]=null;document.getElementById(id==='p1'?'s1':'s2').textContent='';show(id);state()}});document.addEventListener('click',e=>{if(!e.target.closest('.search'))document.querySelectorAll('.drop').forEach(x=>x.classList.remove('open'))});
function h2h(a,b){const pairs=h2hCache?.pairs||{},an=compact(a.player),bn=compact(b.player);for(const x of Object.values(pairs)){if(!x||typeof x!=='object')continue;const events=Array.isArray(x.events)?x.events:[],names=[x.pick,x.opponent,x.player1,x.player2,...events.flatMap(e=>[e.home_name,e.away_name])].filter(Boolean).map(compact);if(!names.includes(an)||!names.includes(bn))continue;let aw=0,bw=0;events.forEach(e=>{const w=compact(e.winner_name||e.winner);if(w===an)aw++;else if(w===bn)bw++});return events.length?`${aw}-${bw} (${events.length})`:'No H2H data'}return 'No H2H data'}
function history(){try{return JSON.parse(localStorage.getItem(historyKey)||'[]')}catch{return[]}}function renderHistory(){const rows=history(),box=document.getElementById('history');box.innerHTML=rows.length?rows.map(r=>`<div class="history-row"><span>${r.p1}</span><span>vs</span><span>${r.p2}</span><b>${r.winner}</b></div>`).join(''):'<div class="empty">Zatiaľ bez histórie.</div>'}function save(row){const rows=history().filter(x=>!(x.p1===row.p1&&x.p2===row.p2&&x.surface===row.surface));rows.unshift(row);localStorage.setItem(historyKey,JSON.stringify(rows.slice(0,20)));renderHistory()}document.getElementById('clear').onclick=()=>{localStorage.removeItem(historyKey);renderHistory()};renderHistory();
const prob=d=>1/(1+10**(-d/400));document.getElementById('run').onclick=()=>{const a=sel.p1,b=sel.p2,k=document.getElementById('surface').value,box=document.getElementById('result');box.style.display='block';const r1=valid(a?.[k])?Number(a[k]):null,r2=valid(b?.[k])?Number(b[k]):null;if(r1===null||r2===null){box.innerHTML=`<p class="error">No ELO data for ${labels[k]}.</p>`;return}const p1=prob(r1-r2),p2=1-p1,swapped=prob(r2-r1),tie=Math.abs(p1-.5)<=1e-12,sym=Math.abs(p1+swapped-1)<=1e-12,w=tie?'NO_PREDICTION':p1>.5?a.player:b.player;box.innerHTML=`<div class="status">${tie?'NO_PREDICTION':'PREDICTION'}</div><div class="winner">${w}</div><div class="metrics"><div class="metric">${a.player} ${profile(a)}<b>${(p1*100).toFixed(2)}%</b></div><div class="metric">${b.player} ${profile(b)}<b>${(p2*100).toFixed(2)}%</b></div><div class="metric">ELO ${labels[k]}<b>${Math.round(r1)} | ${Math.round(r2)}</b></div><div class="metric">ELO rozdiel<b>${(r1-r2).toFixed(0)}</b></div><div class="metric">H2H P1-P2<b>${h2h(a,b)}</b></div></div><p class="sub">A/B symmetry: ${sym?'PASS':'FAIL'} · complement ${(p1+swapped).toFixed(8)}</p>`;save({p1:`${a.player} ${profile(a)}`,p2:`${b.player} ${profile(b)}`,surface:k,winner:w})};
</script></body></html>'''.replace("__PLAYERS__", players).replace("__H2H__", h2h)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
