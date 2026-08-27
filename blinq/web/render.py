"""Generate the final BlinQ comparison website."""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from blinq.service import BlinqService

H2H_PATH = Path("thinq/data/h2h/h2h_cache.json")
LOGO_PATH = ""
DISCLAIMER = "This data is provided for informational and analytical purposes only. Powered by BackstageTalks Statistical Engine."


def _image_data_uri(candidates: tuple[str, ...]) -> str:
    root = Path(__file__).resolve().parents[2]
    for relative in candidates:
        path = root / relative
        if path.is_file():
            suffix = path.suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return ""


def _logo_source() -> str:
    return _image_data_uri((
        "corq/web/assets/tbt_ai_goat_icon_new.png",
        "corq/site/assets/tbt_ai_goat_icon_new.png",
    ))


def _blinq_logo_source() -> str:
    return _image_data_uri((
        "blinq/web/assets/blinq_logo.png",
    ))

def _h2h() -> Dict[str, Any]:
    try:
        value = json.loads(H2H_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _nav_items() -> List[Dict[str, str]]:
    try:
        from corq.web.paths import NAV_ITEMS
    except Exception:
        return []
    items: List[Dict[str, str]] = []
    for item in NAV_ITEMS:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "")
            path = str(item.get("path") or item.get("url") or "")
            key = str(item.get("key") or label)
        elif isinstance(item, (list, tuple)):
            label = str(item[0]) if len(item) > 0 else ""
            path = str(item[1]) if len(item) > 1 else ""
            key = str(item[2]) if len(item) > 2 else label
        else:
            continue
        if label.lower() in {"all", "all audit"}:
            label = "Audit"
        elif label.lower() in {"tg rss", "telegram rss"}:
            label = "TG"
        items.append({"label": label, "path": path, "key": key})
    return items


def _nav_html() -> str:
    links = []
    found_blinq = False
    for item in _nav_items():
        label, path, key = item["label"], item["path"], item["key"]
        active = label.lower() == "blinq" or key.lower() == "blinq"
        found_blinq = found_blinq or active
        href = f"../{path}" if path.endswith(".xml") else f"../{path}/"
        links.append(f'<a class="{"active" if active else ""}" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
    if not found_blinq:
        links.insert(4, '<a class="active" href="./">BlinQ</a>')
    return "".join(links)


def render(output: Path) -> None:
    players = json.dumps(BlinqService().players(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    h2h = json.dumps(_h2h(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    nav = _nav_html()
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_publishable_key = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    page = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlinQ</title><script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<style>
:root{--bg:#07111f;--panel:#0e1b2d;--line:#29405e;--text:#eef5ff;--muted:#8fa4bd;--cyan:#38d5ff;--green:#61d6a7;--warn:#ffcc66}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#10233d,#07111f 45%,#050b14);color:var(--text);font:14px/1.5 Inter,Segoe UI,Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;min-height:100vh}.wrap{max-width:1920px;margin:0 auto;padding:14px}.topbar{display:flex;align-items:center;gap:18px;min-height:68px}.brand{display:flex;align-items:center;gap:12px;min-width:230px}.brand-mark{width:60px;height:60px;border-radius:50%;border:1px solid rgba(56,213,255,.75);box-shadow:0 0 22px rgba(56,213,255,.2);overflow:hidden;background:#071827}.brand-logo{width:100%;height:100%;object-fit:contain}.brand-title{font-family:inherit;font-weight:900;font-size:18px}.brand-sub{font-size:9px;color:var(--muted);letter-spacing:.13em;text-transform:uppercase}.nav{display:flex;gap:8px;flex-wrap:wrap}.nav a{color:#bcd1ea;text-decoration:none;border:1px solid #22344d;background:#0d1727;padding:7px 12px;border-radius:999px;font-weight:700}.nav a.active{border-color:var(--cyan);color:#fff;box-shadow:0 0 16px rgba(56,213,255,.16)}.hero{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0 18px}.hero-panel{background:linear-gradient(180deg,rgba(17,29,47,.92),rgba(9,17,30,.92));border:1px solid #23344d;border-radius:14px;padding:11px}.hero-title{font-size:10px;color:var(--cyan);text-transform:uppercase;letter-spacing:.14em;font-weight:900}.hero-line{margin-top:3px;color:#dbeafe;font-size:12px}.minimal-header{width:min(1020px,100%);margin:0 auto;padding:10px 0 0}.engine-label{color:#eef5ff;font-size:16px;font-weight:800;letter-spacing:-.01em}.engine-label span{display:block;color:var(--muted);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;margin:2px 0 0}.content{width:min(1020px,100%);margin:auto;padding:8px 0 28px}.blinq-logo-wrap{display:flex;justify-content:center;align-items:center;width:min(420px,90vw);height:170px;margin:0 auto 8px;overflow:visible}.blinq-logo{display:block;width:100%;height:100%;object-fit:contain;object-position:center;transform:none;mix-blend-mode:normal;filter:none;image-rendering:auto}.blinq-logo-fallback{font-size:42px;font-weight:800;letter-spacing:-.04em;color:#fff}.motto{text-align:center;color:#d8e7f8;font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin:-4px 0 18px}.motto-sep{color:var(--cyan);padding:0 9px}.lead{color:var(--muted)}.card,.result,.history{background:rgba(14,27,45,.96);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 22px 70px #0006}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}label{display:block;color:#d2e1f2;font-size:12px;font-weight:700;margin-bottom:7px}.search{position:relative}input,select,button{width:100%;border-radius:12px;border:1px solid #2b4668;background:#081525;color:var(--text);padding:13px;font:inherit}input:focus{outline:none;border-color:var(--cyan)}.drop{display:none;position:absolute;z-index:20;top:52px;left:0;right:0;max-height:300px;overflow:auto;background:#091524;border:1px solid #315072;border-radius:12px;padding:6px;box-shadow:0 18px 45px #000b}.drop.open{display:block}.opt{display:block;width:100%;text-align:left;border:0;background:transparent;color:var(--text);margin:0;padding:10px;cursor:pointer}.opt:hover{background:#14263e}.opt small{display:block;color:var(--muted);margin-top:2px}.selected{min-height:24px;color:var(--green);font-size:12px;padding-top:6px}.controls{display:grid;grid-template-columns:220px 1fr;gap:14px;align-items:end;margin-top:17px}.run{background:linear-gradient(90deg,var(--green),var(--cyan));color:#04120d;border:0;font-weight:900;cursor:pointer}.run:disabled{opacity:.4;cursor:not-allowed}.help{color:var(--muted);font-size:12px}.error{color:#ff8a68;font-weight:700}.result{display:none;margin-top:16px}.winner{font-size:28px;font-weight:900}.status{color:var(--green);font-weight:900}.prob-bar{display:flex;height:14px;border-radius:999px;overflow:hidden;background:#172a43;margin-top:16px}.prob-left{background:linear-gradient(90deg,var(--green),#43c9c3)}.prob-right{background:linear-gradient(90deg,#559ff7,#766de8)}.prob-labels{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:6px}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:16px}.metric{padding:12px;background:#091524;border:1px solid var(--line);border-radius:11px;color:var(--muted)}.metric b{display:block;color:var(--text);font-size:17px;margin-top:4px}.history{position:relative;margin-top:16px}.history.guest .history-list,.history.guest .clear{filter:blur(5px);pointer-events:none;user-select:none}.history-overlay{display:none;position:absolute;inset:52px 18px 18px;z-index:3;align-items:center;justify-content:center;text-align:center;color:var(--text);font-weight:800;background:rgba(7,17,31,.28);border-radius:12px}.history.guest .history-overlay{display:flex}.history-head{display:flex;justify-content:space-between;align-items:center}.history-head h2{font-size:17px;font-weight:700;letter-spacing:-.01em;margin:0}.clear{width:auto;padding:8px 12px;background:transparent;color:var(--muted);border:1px solid var(--line)}.history-list{display:grid;gap:8px;margin-top:14px}.history-row{display:grid;grid-template-columns:1fr auto 1fr auto;gap:10px;align-items:center;background:#091524;border:1px solid var(--line);border-radius:11px;padding:11px}.empty{color:var(--muted)}.auth-card{position:relative;margin-bottom:16px;background:#0a1728;border:1px solid var(--line);border-radius:14px;padding:14px 14px 34px}.auth-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.auth-row input{width:auto;flex:1;min-width:220px}.auth-row button{width:auto;cursor:pointer}.auth-row button:disabled{opacity:.5;cursor:not-allowed}.access-note{color:var(--muted);font-size:12px;margin-top:8px}.free-note{position:absolute;right:16px;bottom:10px;margin:0;color:var(--green);text-align:right}.auth-message{min-height:0}.auth-message:not(:empty){display:inline-block;margin-top:10px;padding:7px 10px;border-radius:9px;border:1px solid rgba(255,122,92,.55);background:rgba(255,92,74,.10);color:#ff9a78;font-weight:700}.auth-message.error{color:#ff725c;border-color:rgba(255,96,74,.78);background:rgba(255,76,54,.14)}.footer{margin:24px 0 6px;text-align:center;color:#6f86a4;font-size:11px}@media(max-width:900px){.topbar{align-items:flex-start;flex-direction:column}.hero{grid-template-columns:1fr}}@media(max-width:760px){.grid,.controls,.metrics,.history-row{grid-template-columns:1fr}.brand-mark{width:54px;height:54px}.blinq-logo-wrap{width:min(420px,92vw);height:150px}.auth-card{padding-bottom:14px}.free-note{position:static;margin-top:10px;text-align:left}}
</style></head><body><div class="wrap"><header class="topbar"><div class="brand"><div class="brand-mark"><img class="brand-logo" src="__LOGO__" alt="BackstageTalks"></div><div><div class="brand-title">BackstageTalks</div><div class="brand-sub">Statistical Engine</div></div></div><nav class="nav" aria-label="Main navigation">__NAV__</nav></header><main class="content"><div class="blinq-logo-wrap">__BLINQ_LOGO__</div><div class="motto">Ignore the hype.<span class="motto-sep">—</span>Follow the data.</div><section class="hero"><article class="hero-panel"><div class="hero-title">THE PLATFORM</div><div class="hero-line">Independent tennis intelligence for data enthusiasts.</div></article><article class="hero-panel"><div class="hero-title">THE METHOD</div><div class="hero-line">Real player data meets transparent model logic.</div></article><article class="hero-panel"><div class="hero-title">THE PURPOSE</div><div class="hero-line"><strong>Less guesswork. More edge.</strong></div></article></section><section class="auth-card"><div id="signedOut"><div class="auth-row"><input id="authEmail" type="email" placeholder="Email"><input id="authPassword" type="password" placeholder="Password"><button id="signIn">Sign in</button><button id="signUp">Create account</button><button id="forgotPassword">Forgot password</button></div><div class="access-note free-note">New accounts receive 10 free successful predictions.</div><div id="authMessage" class="auth-message" aria-live="polite"></div></div><div id="signedIn" style="display:none"><div class="auth-row"><b id="userEmail"></b><span id="credits"></span><button id="signOut">Sign out</button></div><div id="accessMessage" class="access-note"></div></div></section><section class="card"><div class="grid"><div><label>Player 1</label><div class="search"><input id="p1" autocomplete="off" placeholder="Type at least 2 characters"><div id="d1" class="drop"></div></div><div id="s1" class="selected"></div></div><div><label>Player 2</label><div class="search"><input id="p2" autocomplete="off" placeholder="Type at least 2 characters"><div id="d2" class="drop"></div></div><div id="s2" class="selected"></div></div></div><div class="controls"><div><label>Surface</label><select id="surface"><option value="elo">Overall</option><option value="hard_elo">Hard</option><option value="clay_elo">Clay</option><option value="grass_elo">Grass</option></select></div><button id="run" class="run" disabled>Calculate prediction</button></div><p class="help">Type at least 2 characters and select two different players.</p></section><section id="result" class="result"></section><section id="historySection" class="history guest"><div class="history-head"><h2>Comparison history</h2><button id="clear" class="clear">Clear</button></div><div id="history" class="history-list"></div><div class="history-overlay">Sign in to view your comparison history</div></section><footer class="footer">__DISCLAIMER__</footer></main></div>
<script>
const SUPABASE_URL='__SUPABASE_URL__',SUPABASE_PUBLISHABLE_KEY='__SUPABASE_PUBLISHABLE_KEY__';const BLINQ_PORTAL_PATH='/follow-the-data/',BLINQ_PORTAL_URL=`${location.origin}${BLINQ_PORTAL_PATH}`;const sb=(SUPABASE_URL&&SUPABASE_PUBLISHABLE_KEY&&window.supabase)?supabase.createClient(SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY):null;let accessToken='';const authMessage=document.getElementById('authMessage');const setAuthMessage=(text,isError=false)=>{authMessage.textContent=text||'';authMessage.classList.toggle('error',Boolean(isError))};if(!sb){setAuthMessage('Account service is temporarily unavailable. Please try again later.',true);['signIn','signUp','forgotPassword'].forEach(id=>document.getElementById(id).disabled=true)}
const API_ENDPOINT=location.hostname.endsWith('github.io')?'https://agreeable-sky-011a7fe10.7.azurestaticapps.net/api/blinq/predict':'/api/blinq/predict';const players=__PLAYERS__,h2hCache=__H2H__,labels={elo:'Overall',hard_elo:'Hard',clay_elo:'Clay',grass_elo:'Grass'},sel={p1:null,p2:null},historyKey='blinq_history_guest',currentUserId='';const valid=v=>v!==null&&v!==''&&Number.isFinite(Number(v)),compact=v=>String(v||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,''),profile=p=>`${p.country_code?`(${String(p.country_code).toUpperCase()}) · `:''}${p.rank?`#${p.rank}`:'(X)'}`;
function choose(id,p){sel[id]=p;document.getElementById(id).value=p.player;document.getElementById(id==='p1'?'s1':'s2').textContent=profile(p);document.getElementById(id==='p1'?'d1':'d2').classList.remove('open');state()}
function show(id){const q=document.getElementById(id).value.trim().toLowerCase(),other=sel[id==='p1'?'p2':'p1'],box=document.getElementById(id==='p1'?'d1':'d2');if(q.length<2){box.innerHTML='<div class="help">Type at least 2 characters.</div>';box.classList.add('open');return}const found=players.filter(p=>(p.player.toLowerCase().includes(q)||String(p.country_code||'').toLowerCase()===q||String(p.rank||'')===q)&&(!other||p.player!==other.player)).slice(0,10);box.innerHTML=found.length?found.map(p=>`<button class="opt" data-i="${players.indexOf(p)}"><b>${p.player}</b><small>${profile(p)}</small></button>`).join(''):'<div class="help">No match found.</div>';box.classList.add('open');box.querySelectorAll('.opt').forEach(b=>b.onclick=()=>choose(id,players[Number(b.dataset.i)]))}
function state(){const same=sel.p1&&sel.p2&&sel.p1.player===sel.p2.player;document.getElementById('run').disabled=!sel.p1||!sel.p2||same}['p1','p2'].forEach(id=>{const e=document.getElementById(id);e.onfocus=()=>show(id);e.oninput=()=>{sel[id]=null;document.getElementById(id==='p1'?'s1':'s2').textContent='';show(id);state()}});document.addEventListener('click',e=>{if(!e.target.closest('.search'))document.querySelectorAll('.drop').forEach(x=>x.classList.remove('open'))});
function h2h(a,b){const pairs=h2hCache?.pairs||{},an=compact(a.player),bn=compact(b.player);for(const x of Object.values(pairs)){if(!x||typeof x!=='object')continue;const events=Array.isArray(x.events)?x.events:[],names=[x.pick,x.opponent,x.player1,x.player2,...events.flatMap(e=>[e.home_name,e.away_name])].filter(Boolean).map(compact);if(!names.includes(an)||!names.includes(bn))continue;let aw=0,bw=0;events.forEach(e=>{const w=compact(e.winner_name||e.winner);if(w===an)aw++;else if(w===bn)bw++});return events.length?`${aw}-${bw} (${events.length})`:'No previous matches'}return 'No previous matches'}
function history(){if(!currentUserId)return[];try{return JSON.parse(localStorage.getItem(historyKey)||'[]')}catch{return[]}}function renderHistory(){const rows=history(),box=document.getElementById('history');box.innerHTML=rows.length?rows.map(r=>`<div class="history-row"><span>${r.p1}</span><span>vs</span><span>${r.p2}</span><b>${r.winner}<small style="display:block;color:var(--muted)">${labels[r.surface]||r.surface} · ${r.time?new Date(r.time).toLocaleString('en-GB'):''}</small></b></div>`).join(''):'<div class="empty">No comparisons yet.</div>'}function save(row){if(!currentUserId)return;const rows=history().filter(x=>!(x.p1===row.p1&&x.p2===row.p2&&x.surface===row.surface));rows.unshift(row);localStorage.setItem(historyKey,JSON.stringify(rows.slice(0,20)));renderHistory()}document.getElementById('clear').onclick=()=>{if(!currentUserId)return;localStorage.removeItem(historyKey);renderHistory()};renderHistory();
async function refreshAuth(){if(!sb)return;const {data}=await sb.auth.getSession();const session=data?.session;accessToken=session?.access_token||'';currentUserId=session?.user?.id||'';historyKey=currentUserId?`blinq_history_v3_${currentUserId}`:'blinq_history_guest';document.getElementById('historySection').classList.toggle('guest',!session);renderHistory();document.getElementById('signedOut').style.display=session?'none':'block';document.getElementById('signedIn').style.display=session?'block':'none';if(session){document.getElementById('userEmail').textContent=session.user.email||'';await checkAccess()}}async function checkAccess(){if(!accessToken)return;const res=await fetch(API_ENDPOINT.replace('/predict','/access/status'),{headers:{Authorization:`Bearer ${accessToken}`}});const d=await res.json();document.getElementById('credits').textContent=d.credits_remaining==null?'':`Free predictions: ${d.credits_remaining} of ${d.credits_granted}`;const msg=d.access_status==='EXPIRED'?'Your BlinQ access has expired.':d.access_status==='PAYMENT_PENDING'?'Payment verification pending. Your BlinQ Pro access will be activated after the payment email is matched with your account.':'';document.getElementById('accessMessage').textContent=msg}if(sb){document.getElementById('signUp').onclick=async()=>{const email=document.getElementById('authEmail').value.trim(),password=document.getElementById('authPassword').value;const {error}=await sb.auth.signUp({email,password,options:{emailRedirectTo:BLINQ_PORTAL_URL}});setAuthMessage(error?'We could not create the account right now. Please try again in a moment.':'Check your email to confirm the account.',Boolean(error))};document.getElementById('signIn').onclick=async()=>{const email=document.getElementById('authEmail').value.trim(),password=document.getElementById('authPassword').value;const {error}=await sb.auth.signInWithPassword({email,password});if(error){setAuthMessage('Sign in failed. Please check your email and password.',true);return}setAuthMessage('Signed in successfully.');await refreshAuth()};document.getElementById('forgotPassword').onclick=async()=>{const email=document.getElementById('authEmail').value.trim();if(!email){alert('Enter your email first.');return}const {error}=await sb.auth.resetPasswordForEmail(email,{redirectTo:`${BLINQ_PORTAL_URL}?recovery=1`});setAuthMessage(error?'We could not send the reset email right now. Please try again in a moment.':'Password reset email sent.',Boolean(error))};document.getElementById('signOut').onclick=async()=>{await sb.auth.signOut();await refreshAuth()};sb.auth.onAuthStateChange(()=>refreshAuth());refreshAuth()}
document.getElementById('run').onclick=async()=>{const a=sel.p1,b=sel.p2,k=document.getElementById('surface').value,box=document.getElementById('result'),button=document.getElementById('run');box.style.display='block';button.disabled=true;button.textContent='Calculating...';box.innerHTML='<p class="lead">Calculating ThinQ components and model consistency...</p>';try{const response=await fetch(API_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json',...(accessToken?{Authorization:`Bearer ${accessToken}`}:{})},body:JSON.stringify({player1:a.player,player2:b.player,surface:labels[k]})});const raw=await response.text();let data;try{data=JSON.parse(raw)}catch{throw new Error(`Prediction API returned ${response.status} ${response.statusText} instead of JSON`)}if(!response.ok)throw new Error((data.reason||`Prediction API failed (${response.status})`)+(data.error_type?` [${data.error_type}]`:''));const p1=Number(data.player1_probability??.5),p2=Number(data.player2_probability??.5),winner=data.winner||'NO_PREDICTION',audit=data.symmetry_audit||{},elo=data.elo||{},h=data.h2h||{};const elo1=elo.pick_elo??a[k]??a.elo,elo2=elo.opponent_elo??b[k]??b.elo;const h2hValue=h.total_matches?`${h.pick_wins||0}-${h.opponent_wins||0} (${h.total_matches})`:'No previous matches';box.innerHTML=`<div class="status">${data.prediction_status||data.status}</div><div class="winner">${winner}</div><div class="prob-bar"><div class="prob-left" style="width:${(p1*100).toFixed(2)}%"></div><div class="prob-right" style="width:${(p2*100).toFixed(2)}%"></div></div><div class="prob-labels"><span>${a.player} ${(p1*100).toFixed(2)}%</span><span>${(p2*100).toFixed(2)}% ${b.player}</span></div><div class="metrics"><div class="metric">${a.player} ${profile(a)}<b>${(p1*100).toFixed(2)}%</b></div><div class="metric">${b.player} ${profile(b)}<b>${(p2*100).toFixed(2)}%</b></div><div class="metric">ThinQ confidence<b>${data.confidence==null?'N/A':(Number(data.confidence)*100).toFixed(1)+'%'}</b></div><div class="metric">ELO ${labels[k]}<b>${elo1??'N/A'} | ${elo2??'N/A'}</b></div><div class="metric">Head-to-head<b>${h2hValue}</b></div></div>${String(audit.status||'PASS').toUpperCase()==='PASS'?'':'<p class="error">Model consistency check failed. Prediction suppressed.</p>'}`;if(data.access)document.getElementById('credits').textContent=`Free predictions: ${data.access.credits_remaining} of ${data.access.credits_granted}`;if(accessToken)await checkAccess();save({p1:`${a.player} ${profile(a)}`,p2:`${b.player} ${profile(b)}`,surface:k,winner,time:new Date().toISOString()});}catch(error){box.innerHTML='<p class="error">We could not complete the comparison right now. Please try again in a moment.</p>'}finally{button.disabled=false;button.textContent='Calculate prediction'}};
</script></body></html>'''
    page = page.replace("__PLAYERS__", players).replace("__H2H__", h2h)
    page = page.replace("__NAV__", nav).replace("__LOGO__", _logo_source())
    blinq_logo = _blinq_logo_source()
    blinq_logo_html = (
        f'<img class="blinq-logo" src="{html.escape(blinq_logo, quote=True)}" alt="BlinQ">'
        if blinq_logo
        else '<div class="blinq-logo-fallback">BlinQ</div>'
    )
    page = page.replace("__BLINQ_LOGO__", blinq_logo_html)
    page = page.replace("__DISCLAIMER__", DISCLAIMER)
    page = page.replace("__SUPABASE_URL__", supabase_url).replace("__SUPABASE_PUBLISHABLE_KEY__", supabase_publishable_key)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="blinq/site/index.html")
    args = parser.parse_args()
    render(Path(args.output))


if __name__ == "__main__":
    main()
