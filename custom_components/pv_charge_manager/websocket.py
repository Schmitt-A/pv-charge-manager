"""WebSocket commands for the panel. The snapshot is built without a second plan."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api

from .const import DOMAIN
from .controls import RejectedControl
from .panel import (
    apply_panel_control,
    build_panel_snapshot,
    collect_probe,
    entity_map_for_probe,
)

_WS_KEY = f"{DOMAIN}_ws"


def async_register_websocket_commands(hass) -> None:
    """Register the panel commands once."""
    if hass.data.get(_WS_KEY):
        return
    hass.data[_WS_KEY] = True
    websocket_api.async_register_command(hass, websocket_get_snapshot)
    websocket_api.async_register_command(hass, websocket_set_control)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/snapshot",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_get_snapshot(hass, connection, msg) -> None:
    """Return the panel snapshot for one config entry."""
    item = _item(hass, msg.get("entry_id"))
    if item is None:
        connection.send_error(msg["id"], "not_found", "Keine Konfiguration geladen.")
        return
    connection.send_result(msg["id"], _snapshot(item))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_control",
        vol.Required("key"): str,
        vol.Required("value"): vol.Any(str, int, float, bool),
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_set_control(hass, connection, msg) -> None:
    """Store one overview control and return the refreshed snapshot."""
    item = _item(hass, msg.get("entry_id"))
    if item is None:
        connection.send_error(msg["id"], "not_found", "Keine Konfiguration geladen.")
        return
    store = item["store"]
    try:
        apply_panel_control(
            store.runtime.state.settings,
            store.runtime.state.plans,
            msg["key"],
            msg["value"],
        )
    except RejectedControl:
        connection.send_error(msg["id"], "invalid_format", "Wert nicht erlaubt.")
        return
    await store.async_save()
    await item["coordinator"].async_request_refresh()
    connection.send_result(msg["id"], _snapshot(item))


def _item(hass, entry_id: str | None):
    entries = {
        key: value
        for key, value in hass.data.get(DOMAIN, {}).items()
        if isinstance(value, dict) and "coordinator" in value
    }
    if entry_id:
        return entries.get(entry_id)
    if not entries:
        return None
    return next(iter(entries.values()))


def _snapshot(item: dict[str, Any]) -> dict[str, Any]:
    coordinator = item["coordinator"]
    store = item["store"].runtime
    data = coordinator.data or {}
    options = getattr(coordinator.entry, "options", {}) or {}
    entity_map = entity_map_for_probe(store.state.entity_map, options)
    return build_panel_snapshot(
        data,
        store.state.settings,
        plans=store.state.plans,
        step=store.state.step,
        probe=collect_probe(entity_map, store.state.settings, _states(item, entity_map)),
        entry_id=store.entry_id,
        backup=store.export_backup(),
    )


def _states(item: dict[str, Any], entity_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    hass = item["coordinator"].hass
    found: dict[str, dict[str, Any]] = {}
    for entity_id in _ids(entity_map):
        state = hass.states.get(entity_id)
        if state is None:
            continue
        found[entity_id] = {"state": state.state, "age_s": _age_s(state)}
    return found


def _ids(entity_map: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for value in entity_map.values():
        if isinstance(value, str) and value:
            ids.append(value)
        elif isinstance(value, list):
            ids.extend(str(item) for item in value if item)
    return ids


def _age_s(state: Any) -> float | None:
    last = getattr(state, "last_updated", None)
    if last is None:
        return None
    try:
        moment = datetime.now(last.tzinfo) if getattr(last, "tzinfo", None) else datetime.now(UTC)
        return (moment - last).total_seconds()
    except (TypeError, ValueError):
        return None
