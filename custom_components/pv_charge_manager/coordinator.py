"""Coordinator placeholder for PV Charge Manager runtime state."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


class PVChargeManagerCoordinator(DataUpdateCoordinator):
    """Coordinate sensor reads and calculations."""

    def __init__(self, hass, logger, entry) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

    async def _async_update_data(self):
        """Fetch Home Assistant states and calculate derived values."""
        return {}
