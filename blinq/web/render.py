"""Generate the static BlinQ player comparison website."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from blinq.service import BlinqService


def _public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: row.get(key)
        for key in ("player", "elo", "hard_elo", "clay_elo", "grass_elo")
    }


def render(output: Path) -> None:
    rows = [_public(row) for row in BlinqService().players() if row.get("player")]
    rows.sort(key=lambda row: str(row.get("player") or "").casefold())
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    html = r'''<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BlinQ</title>
<style>
:root{--bg:#07111f;--panel:#0e1b2d;--panel2:#091524;--line:#21334c;--text:#eef5ff;--muted:#8fa4bd;--cyan:#38d5ff;--green:#61d6a7;--warn:#ffcc66;--red:#fb7185}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at top left,#10233d 0,#07111f 42%,#050b14 100%);color:var(--text);font:15px/1.45 Inter,Segoe UI,system-ui,sans-serif}
main{width:min(1120px,calc(100% - 28px));margin:auto;padding:42px 0 70px}h1{margin:0;font-size:clamp(34px,7vw,62px);line-height:1}.sub{color:var(--muted);margin:10px 0 28px}.card{width:min(900px,100%);margin:auto;background:linear-gradient(180deg,rgba(17,29,47,.97),rgba(9,17,30,.97));border:1px solid #29405e;border-radius:24px;padding:26px;box-shadow:0 22px 70px #0007}.card-title{font-size:12px;color:var(--cyan);font-weight:900;letter-spacing:.14em;text-transform:uppercase;margin-bottom:18px}.players-grid{display:grid;grid-template-columns:1fr 58px 1fr;gap:14px;align-items:start}.versus{height:54px;display:flex;align-items:center;justify-content:center;color:var(--cyan);font-size:12px;font-weight:900;letter-spacing:.12em;margin-top:24px}.field label,.surface-field label{display:block;color:#b9cbe0;font-size:12px;font-weight:800;margin:0 0 7px}.search-wrap{position:relative}.search-input{width:100%;height:54px;border-radius:14px;border:1px solid #2b4668;background:#081525;color:var(--text);padding:0 44px 0 15px;font:700 16px inherit;outline:none;transition:.15s}.search-input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(56,213,255,.12)}.search-icon{position:absolute;right:15px;top:15px;color:#7dd3fc;pointer-events:none}.dropdown{display:none;position:absolute;z-index:30;left:0;right:0;top:60px;max-height:330px;overflow:auto;background:#091524;border:1px solid #315072;border-radius:14px;box-shadow:0 18px 45px #000b;padding:6px}.dropdown.open{display:block}.option{display:block;width:100%;text-align:left;border:0;border-radius:10px;background:transparent;color:var(--text);padding:10px;cursor:pointer}.option:hover,.option.active{background:#13263e}.option-name{display:block;font-weight:850;font-size:14px}.elo-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.elo-tag{font-size:10px;font-weight:850;padding:2px 6px;border-radius:999px;border:1px solid #36506d;color:#7990aa;background:#0b1828}.elo-tag.ok{color:#8cf0c5;border-color:#177a59;background:#073322}.availability{min-height:31px;display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.empty-note{padding:14px;color:var(--muted)}.controls{display:grid;grid-template-columns:220px 1fr;gap:14px;align-items:end;margin-top:18px}.surface-select{width:100%;height:50px;border-radius:13px;border:1px solid #2b4668;background:#081525;color:var(--text);padding:0 13px;font:700 14px inherit}.run{height:50px;border:0;border-radius:13px;background:linear-gradient(90deg,#34d399,#38d5ff);color:#04120d;font:900 15px inherit;cursor:pointer;box-shadow:0 10px 28px rgba(52,211,153,.18)}.run:disabled{cursor:not-allowed;filter:grayscale(.9);opacity:.42;box-shadow:none}.helper{margin:12px 0 0;color:var(--muted);font-size:12px}.error{color:var(--warn);font-weight:750}.result{display:none;width:min(900px,100%);margin:18px auto 0;background:rgba(14,27,45,.94);border:1px solid var(--line);border-radius:22px;padding:24px}.result.show{display:block}.status{color:var(--green);font-weight:900;letter-spacing:.1em;font-size:12px}.winner{font-size:28px;font-weight:900;margin-top:4px}.bar{height:16px;background:#18283e;border-radius:99px;overflow:hidden;margin:18px 0}.bar>div{height:100%;background:linear-gradient(90deg,var(--green),#65a8ff)}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:14px;background:var(--panel2);border:1px solid var(--line);border-radius:12px;color:var(--muted)}.metric b{display:block;color:var(--text);font-size:21px;margin-top:4px}.audit{color:var(--muted);margin:14px 0 0;font-size:12px}
@media(max-width:760px){main{padding-top:28px}.card{padding:18px}.players-grid{grid-template-columns:1fr}.versus{height:24px;margin:0}.controls,.metrics{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
  <h1>BlinQ</h1>
  <p class="sub">Porovnanie dvoch hráčov z reálnych ELO dát.</p>
  <section class="card">
    <div class="card-title">Player comparison</div>
    <div class="players-grid">
      <div class="field">
        <label for="p1">Player 1</label>
        <div class="search-wrap">
          <input id="p1" class="search-input" autocomplete="off" placeholder="Začni písať meno hráča">
          <span class="search-icon">⌕</span>
          <div id="p1-list" class="dropdown"></div>
        </div>
        <div id="p1-availability" class="availability"></div>
      </div>
      <div class="versus">VS</div>
      <div class="field">
        <label for="p2">Player 2</label>
        <div class="search-wrap">
          <input id="p2" class="search-input" autocomplete="off" placeholder="Začni písať meno hráča">
          <span class="search-icon">⌕</span>
          <div id="p2-list" class="dropdown"></div>
        </div>
        <div id="p2-availability" class="availability"></div>
      </div>
    </div>
    <div class="controls">
      <div class="surface-field">
        <label for="surface">Povrch</label>
        <select id="surface" class="surface-select">
          <option value="elo">Overall</option>
          <option value="hard_elo">Hard</option>
          <option value="clay_elo">Clay</option>
          <option value="grass_elo">Grass</option>
        </select>
      </div>
      <button id="run" class="run" disabled>Vypočítať predikciu</button>
    </div>
    <p id="helper" class="helper">Vyber dvoch rozdielnych hráčov zo zoznamu ELO cache.</p>
  </section>
  <section id="result" class="result"></section>
</main>
<script>
const players=__PLAYERS__;
const fields=["elo","hard_elo","clay_elo","grass_elo"];
const labels={elo:"Overall",hard_elo:"Hard",clay_elo:"Clay",grass_elo:"Grass"};
const byName=new Map(players.map(p=>[p.player.toLocaleLowerCase(),p]));
const selected={p1:null,p2:null};
const valid=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v));
const tagHtml=p=>fields.map(k=>`<span class="elo-tag ${valid(p[k])?'ok':''}">${labels[k]} ${valid(p[k])?'✓':'×'}</span>`).join("");

function setPlayer(id,player){
  selected[id]=player;
  document.getElementById(id).value=player?player.player:"";
  document.getElementById(id+"-availability").innerHTML=player?tagHtml(player):"";
  document.getElementById(id+"-list").classList.remove("open");
  updateState();
}
function updateState(){
  const same=selected.p1&&selected.p2&&selected.p1.player===selected.p2.player;
  const ready=selected.p1&&selected.p2&&!same;
  document.getElementById("run").disabled=!ready;
  document.getElementById("helper").innerHTML=same?'<span class="error">Rovnakého hráča nemožno vybrať dvakrát.</span>':'Vyber dvoch rozdielnych hráčov zo zoznamu ELO cache.';
}
function renderOptions(id,query){
  const other=id==="p1"?selected.p2:selected.p1;
  const q=query.trim().toLocaleLowerCase();
  const matches=players.filter(p=>(!q||p.player.toLocaleLowerCase().includes(q))&&(!other||p.player!==other.player)).slice(0,40);
  const box=document.getElementById(id+"-list");
  box.innerHTML=matches.length?matches.map(p=>`<button type="button" class="option" data-player="${encodeURIComponent(p.player)}"><span class="option-name">${p.player}</span><span class="elo-tags">${tagHtml(p)}</span></button>`).join(""):'<div class="empty-note">Žiadny hráč sa nenašiel.</div>';
  box.classList.add("open");
  box.querySelectorAll(".option").forEach(btn=>btn.addEventListener("click",()=>setPlayer(id,byName.get(decodeURIComponent(btn.dataset.player).toLocaleLowerCase()))));
}
["p1","p2"].forEach(id=>{
  const input=document.getElementById(id);
  input.addEventListener("focus",()=>renderOptions(id,input.value));
  input.addEventListener("input",()=>{selected[id]=null;document.getElementById(id+"-availability").innerHTML="";renderOptions(id,input.value);updateState()});
  input.addEventListener("keydown",event=>{if(event.key==="Escape")document.getElementById(id+"-list").classList.remove("open")});
});
document.addEventListener("click",event=>{if(!event.target.closest(".search-wrap"))document.querySelectorAll(".dropdown").forEach(x=>x.classList.remove("open"))});

const probability=diff=>1/(1+Math.pow(10,-diff/400));
function rating(player,key){return valid(player[key])?Number(player[key]):null}
document.getElementById("run").addEventListener("click",()=>{
  const box=document.getElementById("result"),a=selected.p1,b=selected.p2,key=document.getElementById("surface").value;
  box.classList.add("show");
  if(!a||!b||a.player===b.player){box.innerHTML='<p class="error">Vyber dvoch rozdielnych hráčov.</p>';return}
  const r1=rating(a,key),r2=rating(b,key);
  if(r1===null||r2===null){box.innerHTML=`<p class="error">Pre povrch ${labels[key]} chýbajú ELO dáta. Vyber dostupný povrch.</p>`;return}
  const p1=probability(r1-r2),swapped=probability(r2-r1),p2=1-p1;
  const tie=Math.abs(p1-.5)<=1e-12,symmetry=Math.abs((p1+swapped)-1)<=1e-12;
  const winner=tie?"NO_PREDICTION":(p1>.5?a.player:b.player);
  box.innerHTML=`<div class="status">${tie?'NO_PREDICTION':'PREDICTION'}</div><div class="winner">${winner}</div><div class="bar"><div style="width:${(p1*100).toFixed(2)}%"></div></div><div class="metrics"><div class="metric">${a.player}<b>${(p1*100).toFixed(2)}%</b></div><div class="metric">${b.player}<b>${(p2*100).toFixed(2)}%</b></div><div class="metric">ELO rozdiel<b>${(r1-r2).toFixed(0)}</b></div></div><p class="audit">Povrch: ${labels[key]} · A/B symmetry: ${symmetry?'PASS':'FAIL'} · Complement sum: ${(p1+swapped).toFixed(8)}</p>`;
});
</script>
</body>
</html>'''.replace("__PLAYERS__", payload)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
