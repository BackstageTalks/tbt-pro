"""Azure Functions API for authenticated BlinQ predictions."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import azure.functions as func
import requests
from blinq.service import BlinqService

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
DEFAULT_FREE_PREDICTIONS = 10
_ALLOWED = {"https://backstagetalks.github.io", "https://agreeable-sky-011a7fe10.7.azurestaticapps.net"}

def _origins() -> set[str]:
    raw=os.getenv("BLINQ_ALLOWED_ORIGINS","")
    return {x.strip().rstrip("/") for x in raw.split(",") if x.strip()} or set(_ALLOWED)

def _response(req: func.HttpRequest, payload: Dict[str,Any], status: int=200) -> func.HttpResponse:
    headers={"Access-Control-Allow-Methods":"GET, POST, OPTIONS","Access-Control-Allow-Headers":"Authorization, Content-Type","Vary":"Origin","Cache-Control":"no-store"}
    origin=str(req.headers.get("Origin") or "").strip().rstrip("/")
    if origin in _origins(): headers["Access-Control-Allow-Origin"]=origin
    return func.HttpResponse(json.dumps(payload,ensure_ascii=False,default=str),status_code=status,mimetype="application/json",headers=headers)

def _ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY and SUPABASE_SERVICE_ROLE_KEY)

def _bearer(req: func.HttpRequest) -> str:
    value=str(req.headers.get("Authorization") or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else ""

def _user(req: func.HttpRequest) -> Tuple[Optional[Dict[str,Any]],Optional[str]]:
    token=_bearer(req)
    if not token: return None,"AUTH_REQUIRED"
    if not _ready(): return None,"ACCESS_BACKEND_NOT_CONFIGURED"
    try:
        r=requests.get(f"{SUPABASE_URL}/auth/v1/user",headers={"apikey":SUPABASE_PUBLISHABLE_KEY,"Authorization":f"Bearer {token}"},timeout=12)
        if r.status_code != 200: return None,"INVALID_SESSION"
        data=r.json()
        return (data if isinstance(data,dict) else None),None
    except Exception: return None,"AUTH_UNAVAILABLE"

def _admin_headers(prefer: str="return=representation") -> Dict[str,str]:
    return {"apikey":SUPABASE_SERVICE_ROLE_KEY,"Authorization":f"Bearer {SUPABASE_SERVICE_ROLE_KEY}","Content-Type":"application/json","Prefer":prefer}

def _access(user: Dict[str,Any]) -> Tuple[Optional[Dict[str,Any]],Optional[str]]:
    uid,email=str(user.get("id") or ""),str(user.get("email") or "").strip().lower()
    if not uid or not email: return None,"INVALID_IDENTITY"
    endpoint=f"{SUPABASE_URL}/rest/v1/blinq_access"
    try:
        r=requests.get(endpoint,headers=_admin_headers(),params={"user_id":f"eq.{uid}","select":"*"},timeout=12)
        rows=r.json() if r.status_code==200 else []
        if isinstance(rows,list) and rows: return rows[0],None
        r=requests.post(endpoint,headers=_admin_headers("resolution=merge-duplicates,return=representation"),json={"user_id":uid,"email":email,"role":"USER","plan_code":"FREE","access_status":"ACTIVE","credits_granted":DEFAULT_FREE_PREDICTIONS,"credits_used":0},timeout=12)
        rows=r.json() if r.status_code in (200,201) else []
        return (rows[0] if isinstance(rows,list) and rows else None),(None if rows else "ACCESS_CREATE_FAILED")
    except Exception: return None,"ACCESS_UNAVAILABLE"

def _expired(row: Dict[str,Any]) -> bool:
    value=row.get("expires_at")
    if not value: return False
    try: return datetime.fromisoformat(str(value).replace("Z","+00:00")) <= datetime.now(timezone.utc)
    except ValueError: return True

def _decision(row: Dict[str,Any]) -> Tuple[bool,str,bool]:
    role=str(row.get("role") or "USER").upper(); plan=str(row.get("plan_code") or "FREE").upper(); status=str(row.get("access_status") or "BLOCKED").upper()
    if role=="ADMIN": return True,"ADMIN",False
    if status=="BLOCKED": return False,"BLOCKED",False
    if status!="ACTIVE" or _expired(row): return False,"EXPIRED",False
    if plan in {"PRO","PRO_PLUS"}: return True,plan,False
    remaining=int(row.get("credits_granted") or 0)-int(row.get("credits_used") or 0)
    return (remaining>0),(plan if remaining>0 else "CREDITS_EXHAUSTED"),True

def _public(row: Dict[str,Any]) -> Dict[str,Any]:
    granted=int(row.get("credits_granted") or 0); used=int(row.get("credits_used") or 0); allowed,reason,metered=_decision(row)
    return {"allowed":allowed,"access_status":reason,"role":row.get("role"),"plan_code":row.get("plan_code"),"credits_granted":granted,"credits_used":used,"credits_remaining":max(0,granted-used),"expires_at":row.get("expires_at"),"metered":metered}

def _consume(uid: str) -> bool:
    try:
        r=requests.post(f"{SUPABASE_URL}/rest/v1/rpc/consume_blinq_credit",headers=_admin_headers(),json={"p_user_id":uid},timeout=12)
        return r.status_code==200 and r.json() is True
    except Exception: return False

@app.route(route="blinq/health",methods=["GET","OPTIONS"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    if req.method=="OPTIONS": return _response(req,{},204)
    return _response(req,{"status":"OK","service":"BlinQ API","auth_configured":_ready(),"prediction_endpoint":"/api/blinq/predict"})

@app.route(route="blinq/access/status",methods=["GET","OPTIONS"])
def access_status(req: func.HttpRequest) -> func.HttpResponse:
    if req.method=="OPTIONS": return _response(req,{},204)
    user,error=_user(req)
    if error or not user: return _response(req,{"status":error or "AUTH_REQUIRED"},401)
    row,error=_access(user)
    if error or not row: return _response(req,{"status":error or "ACCESS_UNAVAILABLE"},503)
    return _response(req,{"status":"OK","email":user.get("email"),**_public(row)})

@app.route(route="blinq/predict",methods=["POST","OPTIONS"])
def predict(req: func.HttpRequest) -> func.HttpResponse:
    if req.method=="OPTIONS": return _response(req,{},204)
    user,error=_user(req)
    if error or not user: return _response(req,{"status":error or "AUTH_REQUIRED","reason":"Sign in is required."},401)
    row,error=_access(user)
    if error or not row: return _response(req,{"status":error or "ACCESS_UNAVAILABLE"},503)
    allowed,reason,metered=_decision(row)
    if not allowed: return _response(req,{"status":reason,"reason":"No active prediction access.","access":_public(row)},403)
    try: body=req.get_json()
    except ValueError: return _response(req,{"status":"INVALID_INPUT","reason":"Request body must be JSON."},400)
    if not isinstance(body,dict): return _response(req,{"status":"INVALID_INPUT","reason":"JSON object is required."},400)
    p1,p2=str(body.get("player1") or "").strip(),str(body.get("player2") or "").strip(); surface=str(body.get("surface") or "Overall").strip()
    if not p1 or not p2 or p1.casefold()==p2.casefold(): return _response(req,{"status":"INVALID_INPUT","reason":"Select two different players."},400)
    try:
        result=BlinqService().predict(p1,p2,surface)
        success=str(result.get("prediction_status") or result.get("status") or "").upper()=="PREDICTION"
        if success and metered and not _consume(str(user.get("id"))): return _response(req,{"status":"CREDIT_UPDATE_FAILED"},503)
        refreshed,_=_access(user); result["access"]=_public(refreshed or row)
        return _response(req,result,200)
    except Exception as exc:
        return _response(req,{"status":"NO_PREDICTION","prediction_status":"NO_PREDICTION","winner":None,"reason":"BlinQ backend failed safely.","error_type":type(exc).__name__},500)
