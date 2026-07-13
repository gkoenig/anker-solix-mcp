from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AnkerSolixClientProtocol
from ..util import sanitize


def register(mcp: FastMCP, client: AnkerSolixClientProtocol) -> None:
    @mcp.tool()
    async def list_devices() -> dict[str, Any]:
        """List every device (Solarbank, expansion battery pack, Smartmeter,
        etc.) linked to the Anker account, keyed by device serial number.

        Each entry contains whatever fields the Anker cloud API reports for
        that specific device model and firmware version - typically at least a
        name and a type/model field, plus live status fields where available.
        Use this to find device serial numbers (device_sn) for the more
        specific tools like get_solarbank_status and get_smartmeter_status.
        """
        devices = await client.devices()
        return sanitize(devices)

    @mcp.tool()
    async def get_device(device_sn: str) -> dict[str, Any]:
        """Get the full cached detail record for one device by serial number,
        with no type-specific filtering applied.

        Args:
            device_sn: The device serial number, as returned by list_devices.
        """
        devices = await client.devices()
        device = devices.get(device_sn)
        if device is None:
            return {
                "error": f"No device found with serial number {device_sn!r}. "
                "Call list_devices to see available devices."
            }
        return sanitize(device)
