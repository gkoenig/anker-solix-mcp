from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClient
from ..util import sanitize


def register(mcp: FastMCP, client: AnkerSolixClient) -> None:
    @mcp.tool()
    async def get_energy_statistics() -> dict[str, Any]:
        """Fetch fresh energy statistics from the Anker cloud API: solar
        production, battery charge/discharge, grid import/export, and home
        usage totals, for every site/device the account can see.

        Unlike the other tools, this always makes a live request rather than
        serving the throttled cache, since energy totals are the numbers most
        often asked about ("how much did we produce/use today").
        """
        result = await client.energy_snapshot()
        return sanitize(result)
