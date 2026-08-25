"""Authenticated BlinQ Azure Functions API."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
import azure.functions as func
import requests
from blinq.service import BlinqService

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
URL=os.getenv("SUPABASE_URL","").rstrip("/")
PUB=os.getenv("SUPABASE_PUBLISHABLE_KEY",os.getenv("SUPABASE_ANON_KEY",""))
SECRET=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
ORIGINS={x.strip().rstrip("/") for x in os.getenv("BLINQ_ALLOWED_ORIGINS","https://backstagetalks.github.io,https://agreeable-sky-011a7fe10.7.azurestaticapps.net").split(",") if x.strip()}

def reply(req,payload,status=200):
    origin=str(req.headers.get("Origin") or "").strip().rstrip("/")
    headers={"Access-Control-Allow-Methods":"GET, POST, OPTIONS","Access-Control-Allow-Headers":"Authorization, Content-Type, apikey","Cache-Control":"no-store","Vary":"Origin"}
    if origin in ORIGINS: headers["Access-Control-Allow-Origin"]=origin
    return func.HttpResponse(json.dumps(payload,ensure_ascii=False,default=str),status_code=status,mimetype="application/json",headers=headers)

def token(req):
    value=str(req.headers.get("Authorization") or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else ""

def admin_headers():
    return {"apikey":SECRET,"Authorization":f"Bearer {SECRET}","Content-Type":"application/json","Prefer":"return=representation"}

def get_user(req):
    t=token(req)
    if not t: return None,"AUTH_REQUIRED"
    if not (URL and PUB and SECRET): return None,"ACCESS_BACKEND_NOT_CONFIGURED"
    try:
        r=requests.get(f"{URL}/auth/v1/user",headers={"apikey":PUB,"Authorization":f"Bearer {t}"},timeout=12)
        return (r.json(),None) if r.status_code==200 else (None,"INVALID_SESSION")
    except Exception: return None,"AUTH_UNAVAILABLE"

def get_access(uid):
    try:
        r=requests.get(f"{URL}/rest/v1/blinq_access",headers=admin_headers(),params={"user_id":f"eq.{uid}","select":"*"},timeout=12)
        rows=r.json() if r.status_code==200 else []
        return (rows[0],None) if isinstance(rows,list) and rows else (None,"ACCESS_NOT_FOUND")
    except Exception: return None,"ACCESS_UNAVAILABLE"

def effective(row):
    status=str(row.get("access_status") or "INACTIVE").upper()
    if status in {"PRO_ACTIVE","PRO_PLUS_ACTIVE"}:
        try:
            end=datetime.fromisoformat(str(row.get("paid_until") or "").replace("Z","+00:00"))
            return status if end>datetime.now(timezone.utc) else "EXPIRED"
        except ValueError: return "EXPIRED"
    if status=="FREE_ACTIVE":
        return status if int(row.get("credits_granted") or 0)>int(row.get("credits_used") or 0) else "EXPIRED"
    return status

def public(row):
    g,u=int(row.get("credits_granted") or 0),int(row.get("credits_used") or 0)
    return {"access_status":effective(row),"plan_code":row.get("plan_code"),"credits_granted":g,"credits_used":u,"credits_remaining":max(0,g-u),"paid_until":row.get("paid_until"),"role":row.get("role") or "USER"}

def consume(uid):
    r=requests.post(f"{URL}/rest/v1/rpc/consume_blinq_credit",headers=admin_headers(),json={"p_user_id":uid},timeout=12)
    return r.status_code==200 and r.json() is True

@app.route(route="blinq/health",methods=["GET","OPTIONS"])
def health(req):
    if req.method=="OPTIONS": return reply(req,{},204)
    return reply(req,{"status":"OK","service":"BlinQ API","auth_configured":bool(URL and PUB and SECRET)})

@app.route(route="blinq/access/status",methods=["GET","OPTIONS"])
def access_status(req):
    if req.method=="OPTIONS": return reply(req,{},204)
    user,error=get_user(req)
    if error: return reply(req,{"status":error},401)
    row,error=get_access(str(user.get("id") or ""))
    if error: return reply(req,{"status":error},403)
    return reply(req,{"status":"OK","email":user.get("email"),**public(row)})

@app.route(route="blinq/predict",methods=["POST","OPTIONS"])
def predict(req):
    if req.method=="OPTIONS": return reply(req,{},204)
    user,error=get_user(req)
    if error: return reply(req,{"status":error},401)
    uid=str(user.get("id") or "")
    row,error=get_access(uid)
    if error: return reply(req,{"status":error},403)
    status=effective(row)
    if status not in {"FREE_ACTIVE","PRO_ACTIVE","PRO_PLUS_ACTIVE","ADMIN"}: return reply(req,{"status":"ACCESS_INACTIVE",**public(row)},403)
    try: body=req.get_json()
    except ValueError: return reply(req,{"status":"INVALID_INPUT","reason":"Request body must be JSON."},400)
    p1,p2=str(body.get("player1") or "").strip(),str(body.get("player2") or "").strip()
    surface=str(body.get("surface") or "Overall").strip()
    if not p1 or not p2 or p1.casefold()==p2.casefold(): return reply(req,{"status":"INVALID_INPUT","reason":"Select two different players."},400)
    try:
        result=BlinqService().predict(p1,p2,surface)
        successful=str(result.get("prediction_status") or result.get("status") or "").upper()=="PREDICTION"
        if successful and status=="FREE_ACTIVE":
            if not consume(uid): return reply(req,{"status":"CREDIT_UPDATE_FAILED"},409)
            row,_=get_access(uid)
        result["access"]=public(row or {})
        return reply(req,result)
    except Exception as exc:
        return reply(req,{"status":"NO_PREDICTION","prediction_status":"NO_PREDICTION","winner":None,"reason":"BlinQ backend failed safely.","error_type":type(exc).__name__},500)
