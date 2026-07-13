from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClientProtocol
from ..util import filter_devices, sanitize

_SMARTMETER_KEYWORDS = ("smartmeter", "smart meter", "meter")


def register(mcp: FastMCP, client: AnkerSolixClientProtocol) -> None:
    @mcp.tool()
    async def list_smartmeters() -> dict[str, Any]:
        """List devices that look like Anker Smartmeters, identified
        heuristically from model/type/name fields.

        If nothing matches the heuristic, every device is returned instead so
        you can still find the right one by eye.
        """
        devices = await client.devices()
        return sanitize(filter_devices(devices, _SMARTMETER_KEYWORDS))

    @mcp.tool()
    async def get_smartmeter_status(device_sn: str) -> dict[str, Any]:
        """Get current status for one Smartmeter: grid import/export power and
        any other fields the Anker cloud API reports for this device.

        Args:
            device_sn: The Smartmeter's device serial number (see
                list_smartmeters or list_devices).
        """
        devices = await client.devices()
        device = devices.get(device_sn)
        if device is None:
            return {
                "error": f"No device found with serial number {device_sn!r}. "
                "Call list_smartmeters to see available Smartmeters."
            }
        return sanitize(device)
