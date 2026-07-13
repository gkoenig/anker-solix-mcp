"""MCP tool registrations, grouped by domain.

Each module exposes a single `register(mcp, client)` function that attaches
its tools to a `FastMCP` server instance, closing over the shared
`AnkerSolixClient`. This keeps `server.py` as a plain assembly point.
"""
