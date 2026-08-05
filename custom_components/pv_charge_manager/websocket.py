"""WebSocket command registration for a future custom panel."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .const import DOMAIN


def async_register_websocket_commands(hass) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, websocket_get_status)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/status"})
@websocket_api.async_response
async def websocket_get_status(hass, connection, msg) -> None:
    """Return a compact integration status snapshot."""
    connection.send_result(
        msg["id"],
        {
            "entries": list(hass.data.get(DOMAIN, {}).keys()),
        },
    )
