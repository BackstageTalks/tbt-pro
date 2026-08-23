"""Generate the static BlinQ comparison website."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict
from blinq.service import BlinqService


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key) for key in ("player", "elo", "hard_elo", "clay_elo", "grass_elo")}


def render(output: Path) -> None:
    rows = [_public(row) for row in BlinqService().players() if row.get("player")]
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    html = '''<!doctype html><html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlinQ</title>
<style>:root{--bg:#07111f;--panel:#0e1b2d;--line:#21334c;--text:#eef5ff;--muted:#8fa4bd;--accent:#61d6a7;--warn:#ffcc66}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#06101d,#0b1728);color:var(--text);font:16px system-ui,sans-serif;min-height:100vh}main{width:min(920px,calc(100% - 28px));margin:auto;padding:54px 0}h1{margin:0;font-size:clamp(34px,8vw,64px)}.sub{color:var(--muted);margin:8px 0 34px}.card{background:rgba(14,27,45,.94);border:1px solid var(--line);border-radius:22px;padding:24px;box-shadow:0 22px 70px #0006}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:block;color:var(--muted);font-size:13px;margin:0 0 7px}input,select,button{width:100%;border-radius:12px;border:1px solid var(--line);background:#091524;color:var(--text);padding:14px;font:inherit}button{margin-top:18px;background:var(--accent);color:#04120d;border:0;font-weight:800;cursor:pointer}#result{display:none;margin-top:22px}.winner{font-size:28px;font-weight:800}.status{color:var(--accent);font-weight:700}.bar{height:16px;background:#18283e;border-radius:99px;overflow:hidden;margin:16px 0}.bar>div{height:100%;background:linear-gradient(90deg,var(--accent),#65a8ff)}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:14px;background:#091524;border:1px solid var(--line);border-radius:12px}.metric b{display:block;font-size:21px;margin-top:4px}.error{color:var(--warn)}@media(max-width:650px){.grid,.metrics{grid-template-columns:1fr}}</style></head>
<body><main><h1>BlinQ</h1><p class="sub">Porovnanie dvoch hráčov z reálnych ELO dát.</p><section class="card"><div class="grid"><div><label>Player 1</label><input id="p1" list="players" placeholder="Začni písať meno"></div><div><label>Player 2</label><input id="p2" list="players" placeholder="Začni písať meno"></div></div><datalist id="players"></datalist><div style="margin-top:16px"><label>Povrch</label><select id="surface"><option value="elo">Overall</option><option value="hard_elo">Hard</option><option value="clay_elo">Clay</option><option value="grass_elo">Grass</option></select></div><button id="run">Vypočítať predikciu</button><div id="result"></div></section></main>
<script>const players=__PLAYERS__;const byName=new Map(players.map(x=>[x.player.toLocaleLowerCase(),x]));const list=document.getElementById('players');players.forEach(x=>{const o=document.createElement('option');o.value=x.player;list.appendChild(o)});const prob=d=>1/(1+Math.pow(10,-d/400));const rating=(r,k)=>Number.isFinite(Number(r[k]))?Number(r[k]):(Number.isFinite(Number(r.elo))?Number(r.elo):null);document.getElementById('run').onclick=()=>{const box=document.getElementById('result'),a=byName.get(document.getElementById('p1').value.trim().toLocaleLowerCase()),b=byName.get(document.getElementById('p2').value.trim().toLocaleLowerCase()),k=document.getElementById('surface').value;box.style.display='block';if(!a||!b||a.player===b.player){box.innerHTML='<p class="error">Vyber dvoch rozdielnych hráčov zo zoznamu.</p>';return}const r1=rating(a,k),r2=rating(b,k);if(r1===null||r2===null){box.innerHTML='<p class="error">Chýbajú ELO dáta.</p>';return}const p1=prob(r1-r2),p2=1-p1,tie=Math.abs(p1-.5)<=1e-12,w=tie?'NO_PREDICTION':(p1>.5?a.player:b.player),sym=Math.abs(p1+prob(r2-r1)-1)<=1e-12;box.innerHTML=`<div class="status">${tie?'NO_PREDICTION':'PREDICTION'}</div><div class="winner">${w}</div><div class="bar"><div style="width:${(p1*100).toFixed(2)}%"></div></div><div class="metrics"><div class="metric">${a.player}<b>${(p1*100).toFixed(2)}%</b></div><div class="metric">${b.player}<b>${(p2*100).toFixed(2)}%</b></div><div class="metric">ELO rozdiel<b>${(r1-r2).toFixed(0)}</b></div></div><p class="sub">Symetria A/B: ${sym?'OK':'FAILED'} · ${k}</p>`};</script></body></html>'''.replace("__PLAYERS__", payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
