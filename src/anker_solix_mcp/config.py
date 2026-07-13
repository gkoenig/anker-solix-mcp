"""Runtime configuration for the Anker Solix MCP server, loaded from the
environment (and optionally a `.env` file via python-dotenv)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


_VALID_TRANSPORTS = {"stdio", "streamable-http", "sse"}


@dataclass(frozen=True)
class Settings:
    email: str
    password: str
    country: str
    refresh_interval_seconds: float
    default_site_id: str | None
    mcp_transport: str
    mcp_host: str
    mcp_port: int
    mcp_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        email = os.environ.get("ANKER_EMAIL")
        password = os.environ.get("ANKER_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "ANKER_EMAIL and ANKER_PASSWORD must be set (as environment "
                "variables, or in a .env file in the working directory). "
                "Copy .env.example to .env and fill in your Anker account "
                "credentials to get started."
            )
        mcp_transport = os.environ.get("ANKER_MCP_TRANSPORT", "stdio")
        if mcp_transport not in _VALID_TRANSPORTS:
            raise RuntimeError(
                f"ANKER_MCP_TRANSPORT={mcp_transport!r} is not one of "
                f"{sorted(_VALID_TRANSPORTS)}."
            )
        return cls(
            email=email,
            password=password,
            country=os.environ.get("ANKER_COUNTRY", "DE"),
            refresh_interval_seconds=float(os.environ.get("ANKER_REFRESH_SECONDS", "60")),
            default_site_id=os.environ.get("ANKER_SITE_ID") or None,
            mcp_transport=mcp_transport,
            mcp_host=os.environ.get("ANKER_MCP_HOST", "127.0.0.1"),
            mcp_port=int(os.environ.get("ANKER_MCP_PORT", "8000")),
            mcp_path=os.environ.get("ANKER_MCP_PATH", "/mcp"),
        )
