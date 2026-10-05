"""PV Charge Manager Home Assistant integration."""

from __future__ import annotations

import logging

from .const import DOMAIN, PLATFORMS
from .storage import apply_import

_LOGGER = logging.getLogger(__name__)
_SERVICES = ("export_backup", "import_backup", "recalculate", "start_boost")


async def async_setup_entry(hass, entry) -> bool:
    """Set up PV Charge Manager from a config entry."""
    from .coordinator import PVChargeManagerCoordinator
    from .storage import HomeAssistantStore

    store = HomeAssistantStore(hass, entry.entry_id)
    await store.async_load()

    coordinator = PVChargeManagerCoordinator(hass, _LOGGER, entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "coordinator": coordinator,
        "store": store,
    }
    await _async_ensure_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a PV Charge Manager config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            for service in _SERVICES:
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def async_reload_entry(hass, entry) -> None:
    """Reload after the options flow writes a new draft."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_ensure_services(hass) -> None:
    if hass.services.has_service(DOMAIN, "export_backup"):
        return
    from homeassistant.core import SupportsResponse

    async def export_backup(call):
        store = _store_for_call(hass, call)
        if store is None:
            return {"ok": False, "error": "no_entry"}
        return store.runtime.export_backup()

    async def import_backup(call):
        store = _store_for_call(hass, call)
        if store is None:
            return {"ok": False, "error": "no_entry"}
        result = apply_import(store.runtime, call.data.get("json", ""))
        if result.get("ok"):
            await store.async_save()
            coordinator = hass.data[DOMAIN][store.runtime.entry_id]["coordinator"]
            await coordinator.async_request_refresh()
        return result

    async def recalculate(call):
        item = _item_for_call(hass, call)
        if item is None:
            _LOGGER.warning("recalculate ignored because no config entry is loaded")
            return
        await item["coordinator"].async_request_refresh()

    async def start_boost(call):
        _LOGGER.warning(
            "start_boost has no effect yet; duration_minutes=%s",
            call.data.get("duration_minutes"),
        )

    hass.services.async_register(
        DOMAIN,
        "export_backup",
        export_backup,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "import_backup",
        import_backup,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(DOMAIN, "recalculate", recalculate)
    hass.services.async_register(DOMAIN, "start_boost", start_boost)


def _item_for_call(hass, call):
    entries = hass.data.get(DOMAIN, {})
    entry_id = call.data.get("entry_id")
    if entry_id:
        return entries.get(entry_id)
    if len(entries) == 1:
        return next(iter(entries.values()))
    return None


def _store_for_call(hass, call):
    item = _item_for_call(hass, call)
    if item is None:
        return None
    return item.get("store")
