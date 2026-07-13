from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClient
from ..util import sanitize


def register(mcp: FastMCP, client: AnkerSolixClient) -> None:
    @mcp.tool()
    async def list_sites() -> dict[str, Any]:
        """List every Anker power system ("site") linked to this account, keyed
        by site ID.

        A site groups together the devices installed at one location - e.g. a
        Solarbank, its expansion battery pack, and a Smartmeter. Start here (or
        with list_devices) to discover the IDs needed by the other tools.
        """
        sites = await client.sites()
        return sanitize(sites)

    @mcp.tool()
    async def get_site_overview(site_id: str) -> dict[str, Any]:
        """Get the cached detail record for one site, including whatever
        current power-flow summary the Anker cloud API reports for it (e.g.
        solar input, battery charge/discharge, home load, grid import/export).

        Args:
            site_id: The site ID, as returned by list_sites.
        """
        sites = await client.sites()
        site = sites.get(site_id)
        if site is None:
            return {
                "error": f"No site found with id {site_id!r}. Call list_sites to see available sites."
            }
        return sanitize(site)
