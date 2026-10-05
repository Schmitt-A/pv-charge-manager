"""Number platform for PV Charge Manager."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controls import NUMBER_SPECS, RejectedControl, device_info, read_number, write_number

_LOGGER = logging.getLogger(__name__)
_UNITS = {
    "solar_share": "%",
    "priority_soc": "%",
    "buffer_soc": "%",
    "reserve_soc": "%",
    "price_limit_eur": "EUR/kWh",
    "target_soc": "%",
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the plan numbers."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(PVChargeManagerNumber(coordinator, entry, key) for key in NUMBER_SPECS)


class PVChargeManagerNumber(CoordinatorEntity, NumberEntity):
    """One stored number. Changing it refreshes the preview, not the wallbox setpoint."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator)
        low, high, step = NUMBER_SPECS[key]
        self._entry_id = entry.entry_id
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = _UNITS[key]
        self._attr_mode = NumberMode.BOX if key == "price_limit_eur" else NumberMode.SLIDER
        self._attr_device_info = device_info(entry.entry_id, entry.title)

    @property
    def native_value(self) -> float:
        """Return the stored number."""
        return read_number(self._settings(), self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Store the number and recalculate the preview."""
        try:
            write_number(self._settings(), self._key, value)
        except RejectedControl:
            _LOGGER.warning("rejected %s value %s", self._key, value)
            return
        store = self.hass.data[DOMAIN][self._entry_id]["store"]
        await store.async_save()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _settings(self) -> dict:
        return self.hass.data[DOMAIN][self._entry_id]["store"].runtime.state.settings
