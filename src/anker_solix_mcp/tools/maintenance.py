from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClientProtocol
from ..util import sanitize


def register(mcp: FastMCP, client: AnkerSolixClientProtocol) -> None:
    @mcp.tool()
    async def refresh_data() -> dict[str, Any]:
        """Force an immediate refresh of all cached Anker Solix data (sites,
        devices, and energy), bypassing the normal refresh-interval throttle.

        Call this if you suspect other tools are returning stale data - for
        example right after changing a setting in the Anker app.
        """
        await client.refresh(force=True)
        return {"status": "refreshed"}

    @mcp.tool()
    async def get_account_info() -> dict[str, Any]:
        """Get basic info about the authenticated Anker account (e.g.
        nickname, account/email identifiers), with any credentials or tokens
        redacted.
        """
        account = await client.account()
        return sanitize(account)
