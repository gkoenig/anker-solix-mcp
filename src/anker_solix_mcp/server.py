"""Entry point for the Anker Solix MCP server.

Builds a `FastMCP` server, registers every tool module, and runs it over
either stdio - the transport Claude Desktop, Claude Code, and most other MCP
hosts use to launch a local server as a subprocess - or streamable-http, for
running this as a standalone network service. See `Settings.mcp_transport`
and the README's "Running over HTTP" section.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP

from anker_solix_mcp.client import AnkerSolixClient, AnkerSolixClientProtocol
from anker_solix_mcp.config import Settings
from anker_solix_mcp.http_auth import BearerTokenMiddleware
from anker_solix_mcp.tools import devices, energy, maintenance, sites, smartmeter, solarbank

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("anker_solix_mcp")

_INSTRUCTIONS = (
    "Tools for reading data from an Anker Solix solar setup: Solarbanks, "
    "expansion battery packs, and Smartmeters. Start with list_sites and/or "
    "list_devices to discover site and device IDs, then use the more specific "
    "status tools (get_solarbank_status, get_smartmeter_status, "
    "get_energy_statistics, ...). Data comes from Anker's unofficial cloud "
    "API and is cached briefly to avoid excessive requests - call "
    "refresh_data if you need the very latest reading."
)


def build_server(
    client: AnkerSolixClientProtocol,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    streamable_http_path: str = "/mcp",
) -> FastMCP:
    """Assemble a FastMCP server with every tool module registered against
    the given client. Kept separate from `main()` so tests can build a server
    around a fake client without touching the environment or the network.

    `host`/`port`/`streamable_http_path` only take effect for the HTTP
    transports (`streamable-http`/`sse`); they're ignored for `stdio`.
    """
    mcp = FastMCP(
        "anker-solix",
        instructions=_INSTRUCTIONS,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
    )

    sites.register(mcp, client)
    devices.register(mcp, client)
    solarbank.register(mcp, client)
    smartmeter.register(mcp, client)
    energy.register(mcp, client)
    maintenance.register(mcp, client)

    return mcp


def _run_http(server: FastMCP, settings: Settings) -> None:
    """Run the streamable-http/sse transport behind `BearerTokenMiddleware`,
    bypassing `FastMCP.run()` so we can inject that middleware - FastMCP's
    own `auth=`/`token_verifier=` support requires standing up a full OAuth
    protected-resource setup (issuer URL, metadata endpoints, ...), which is
    overkill for gating a single-account personal server behind one token.
    """
    import uvicorn

    app = server.streamable_http_app() if settings.mcp_transport == "streamable-http" else server.sse_app()

    url = f"http://{settings.mcp_host}:{settings.mcp_port}{settings.mcp_path}"
    if settings.mcp_auth_token:
        app.add_middleware(BearerTokenMiddleware, token=settings.mcp_auth_token)
        logger.info("Starting %s server on %s (bearer token required)", settings.mcp_transport, url)
    else:
        logger.warning(
            "Starting %s server on %s WITHOUT an auth token (ANKER_MCP_AUTH_TOKEN is "
            "unset) - anyone who can reach this address can call every tool. Set "
            "ANKER_MCP_AUTH_TOKEN unless this is strictly bound to loopback or an "
            "already-trusted network.",
            settings.mcp_transport,
            url,
        )

    config = uvicorn.Config(app, host=settings.mcp_host, port=settings.mcp_port, log_level="info")
    uvicorn.Server(config).run()


def main() -> None:
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        print(f"anker-solix-mcp: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    client = AnkerSolixClient(settings)
    server = build_server(
        client,
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path=settings.mcp_path,
    )
    try:
        if settings.mcp_transport == "stdio":
            server.run(transport="stdio")
        else:
            _run_http(server, settings)
    finally:
        asyncio.run(client.close())


if __name__ == "__main__":
    main()
