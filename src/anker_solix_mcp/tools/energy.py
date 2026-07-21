from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClientProtocol
from ..util import sanitize


def register(mcp: FastMCP, client: AnkerSolixClientProtocol) -> None:
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

    @mcp.tool()
    async def get_energy_analysis(
        site_id: str,
        dev_type: str,
        range_type: str = "day",
        start_day: str | None = None,
        end_day: str | None = None,
        device_sn: str = "",
    ) -> dict[str, Any]:
        """Fetch a time-series energy breakdown for one site from the Anker
        cloud API - the way to get sub-daily (intraday) resolution, e.g. to
        answer "how much power was used between 22:00 and 06:00 last night?".

        Args:
            site_id: Site ID (see list_sites).
            dev_type: What to break down - one of "solar_production",
                "solar_production_pv1".."pv4", "solarbank", "home_usage",
                "grid", "pps", "ev_charger".
            range_type: "day" | "week" | "month" | "year". Use "day" for
                intraday data.
            start_day: Start of the range as "YYYY-MM-DD" (or "YYYY-MM" for
                month, "YYYY" for year). Defaults to today.
            end_day: End of the range, same format as start_day. Omit (or set
                equal to start_day) together with range_type="day" to get a
                SINGLE day's intraday series: the response's "power" list
                then has one point roughly every 20 minutes, with "time" as
                "HH:MM" - sum the points in the window you care about (e.g.
                22:00-23:59 plus 00:00-06:00) to get a night-time total.
                Leaving end_day unset with range_type="week"/"month"/"year"
                instead returns one point per day/week/month across the
                range.
            device_sn: Device serial number. Only relevant for dev_type
                "solarbank", "pps" or "ev_charger" - leave empty for
                site-level totals like "home_usage" or "grid".
        """
        result = await client.energy_analysis(
            site_id=site_id,
            dev_type=dev_type,
            range_type=range_type,
            start_day=start_day,
            end_day=end_day,
            device_sn=device_sn,
        )
        return sanitize(result)
