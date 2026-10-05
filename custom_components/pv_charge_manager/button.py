"""Button platform for PV Charge Manager."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controls import device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the recalculate button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([PVChargeManagerButton(coordinator, entry)])


class PVChargeManagerButton(CoordinatorEntity, ButtonEntity):
    """Run the same recalculate service as the integration."""

    _attr_has_entity_name = True
    _attr_translation_key = "recalculate"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_recalculate"
        self._attr_device_info = device_info(entry.entry_id, entry.title)

    async def async_press(self) -> None:
        """Ask the recalculate service to refresh this entry."""
        await self.hass.services.async_call(
            DOMAIN,
            "recalculate",
            {"entry_id": self._entry_id},
            blocking=True,
        )
