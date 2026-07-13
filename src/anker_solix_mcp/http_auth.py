"""Minimal bearer-token gate for the HTTP transports (streamable-http/sse).

`FastMCP`'s built-in `auth=`/`token_verifier=` machinery is designed for a
full OAuth protected-resource setup (it requires an `issuer_url` and serves
OAuth metadata endpoints) - overkill for gating a single-account personal
tool behind one static token. `BearerTokenMiddleware` instead does the one
thing that setup needs: reject any HTTP request that doesn't carry the
configured token, before it reaches the MCP session.
"""

from __future__ import annotations

import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerTokenMiddleware:
    """ASGI middleware requiring `Authorization: Bearer <token>` to match a
    fixed, server-configured token on every HTTP request.

    Plain ASGI (not `starlette.middleware.base.BaseHTTPMiddleware`) so it
    doesn't buffer or interfere with the streamable-http/SSE response
    streaming the MCP session relies on.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        header_value = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, provided = header_value.partition(" ")
        is_valid = scheme.lower() == "bearer" and hmac.compare_digest(provided, self._token)

        if not is_valid:
            response = JSONResponse(
                {"error": "unauthorized", "message": "Missing or invalid bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)
