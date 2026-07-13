"""Smoke tests that build the MCP server against a fake client, so they don't
require real Anker credentials or network access.
"""

from __future__ import annotations

from typing import Any

import pytest

from anker_solix_mcp.server import build_server

EXPECTED_TOOL_NAMES = {
    "list_sites",
    "get_site_overview",
    "list_devices",
    "get_device",
    "list_solarbanks",
    "get_solarbank_status",
    "get_solarbank_schedule",
    "list_smartmeters",
    "get_smartmeter_status",
    "get_energy_statistics",
    "refresh_data",
    "get_account_info",
}


class FakeAnkerSolixClient:
    """Duck-typed stand-in for AnkerSolixClient - never touches the network."""

    def __init__(self) -> None:
        self.refreshed_forced = False

    async def refresh(self, force: bool = False) -> None:
        if force:
            self.refreshed_forced = True

    async def sites(self) -> dict[str, Any]:
        return {"site-1": {"name": "Home"}}

    async def devices(self) -> dict[str, Any]:
        return {
            "SN-SOLARBANK": {"device_pn": "A17C0", "name": "Solarbank 2 E1600 Pro"},
            "SN-METER": {"type": "smartmeter", "name": "Smartmeter"},
        }

    async def account(self) -> dict[str, Any]:
        return {"nickname": "test-user", "auth_token": "should-be-redacted"}

    async def energy_snapshot(self) -> dict[str, Any]:
        return {"solar_production_today": 12.3}


@pytest.fixture
def server():
    return build_server(FakeAnkerSolixClient())


@pytest.mark.asyncio
async def test_all_expected_tools_are_registered(server):
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert EXPECTED_TOOL_NAMES <= names


@pytest.mark.asyncio
async def test_get_account_info_redacts_token(server):
    # call_tool returns (content_blocks, structured_content) for a
    # dict-returning tool; check both representations.
    content_blocks, structured = await server.call_tool("get_account_info", {})
    rendered = "".join(getattr(block, "text", "") for block in content_blocks)

    assert "should-be-redacted" not in rendered
    assert "***redacted***" in rendered
    assert structured["auth_token"] == "***redacted***"
