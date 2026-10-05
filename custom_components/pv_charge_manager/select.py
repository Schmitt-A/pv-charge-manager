"""Select platform for PV Charge Manager."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controls import SELECTS, RejectedControl, device_info, read_select, write_select

_LOGGER = logging.getLogger(__name__)
_KEYS = ("mode", "strategy")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up mode and strategy selects."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(PVChargeManagerSelect(coordinator, entry, key) for key in _KEYS)


class PVChargeManagerSelect(CoordinatorEntity, SelectEntity):
    """One stored choice. Changing it refreshes the preview, not the wallbox setpoint."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_options = list(SELECTS[key])
        self._attr_device_info = device_info(entry.entry_id, entry.title)

    @property
    def current_option(self) -> str:
        """Return the stored choice."""
        return read_select(self._settings(), self._key)

    async def async_select_option(self, option: str) -> None:
        """Store the choice and recalculate the preview."""
        try:
            write_select(self._settings(), self._key, option)
        except RejectedControl:
            _LOGGER.warning("rejected %s option %s", self._key, option)
            return
        await self._commit()

    def _settings(self) -> dict:
        return self.hass.data[DOMAIN][self._entry_id]["store"].runtime.state.settings

    async def _commit(self) -> None:
        store = self.hass.data[DOMAIN][self._entry_id]["store"]
        await store.async_save()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
