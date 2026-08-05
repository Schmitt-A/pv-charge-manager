"""Sensor platform for PV Charge Manager."""

from __future__ import annotations


async def async_setup_entry(hass, entry, async_add_entities) -> bool:
    """Set up PV Charge Manager sensors."""
    async_add_entities([])
    return True
