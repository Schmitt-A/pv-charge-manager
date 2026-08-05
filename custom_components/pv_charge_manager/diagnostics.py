"""Diagnostics for PV Charge Manager."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = {"access_token", "password", "secret"}


async def async_get_config_entry_diagnostics(hass, entry):
    """Return diagnostics for a config entry."""
    runtime = hass.data.get("pv_charge_manager", {}).get(entry.entry_id, {})
    coordinator = runtime.get("coordinator")
    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "runtime": coordinator.data if coordinator and coordinator.data else {},
        },
        TO_REDACT,
    )
