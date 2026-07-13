"""Small, dependency-free helpers for shaping Anker Solix API responses before
they are handed to an MCP client.

The upstream `anker-solix-api` library is a reverse-engineered client for an
unofficial, undocumented Anker cloud API. Its cached dictionaries vary in
shape by device model and firmware version, so these helpers deliberately
avoid hardcoding an exact schema: they redact anything that looks like a
credential, and filter heuristically rather than asserting one true shape.
"""

from __future__ import annotations

from typing import Any

_REDACT_SUBSTRINGS = (
    "password",
    "passwd",
    "token",
    "secret",
    "cookie",
    "auth_",
    "authcode",
    "ticket",
    "session_id",
    "refresh_token",
    "access_token",
    "private_key",
)

_REDACTED = "***redacted***"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _REDACT_SUBSTRINGS)


def sanitize(value: Any) -> Any:
    """Recursively redact likely-sensitive fields (tokens, passwords, cookies)
    from API response data before it is returned by an MCP tool.

    This is a defense-in-depth measure: it should not be relied on as the only
    protection against leaking credentials, but it prevents an accidental
    passthrough of an auth token buried in a nested response from ever
    reaching an LLM's context window.
    """
    if isinstance(value, dict):
        return {
            key: (_REDACTED if _is_sensitive_key(str(key)) else sanitize(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


_DEVICE_TYPE_FIELDS = ("type", "device_type", "category", "device_pn", "device_model", "name")


def filter_devices(devices: dict[str, Any], keywords: tuple[str, ...]) -> dict[str, Any]:
    """Filter a device dict (serial number -> device detail dict) down to
    entries whose type-ish fields contain any of `keywords` (case-insensitive).

    Checks several commonly-populated fields rather than one fixed schema,
    since the field actually carrying the device type varies by model. If
    nothing matches, the full, unfiltered device set is returned so callers
    can still inspect it rather than silently getting an empty result.
    """
    keywords_lower = tuple(k.lower() for k in keywords)

    def matches(dev: dict[str, Any]) -> bool:
        for field in _DEVICE_TYPE_FIELDS:
            val = dev.get(field)
            if val and any(k in str(val).lower() for k in keywords_lower):
                return True
        return False

    filtered = {
        sn: dev for sn, dev in devices.items() if isinstance(dev, dict) and matches(dev)
    }
    return filtered or dict(devices)
