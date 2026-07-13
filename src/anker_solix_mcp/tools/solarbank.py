from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClientProtocol
from ..util import filter_devices, sanitize

# Heuristic keywords used to spot Solarbank / expansion-battery entries among
# the account's devices. Anker's model names for this line include e.g.
# "A17C0" (Solarbank 2 E1600 Pro) and "A17X8" (1600 expansion pack).
_SOLARBANK_KEYWORDS = ("solarbank", "solar bank", "a17")


def register(mcp: FastMCP, client: AnkerSolixClientProtocol) -> None:
    @mcp.tool()
    async def list_solarbanks() -> dict[str, Any]:
        """List devices that look like Solarbanks or their expansion battery
        packs, identified heuristically from model/type/name fields.

        If nothing matches the heuristic, every device is returned instead so
        you can still find the right one by eye - use get_device on any
        serial number for the unfiltered detail record.
        """
        devices = await client.devices()
        return sanitize(filter_devices(devices, _SOLARBANK_KEYWORDS))

    @mcp.tool()
    async def get_solarbank_status(device_sn: str) -> dict[str, Any]:
        """Get current status for one Solarbank (or expansion battery pack):
        battery state of charge, solar input power, output power,
        charge/discharge power, temperature, and any other fields the Anker
        cloud API reports for this device.

        Args:
            device_sn: The Solarbank's device serial number (see list_solarbanks
                or list_devices).
        """
        devices = await client.devices()
        device = devices.get(device_sn)
        if device is None:
            return {
                "error": f"No device found with serial number {device_sn!r}. "
                "Call list_solarbanks to see available Solarbanks."
            }
        return sanitize(device)

    @mcp.tool()
    async def get_solarbank_schedule(device_sn: str) -> dict[str, Any]:
        """Get the charge/discharge schedule and output-power plan configured
        for a Solarbank, if the Anker cloud API reports one under this
        device's cached data.

        Args:
            device_sn: The Solarbank's device serial number (see list_solarbanks
                or list_devices).
        """
        devices = await client.devices()
        device = devices.get(device_sn)
        if device is None:
            return {
                "error": f"No device found with serial number {device_sn!r}. "
                "Call list_solarbanks to see available Solarbanks."
            }
        schedule = device.get("schedule")
        if schedule is None:
            return {
                "note": (
                    "This device's cached data has no top-level 'schedule' "
                    "field on this firmware/account. Returning the full device "
                    "record instead so you can look for schedule-related "
                    "fields under a different key."
                ),
                "device": sanitize(device),
            }
        return sanitize(schedule)
