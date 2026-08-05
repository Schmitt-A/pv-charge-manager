"""Diagnostics for PV Charge Manager."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = {"access_token", "password", "secret"}


async def async_get_config_entry_diagnostics(hass, entry):
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "runtime": hass.data.get("pv_charge_manager", {}).get(entry.entry_id, {}),
        },
        TO_REDACT,
    )
