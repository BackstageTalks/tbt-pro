"""Azure Functions API for authenticated BlinQ predictions."""
from __future__ import annotations

import json
import os
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

_DEFAULT_ALLOWED_ORIGINS = {
    "https://backstagetalks.github.io",
    "https://agreeable-sky-011a7fe10.7.azurestaticapps.net",
}


def _allowed_origins() -> set[str]:
    configured = os.getenv("BLINQ_ALLOWED_ORIGINS", "")
    values = {item.strip().rstrip("/") for item in configured.split(",") if item.strip()}
    return values or set(_DEFAULT_ALLOWED_ORIGINS)


def _response(req: func.HttpRequest, payload: Dict[str, Any], status: int = 200) -> func.HttpResponse:
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Vary": "Origin",
        "Cache-Control": "no-store",
    }
    origin = str(req.headers.get("Origin") or "").strip().rstrip("/")
    if origin in _allowed_origins():
        headers["Access-Control-Allow-Origin"] = origin
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
        headers=headers,
    )


def _supabase_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY and SUPABASE_SERVICE_ROLE_KEY)


def _bearer(req: func.HttpRequest) -> str:
    value = str(req.headers.get("Authorization") or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else ""


def _auth_user(req: func.HttpRequest) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    token = _bearer(req)
    if not token:
        return None, "AUTH_REQUIRED"
    if not _supabase_ready():
        return None, "ACCESS_BACKEND_NOT_CONFIGURED"
    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token}",
            },
            timeout=12,
        )
        if response.status_code != 200:
            return None, "INVALID_SESSION"
        payload = response.json()
        return (payload if isinstance(payload, dict) else None), None
    except Exception:
        return None, "AUTH_UNAVAILABLE"


def _admin_headers(prefer: str = "return=representation") -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _access_row(user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    user_id = str(user.get("id") or "")
    email = str(user.get("email") or "").strip().lower()
    if not user_id or not email:
        return None, "INVALID_IDENTITY"

    endpoint = f"{SUPABASE_URL}/rest/v1/blinq_access"
    try:
        response = requests.get(
            endpoint,
            headers=_admin_headers(),
            params={"user_id": f"eq.{user_id}", "select": "*"},
            timeout=12,
        )
        rows = response.json() if response.status_code == 200 else []
        if isinstance(rows, list) and rows:
            return rows[0], None

        response = requests.post(
            endpoint,
            headers=_admin_headers("resolution=merge-duplicates,return=representation"),
            json={
                "user_id": user_id,
                "email": email,
                "role": "USER",
                "plan_code": "FREE",
                "access_status": "ACTIVE",
                "credits_granted": DEFAULT_FREE_PREDICTIONS,
                "credits_used": 0,
            },
            timeout=12,
        )
        rows = response.json() if response.status_code in (200, 201) else []
        if isinstance(rows, list) and rows:
            return rows[0], None
        return None, "ACCESS_CREATE_FAILED"
    except Exception:
        return None, "ACCESS_UNAVAILABLE"


def _is_expired(row: Dict[str, Any]) -> bool:
    expires_at = row.get("expires_at")
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        return parsed <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _access_decision(row: Dict[str, Any]) -> Tuple[bool, str, bool]:
    role = str(row.get("role") or "USER").upper()
    plan = str(row.get("plan_code") or "FREE").upper()
    status = str(row.get("access_status") or "BLOCKED").upper()

    if role == "ADMIN":
        return True, "ADMIN", False
    if status == "BLOCKED":
        return False, "BLOCKED", False
    if status != "ACTIVE" or _is_expired(row):
        return False, "EXPIRED", False
    if plan in {"PRO", "PRO_PLUS"}:
        return True, plan, False

    granted = int(row.get("credits_granted") or 0)
    used = int(row.get("credits_used") or 0)
    remaining = granted - used
    return (remaining > 0), (plan if remaining > 0 else "CREDITS_EXHAUSTED"), True


def _public_access(row: Dict[str, Any]) -> Dict[str, Any]:
    granted = int(row.get("credits_granted") or 0)
    used = int(row.get("credits_used") or 0)
    allowed, status, metered = _access_decision(row)
    return {
        "allowed": allowed,
        "access_status": status,
        "role": row.get("role"),
        "plan_code": row.get("plan_code"),
        "credits_granted": granted,
        "credits_used": used,
        "credits_remaining": max(0, granted - used),
        "expires_at": row.get("expires_at"),
        "metered": metered,
    }


def _consume_credit(user_id: str) -> bool:
    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/consume_blinq_credit",
            headers=_admin_headers(),
            json={"p_user_id": user_id},
            timeout=12,
        )
        return response.status_code == 200 and response.json() is True
    except Exception:
        return False


@app.route(route="blinq/health", methods=["GET", "OPTIONS"])
def blinq_health(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    return _response(
        req,
        {
            "status": "OK",
            "service": "BlinQ API",
            "auth_configured": _supabase_ready(),
            "prediction_endpoint": "/api/blinq/predict",
        },
    )


@app.route(route="blinq/access/status", methods=["GET", "OPTIONS"])
def blinq_access_status(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    user, error = _auth_user(req)
    if error or not user:
        return _response(req, {"status": error or "AUTH_REQUIRED"}, 401)
    row, error = _access_row(user)
    if error or not row:
        return _response(req, {"status": error or "ACCESS_UNAVAILABLE"}, 503)
    return _response(req, {"status": "OK", "email": user.get("email"), **_public_access(row)})


@app.route(route="blinq/predict", methods=["POST", "OPTIONS"])
def blinq_predict(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)

    user, error = _auth_user(req)
    if error or not user:
        return _response(req, {"status": error or "AUTH_REQUIRED", "reason": "Sign in is required."}, 401)

    access_row, error = _access_row(user)
    if error or not access_row:
        return _response(req, {"status": error or "ACCESS_UNAVAILABLE"}, 503)

    allowed, access_status, metered = _access_decision(access_row)
    if not allowed:
        return _response(
            req,
            {
                "status": access_status,
                "reason": "No active prediction access.",
                "access": _public_access(access_row),
            },
            403,
        )

    try:
        body = req.get_json()
    except ValueError:
        return _response(req, {"status": "INVALID_INPUT", "reason": "Request body must be JSON."}, 400)
    if not isinstance(body, dict):
        return _response(req, {"status": "INVALID_INPUT", "reason": "JSON object is required."}, 400)

    player1 = str(body.get("player1") or "").strip()
    player2 = str(body.get("player2") or "").strip()
    surface = str(body.get("surface") or "Overall").strip()
    if not player1 or not player2 or player1.casefold() == player2.casefold():
        return _response(req, {"status": "INVALID_INPUT", "reason": "Select two different players."}, 400)

    try:
        result = BlinqService().predict(player1, player2, surface)
        success = str(result.get("prediction_status") or result.get("status") or "").upper() == "PREDICTION"
        if success and metered and not _consume_credit(str(user.get("id") or "")):
            return _response(req, {"status": "CREDIT_UPDATE_FAILED"}, 503)
        refreshed, _ = _access_row(user)
        result["access"] = _public_access(refreshed or access_row)
        return _response(req, result)
    except Exception as exc:
        return _response(
            req,
            {
                "status": "NO_PREDICTION",
                "prediction_status": "NO_PREDICTION",
                "winner": None,
                "reason": "Prediction service is temporarily unavailable.",
                "error_type": type(exc).__name__,
            },
            500,
        )
