"""Azure Functions HTTP API for the canonical BlinQ prediction service."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

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
        "Access-Control-Allow-Headers": "Content-Type",
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
        },
        200,
    )


@app.route(route="blinq/predict", methods=["POST", "OPTIONS"])
def blinq_predict(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response(req, {}, 204)

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
        return _response(req, result, 200)
    except Exception as exc:
        return _response(
            req,
            {
                "status": "NO_PREDICTION",
                "prediction_status": "NO_PREDICTION",
                "winner": None,
                "reason": "BlinQ backend failed safely.",
                "error_type": type(exc).__name__,
            },
            500,
        )
