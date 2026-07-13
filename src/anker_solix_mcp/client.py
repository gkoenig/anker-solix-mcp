"""Thin async wrapper around `anker_solix_api.api.AnkerSolixApi`.

Responsible for:
  * lazily creating the aiohttp session + API client (so importing this
    module never makes a network call),
  * throttling refreshes so repeated tool calls in a short conversation don't
    hammer Anker's cloud API,
  * exposing the small set of read operations the MCP tools need.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .config import Settings

logger = logging.getLogger("anker_solix_mcp")


class AnkerSolixClient:
    """Lazily-authenticated, refresh-throttled wrapper around AnkerSolixApi."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = None
        self._api = None
        self._lock = asyncio.Lock()
        self._last_refresh: float = 0.0

    async def _ensure_api(self):
        if self._api is not None:
            return self._api

        # Imported lazily: this pulls in aiohttp/cryptography/paho-mqtt, and we
        # don't want that cost (or a missing-dependency error) to happen at
        # module import time - only when a tool is actually invoked.
        from aiohttp import ClientSession
        from anker_solix_api import api as anker_api

        self._session = ClientSession()
        self._api = anker_api.AnkerSolixApi(
            self._settings.email,
            self._settings.password,
            self._settings.country,
            self._session,
            logger,
        )
        return self._api

    async def close(self) -> None:
        """Release the underlying HTTP session. Call on server shutdown."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            self._api = None

    async def refresh(self, force: bool = False) -> None:
        """Refresh the sites/devices caches (sites, site details, device
        details, device energy).

        Refreshes are throttled to `settings.refresh_interval_seconds` unless
        `force=True`, so a burst of tool calls in one conversation turn only
        costs one round trip to Anker's cloud API.
        """
        api = await self._ensure_api()

        if not force and (time.monotonic() - self._last_refresh) < self._settings.refresh_interval_seconds:
            return

        async with self._lock:
            # Re-check inside the lock in case a concurrent call already refreshed.
            if not force and (time.monotonic() - self._last_refresh) < self._settings.refresh_interval_seconds:
                return
            await api.update_sites()
            await api.update_site_details()
            await api.update_device_details()
            await api.update_device_energy()
            self._last_refresh = time.monotonic()

    async def sites(self) -> dict[str, Any]:
        """Refresh-and-return the cached site ("system") dict, keyed by site ID."""
        await self.refresh()
        api = await self._ensure_api()
        return api.sites

    async def devices(self) -> dict[str, Any]:
        """Refresh-and-return the cached device dict, keyed by device serial number."""
        await self.refresh()
        api = await self._ensure_api()
        return api.devices

    async def account(self) -> dict[str, Any]:
        """Refresh-and-return the cached account info dict."""
        await self.refresh()
        api = await self._ensure_api()
        return api.account

    async def energy_snapshot(self) -> dict[str, Any]:
        """Force a fresh device-energy fetch (bypassing the refresh throttle)
        and return the raw response from the Anker cloud API.

        Energy totals (production, charge/discharge, grid import/export) are
        the values most likely to be asked about live, so this always makes a
        real request rather than serving a stale cache.
        """
        api = await self._ensure_api()
        result = await api.update_device_energy()
        self._last_refresh = time.monotonic()
        return result
