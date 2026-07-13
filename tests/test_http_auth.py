"""Unit tests for BearerTokenMiddleware, the auth gate used for the HTTP
transports - see server.py's `_run_http`."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from anker_solix_mcp.http_auth import BearerTokenMiddleware


async def _ok(request):
    return PlainTextResponse("ok")


def _client() -> TestClient:
    app = Starlette(routes=[Route("/mcp", _ok)])
    app.add_middleware(BearerTokenMiddleware, token="secret-token")
    return TestClient(app)


def test_rejects_missing_token():
    response = _client().get("/mcp")
    assert response.status_code == 401


def test_rejects_wrong_token():
    response = _client().get("/mcp", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_rejects_non_bearer_scheme():
    response = _client().get("/mcp", headers={"Authorization": "Basic secret-token"})
    assert response.status_code == 401


def test_accepts_matching_token():
    response = _client().get("/mcp", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert response.text == "ok"
