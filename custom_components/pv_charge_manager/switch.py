"""Switch platform for PV Charge Manager."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controls import device_info, read_always_charge, write_always_charge


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the always-charge switch. Wallbox control stays in the options."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([PVChargeManagerSwitch(coordinator, entry)])


class PVChargeManagerSwitch(CoordinatorEntity, SwitchEntity):
    """Always charge at minimum power. This does not enable wallbox writes."""

    _attr_has_entity_name = True
    _attr_translation_key = "always_charge"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_always_charge"
        self._attr_device_info = device_info(entry.entry_id, entry.title)

    @property
    def is_on(self) -> bool:
        """Return whether the car keeps the minimum power without sun."""
        return read_always_charge(self._settings())

    async def async_turn_on(self, **kwargs) -> None:
        """Store always-charge and recalculate the preview."""
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Store surplus-only charging and recalculate the preview."""
        await self._set(False)

    async def _set(self, value: bool) -> None:
        write_always_charge(self._settings(), value)
        store = self.hass.data[DOMAIN][self._entry_id]["store"]
        await store.async_save()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _settings(self) -> dict:
        return self.hass.data[DOMAIN][self._entry_id]["store"].runtime.state.settings
