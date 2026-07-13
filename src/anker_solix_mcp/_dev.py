"""Entry point for `uv run mcp dev src/anker_solix_mcp/_dev.py` (the MCP
Inspector).

The `mcp dev` CLI needs a module-level `FastMCP` object (conventionally
named `mcp`) to introspect. `server.py` deliberately doesn't expose one at
import time - `build_server()` takes a client explicitly, and `main()` only
builds one after loading `Settings` - so that importing `server.py` (e.g.
from the test suite) never requires Anker credentials or touches the
network. This module exists only to satisfy the Inspector's requirement,
so it's the one place that trades that off: importing it does call
`Settings.from_env()`, exactly like running the server for real would.
"""

from __future__ import annotations

from anker_solix_mcp.client import AnkerSolixClient
from anker_solix_mcp.config import Settings
from anker_solix_mcp.server import build_server

_settings = Settings.from_env()
mcp = build_server(
    AnkerSolixClient(_settings),
    host=_settings.mcp_host,
    port=_settings.mcp_port,
    streamable_http_path=_settings.mcp_path,
)
