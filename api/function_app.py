"""Azure Functions HTTP API for the canonical BlinQ prediction service."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import azure.functions as func

from blinq.service import BlinqService

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _origin() -> str:
    return os.getenv("BLINQ_ALLOWED_ORIGIN", "https://backstagetalks.github.io").strip()


def _response(payload: Dict[str, Any], status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": _origin(),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Vary": "Origin",
            "Cache-Control": "no-store",
        },
    )


@app.route(route="blinq/predict", methods=["POST", "OPTIONS"])
def blinq_predict(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _response({}, 204)
    try:
        body = req.get_json()
    except ValueError:
        return _response({"status": "INVALID_INPUT", "reason": "Request body must be JSON."}, 400)
    if not isinstance(body, dict):
        return _response({"status": "INVALID_INPUT", "reason": "JSON object is required."}, 400)

    player1 = str(body.get("player1") or "").strip()
    player2 = str(body.get("player2") or "").strip()
    surface = str(body.get("surface") or "Overall").strip()
    if not player1 or not player2:
        return _response({"status": "INVALID_INPUT", "reason": "Both players are required."}, 400)

    try:
        result = BlinqService().predict(player1, player2, surface)
        return _response(result, 200)
    except Exception as exc:
        return _response(
            {
                "status": "NO_PREDICTION",
                "prediction_status": "NO_PREDICTION",
                "winner": None,
                "reason": "BlinQ backend failed safely.",
                "error_type": type(exc).__name__,
            },
            500,
        )
