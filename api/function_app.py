"""Azure Functions HTTP API for the canonical BlinQ prediction service."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import azure.functions as func

from blinq.service import BlinqService

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

_DEFAULT_ALLOWED_ORIGINS = {
    "https://backstagetalks.github.io",
    "https://agreeable-sky-011a7fe10.7.azurestaticapps.net",
}


def _allowed_origins() -> set[str]:
    configured = os.getenv("BLINQ_ALLOWED_ORIGINS", "")
    values = {item.strip().rstrip("/") for item in configured.split(",") if item.strip()}
    return values or set(_DEFAULT_ALLOWED_ORIGINS)


def _cors_origin(req: func.HttpRequest) -> str:
    origin = str(req.headers.get("Origin") or "").strip().rstrip("/")
    if origin in _allowed_origins():
        return origin
    return ""


def _response(
    req: func.HttpRequest,
    payload: Dict[str, Any],
    status: int = 200,
) -> func.HttpResponse:
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-BlinQ-Authorization",
        "Vary": "Origin",
        "Cache-Control": "no-store",
    }
    origin = _cors_origin(req)
    if origin:
        headers["Access-Control-Allow-Origin"] = origin

    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
        headers=headers,
    )




SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")).strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
DEFAULT_FREE_PREDICTIONS = int(os.getenv("BLINQ_DEFAULT_FREE_PREDICTIONS", "10"))

def _bearer(req: func.HttpRequest) -> str:
    # Azure Static Web Apps reserves and may replace the standard Authorization
    # header before forwarding a request to its managed Functions API. Carry the
    # Supabase user JWT in an application-specific header instead.
    value = str(req.headers.get("X-BlinQ-Authorization") or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else ""

def _supabase_auth_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)

def _supabase_admin_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

def _auth_user(req: func.HttpRequest) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    token = _bearer(req)
    if not token:
        return None, "AUTH_REQUIRED"
    if not _supabase_auth_ready():
        return None, "AUTH_BACKEND_NOT_CONFIGURED"
    try:
        import requests
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
            timeout=12,
        )
        if response.status_code != 200:
            return None, f"INVALID_SESSION_{response.status_code}"
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("id"):
            return None, "INVALID_SESSION_PAYLOAD"
        return payload, None
    except requests.Timeout:
        return None, "AUTH_TIMEOUT"
    except requests.RequestException:
        return None, "AUTH_UNAVAILABLE"
    except ValueError:
        return None, "AUTH_INVALID_RESPONSE"

def _admin_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _access_row(user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    import requests
    if not _supabase_admin_ready():
        return None, "ACCESS_BACKEND_NOT_CONFIGURED"
    uid = str(user.get("id") or "")
    email = str(user.get("email") or "").strip().lower()
    if not uid or not email:
        return None, "INVALID_IDENTITY"
    endpoint = f"{SUPABASE_URL}/rest/v1/blinq_access"
    try:
        current = requests.get(
            endpoint, headers=_admin_headers(), params={"user_id": f"eq.{uid}", "select": "*"}, timeout=12
        )
        rows = current.json() if current.status_code == 200 else []
        if isinstance(rows, list) and rows:
            return rows[0], None
        created = requests.post(
            endpoint, headers={**_admin_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json={
                "user_id": uid, "email": email, "access_status": "FREE_ACTIVE",
                "plan_code": "FREE_10", "credits_granted": DEFAULT_FREE_PREDICTIONS,
                "bonus_credits": 0, "credits_used": 0, "trial_used": True,
            }, timeout=12
        )
        data = created.json() if created.status_code in (200, 201) else []
        return (data[0] if isinstance(data, list) and data else None), (None if data else "ACCESS_CREATE_FAILED")
    except Exception:
        return None, "ACCESS_UNAVAILABLE"

def _int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _paid_active(row: Dict[str, Any]) -> bool:
    from datetime import datetime, timezone
    paid_until = row.get("paid_until")
    if not paid_until:
        return False
    try:
        end = datetime.fromisoformat(str(paid_until).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return end > datetime.now(timezone.utc)
    except ValueError:
        return False


def _effective_status(row: Dict[str, Any]) -> str:
    status = str(row.get("access_status") or "INACTIVE").upper()
    if status in {"ADMIN", "GOAT_PLUS_ACTIVE"}:
        return status
    if status in {"PRO_ACTIVE", "PRO_PLUS_ACTIVE", "GOAT_ACTIVE"}:
        if _paid_active(row):
            return status
        # Paid access expiry does not delete previously unused FREE or bonus credits.
        remaining = _int_value(row.get("credits_granted")) + _int_value(row.get("bonus_credits")) - _int_value(row.get("credits_used"))
        return "FREE_ACTIVE" if remaining > 0 else "EXPIRED"
    if status == "FREE_ACTIVE":
        remaining = _int_value(row.get("credits_granted")) + _int_value(row.get("bonus_credits")) - _int_value(row.get("credits_used"))
        return "FREE_ACTIVE" if remaining > 0 else "EXPIRED"
    return status


def _public_access(row: Dict[str, Any]) -> Dict[str, Any]:
    granted = _int_value(row.get("credits_granted"))
    bonus = _int_value(row.get("bonus_credits"))
    used = _int_value(row.get("credits_used"))
    effective = _effective_status(row)
    unlimited = effective in {"PRO_ACTIVE", "PRO_PLUS_ACTIVE", "GOAT_ACTIVE", "GOAT_PLUS_ACTIVE", "ADMIN"}
    return {
        "access_status": effective,
        "plan_code": row.get("plan_code"),
        "unlimited": unlimited,
        "credits_granted": granted,
        "bonus_credits": bonus,
        "credits_used": used,
        "credits_remaining": None if unlimited else max(0, granted + bonus - used),
        "paid_until": row.get("paid_until"),
        "payment_verification_pending": str(row.get("access_status") or "").upper() == "PAYMENT_PENDING",
    }


def _consume_credit(user_id: str, access_row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Consume exactly one FREE credit through the canonical atomic RPC.

    Expired paid accounts may resolve to FREE_ACTIVE when saved FREE credits remain.
    Normalize that stored state before calling the RPC, because the database function
    intentionally consumes only rows whose stored status is FREE_ACTIVE.
    """
    import requests

    stored_status = str(access_row.get("access_status") or "").upper()
    if stored_status != "FREE_ACTIVE":
        try:
            normalized = requests.patch(
                f"{SUPABASE_URL}/rest/v1/blinq_access",
                headers=_admin_headers(),
                params={"user_id": f"eq.{user_id}"},
                json={"access_status": "FREE_ACTIVE", "plan_code": "FREE_10", "paid_until": None},
                timeout=12,
            )
            if normalized.status_code not in (200, 204):
                return False, f"CREDIT_STATUS_NORMALIZE_FAILED_{normalized.status_code}"
        except requests.RequestException:
            return False, "CREDIT_STATUS_NORMALIZE_UNAVAILABLE"

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/consume_blinq_credit",
            headers=_admin_headers(),
            json={"p_user_id": user_id},
            timeout=12,
        )
    except requests.RequestException:
        return False, "CREDIT_RPC_UNAVAILABLE"

    if response.status_code != 200:
        return False, f"CREDIT_RPC_FAILED_{response.status_code}"
    try:
        value = response.json()
    except ValueError:
        return False, "CREDIT_RPC_INVALID_RESPONSE"
    return (True, None) if value is True else (False, "NO_FREE_CREDIT_AVAILABLE")

@app.route(route="blinq/health", methods=["GET", "OPTIONS"])
def blinq_health(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    return _response(
        req,
        {
            "status": "OK",
            "service": "BlinQ API",
            "prediction_endpoint": "/api/blinq/predict",
            "auth_configured": _supabase_auth_ready(),
            "access_configured": _supabase_admin_ready(),
            "rapidapi_configured": bool(os.getenv("RAPIDAPI_KEY", "").strip()),
        },
        200,
    )



@app.route(route="blinq/access/status", methods=["GET", "OPTIONS"])
def blinq_access_status(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    user, error = _auth_user(req)
    if error or not user:
        return _response(req, {"status": error or "AUTH_REQUIRED", "reason": error or "Session validation failed."}, 401)
    row, access_error = _access_row(user)
    if access_error or not row:
        return _response(req, {"status": access_error or "ACCESS_UNAVAILABLE"}, 503)
    return _response(req, {"status": "OK", "email": user.get("email"), **_public_access(row)}, 200)



def _require_admin(req: func.HttpRequest) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    user, error = _auth_user(req)
    if error or not user:
        return None, None, error or "AUTH_REQUIRED"
    row, access_error = _access_row(user)
    if access_error or not row:
        return user, None, access_error or "ACCESS_UNAVAILABLE"
    if _effective_status(row) != "ADMIN":
        return user, row, "ADMIN_REQUIRED"
    return user, row, None


def _admin_account_by_email(email: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    import requests
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return None, "INVALID_EMAIL"
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/blinq_access",
            headers=_admin_headers(),
            params={"email": f"eq.{normalized}", "select": "*", "limit": "1"},
            timeout=12,
        )
        if response.status_code != 200:
            return None, "ACCOUNT_LOOKUP_FAILED"
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None, "ACCOUNT_NOT_FOUND"
        return rows[0], None
    except Exception:
        return None, "ACCOUNT_LOOKUP_UNAVAILABLE"


def _admin_public_account(row: Dict[str, Any]) -> Dict[str, Any]:
    access = _public_access(row)
    return {
        "user_id": row.get("user_id"),
        "email": row.get("email"),
        "role": row.get("role"),
        "access_status_stored": row.get("access_status"),
        **access,
    }


@app.route(route="blinq/admin/account", methods=["GET", "POST", "OPTIONS"])
def blinq_admin_account(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    _, _, admin_error = _require_admin(req)
    if admin_error:
        status = 403 if admin_error == "ADMIN_REQUIRED" else 401 if admin_error.startswith(("AUTH_", "INVALID_SESSION")) else 503
        return _response(req, {"status": admin_error}, status)

    if req.method == "GET":
        account, lookup_error = _admin_account_by_email(req.params.get("email") or "")
        if lookup_error or not account:
            return _response(req, {"status": lookup_error or "ACCOUNT_NOT_FOUND"}, 404 if lookup_error == "ACCOUNT_NOT_FOUND" else 400)
        return _response(req, {"status": "OK", "account": _admin_public_account(account)}, 200)

    try:
        body = req.get_json()
    except ValueError:
        return _response(req, {"status": "INVALID_INPUT", "reason": "Request body must be JSON."}, 400)
    if not isinstance(body, dict):
        return _response(req, {"status": "INVALID_INPUT"}, 400)

    account, lookup_error = _admin_account_by_email(body.get("email") or "")
    if lookup_error or not account:
        return _response(req, {"status": lookup_error or "ACCOUNT_NOT_FOUND"}, 404 if lookup_error == "ACCOUNT_NOT_FOUND" else 400)

    action = str(body.get("access_status") or "KEEP").strip().upper()
    allowed = {"KEEP", "FREE_ACTIVE", "PRO_ACTIVE", "PRO_PLUS_ACTIVE", "GOAT_ACTIVE", "GOAT_PLUS_ACTIVE"}
    if action not in allowed:
        return _response(req, {"status": "INVALID_ACCESS_STATUS"}, 400)
    try:
        add_comparisons = int(body.get("add_comparisons") or 0)
        duration_days = int(body.get("duration_days") or 0)
    except (TypeError, ValueError):
        return _response(req, {"status": "INVALID_NUMERIC_VALUE"}, 400)
    if add_comparisons < 0 or add_comparisons > 100000:
        return _response(req, {"status": "INVALID_COMPARISON_COUNT"}, 400)
    if action == "PRO_ACTIVE":
        duration_days = 30
    elif action == "PRO_PLUS_ACTIVE":
        duration_days = 90
    elif action == "GOAT_ACTIVE":
        duration_days = 365
    elif action == "GOAT_PLUS_ACTIVE":
        duration_days = 0

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    patch: Dict[str, Any] = {}
    if action != "KEEP":
        patch["access_status"] = action
        if action == "FREE_ACTIVE":
            patch.update({"plan_code": "FREE_10", "paid_until": None})
        else:
            patch.update({
                "plan_code": "PRO_30D" if action == "PRO_ACTIVE" else "PRO_PLUS_90D" if action == "PRO_PLUS_ACTIVE" else "GOAT_365D" if action == "GOAT_ACTIVE" else "GOAT_PLUS_INFINITY",
                "paid_at": now.isoformat(),
                "paid_until": None if action == "GOAT_PLUS_ACTIVE" else (now + timedelta(days=duration_days)).isoformat(),
            })
    if add_comparisons:
        patch["credits_granted"] = _int_value(account.get("credits_granted")) + add_comparisons
    payment_reference = str(body.get("payment_reference") or "").strip()
    if payment_reference:
        patch["payment_reference"] = payment_reference[:200]
    if not patch:
        return _response(req, {"status": "NO_CHANGES"}, 400)

    import requests
    try:
        updated = requests.patch(
            f"{SUPABASE_URL}/rest/v1/blinq_access",
            headers=_admin_headers(),
            params={"user_id": f"eq.{account.get('user_id')}"},
            json=patch,
            timeout=12,
        )
        if updated.status_code not in (200, 204):
            return _response(req, {"status": "ACCOUNT_UPDATE_FAILED"}, 500)
        rows = updated.json() if updated.content else []
        result = rows[0] if isinstance(rows, list) and rows else {**account, **patch}
        return _response(req, {"status": "OK", "account": _admin_public_account(result)}, 200)
    except Exception:
        return _response(req, {"status": "ACCOUNT_UPDATE_UNAVAILABLE"}, 503)


@app.route(route="blinq/access/request", methods=["POST", "OPTIONS"])
def blinq_access_request(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)
    user, error = _auth_user(req)
    if error or not user:
        return _response(req, {"status": error or "AUTH_REQUIRED"}, 401)
    row, access_error = _access_row(user)
    if access_error or not row:
        return _response(req, {"status": access_error or "ACCESS_UNAVAILABLE"}, 503)
    import requests
    from datetime import datetime, timezone
    updated = requests.patch(
        f"{SUPABASE_URL}/rest/v1/blinq_access", headers=_admin_headers(),
        params={"user_id": f"eq.{user.get('id')}"},
        json={"access_status": "PAYMENT_PENDING", "access_requested_at": datetime.now(timezone.utc).isoformat()}, timeout=12
    )
    if updated.status_code not in (200, 204):
        return _response(req, {"status": "REQUEST_FAILED"}, 500)
    return _response(req, {
        "status": "PAYMENT_PENDING",
        "message": "Your BlinQ Pro access will be activated after the payment email is matched with your account.",
    }, 200)


def _is_billable_prediction(result: Dict[str, Any]) -> bool:
    status = str(result.get("prediction_status") or result.get("status") or "").upper()
    winner = result.get("winner")
    p1, p2 = result.get("player1_probability"), result.get("player2_probability")
    audit = result.get("symmetry_audit") if isinstance(result.get("symmetry_audit"), dict) else {}
    try:
        valid_probabilities = p1 is not None and p2 is not None and abs(float(p1) + float(p2) - 1.0) <= 0.0001
    except (TypeError, ValueError):
        valid_probabilities = False
    return bool(status == "PREDICTION" and winner and valid_probabilities and audit.get("status") == "PASS")

@app.route(route="blinq/predict", methods=["POST", "OPTIONS"])
def blinq_predict(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)

    user, auth_error = _auth_user(req)
    if auth_error or not user:
        return _response(req, {"status": auth_error or "AUTH_REQUIRED", "reason": auth_error or "Sign in is required."}, 401)

    access_row, access_error = _access_row(user)
    if access_error or not access_row:
        return _response(req, {"status": access_error or "ACCESS_UNAVAILABLE", "reason": "Access status is temporarily unavailable."}, 503)

    effective = _effective_status(access_row)
    if effective not in {"FREE_ACTIVE", "PRO_ACTIVE", "PRO_PLUS_ACTIVE", "GOAT_ACTIVE", "GOAT_PLUS_ACTIVE", "ADMIN"}:
        if effective == "EXPIRED":
            reason = "Your BlinQ access has expired."
        elif effective == "PAYMENT_PENDING":
            reason = "Payment verification pending."
        else:
            reason = "Your BlinQ access is currently disabled."
        return _response(req, {"status": effective, "reason": reason, **_public_access(access_row)}, 403)

    try:
        body = req.get_json()
    except ValueError:
        return _response(
            req,
            {"status": "INVALID_INPUT", "reason": "Request body must be JSON."},
            400,
        )

    if not isinstance(body, dict):
        return _response(
            req,
            {"status": "INVALID_INPUT", "reason": "JSON object is required."},
            400,
        )

    player1 = str(body.get("player1") or "").strip()
    player2 = str(body.get("player2") or "").strip()
    surface = str(body.get("surface") or "Overall").strip()

    if not player1 or not player2:
        return _response(
            req,
            {"status": "INVALID_INPUT", "reason": "Both players are required."},
            400,
        )

    if player1.casefold() == player2.casefold():
        return _response(
            req,
            {"status": "INVALID_INPUT", "reason": "Select two different players."},
            400,
        )

    try:
        result = BlinqService().predict(player1, player2, surface)
        if _is_billable_prediction(result):
            if effective == "FREE_ACTIVE":
                consumed, credit_error = _consume_credit(str(user.get("id") or ""), access_row)
                if not consumed:
                    refreshed, _ = _access_row(user)
                    current_access = _public_access(refreshed or access_row)
                    status_code = 403 if credit_error == "NO_FREE_CREDIT_AVAILABLE" else 503
                    return _response(
                        req,
                        {
                            "status": "CREDIT_UPDATE_FAILED",
                            "reason": credit_error or "Credit could not be updated.",
                            **current_access,
                        },
                        status_code,
                    )
            refreshed, _ = _access_row(user)
            result["access"] = _public_access(refreshed or access_row)
        else:
            if str(result.get("prediction_status") or result.get("status") or "").upper() == "PREDICTION":
                result = {
                    **result,
                    "status": "NO_PREDICTION",
                    "prediction_status": "NO_PREDICTION",
                    "outcome_type": "VALIDATION_FAILED",
                    "public_status": "RESULT_UNAVAILABLE",
                    "public_label": "RESULT UNAVAILABLE",
                    "winner": None,
                    "winner_side": None,
                    "winner_probability": None,
                    "player1_probability": None,
                    "player2_probability": None,
                    "confidence": None,
                    "confidence_label": "NOT_CALCULATED",
                    "reason": "The comparison could not be verified.",
                }
            result["access"] = _public_access(access_row)
        return _response(req, result, 200)
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
