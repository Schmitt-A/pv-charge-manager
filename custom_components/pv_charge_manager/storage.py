"""Storage model helpers for PV Charge Manager."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .backup import (
    ImportResult,
    UnsupportedSchema,
    default_settings,
    export_document,
    import_document,
)


def storage_key(entry_id: str) -> str:
    """Return the Home Assistant storage key for one config entry."""
    return f"pv_charge_manager.{entry_id}"


@dataclass(slots=True)
class EntityMapping:
    """Configured Home Assistant entity mapping."""

    grid_import_sensor: str | None = None
    grid_export_sensor: str | None = None
    home_consumption_sensor: str | None = None
    battery_soc_sensor: str | None = None
    battery_charge_power_sensor: str | None = None
    pv_power_sensors: list[str] = field(default_factory=list)
    forecast_sensors: list[str] = field(default_factory=list)

    @classmethod
    def from_options(cls, options: dict) -> EntityMapping:
        """Build an entity mapping from config-entry options."""
        return cls(
            grid_import_sensor=options.get("grid_import_sensor"),
            grid_export_sensor=options.get("grid_export_sensor"),
            home_consumption_sensor=options.get("home_consumption_sensor"),
            battery_soc_sensor=options.get("battery_soc_sensor"),
            battery_charge_power_sensor=options.get("battery_charge_power_sensor"),
            pv_power_sensors=list(options.get("pv_power_sensors", [])),
            forecast_sensors=list(options.get("forecast_sensors", [])),
        )


@dataclass(slots=True)
class VehicleProfile:
    """Vehicle charging profile."""

    name: str
    capacity_kwh: float
    maximum_current_a: float = 16.0
    charging_efficiency: float = 0.9
    target_soc_percent: float = 80.0


@dataclass(slots=True)
class PersistedState:
    """State the coordinator cannot reread from live entities."""

    settings: dict[str, Any] = field(default_factory=default_settings)
    plans: list[dict[str, Any]] = field(default_factory=list)
    entity_map: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)
    step: str = "site"

    @classmethod
    def from_import(cls, result: ImportResult) -> PersistedState:
        """Build state from a migrated backup."""
        return cls(
            settings=dict(result.settings),
            plans=list(result.plans),
            entity_map=dict(result.entity_map),
            learning=dict(result.learning),
            step=result.step,
        )


class RuntimeStore:
    """In-memory store. Tests use it directly; Home Assistant wraps it."""

    def __init__(self, entry_id: str, raw: dict[str, Any] | None = None) -> None:
        self.entry_id = entry_id
        self.key = storage_key(entry_id)
        if raw:
            self.state = PersistedState.from_import(import_document(raw))
        else:
            self.state = PersistedState()

    def export_backup(self, now: datetime | None = None) -> dict[str, Any]:
        """Return the versioned document for this entry."""
        state = self.state
        return export_document(
            state.settings,
            state.step,
            now,
            plans=state.plans,
            entity_map=state.entity_map,
            learning=state.learning,
        )

    def import_backup(self, payload: dict[str, Any] | str) -> ImportResult:
        """Replace the stored draft. A string payload must be JSON."""
        if isinstance(payload, str):
            payload = json.loads(payload)
        result = import_document(payload)
        self.state = PersistedState.from_import(result)
        return result


def apply_import(store: RuntimeStore, payload: dict[str, Any] | str) -> dict[str, Any]:
    """Import a backup and return a service response. The store is unchanged on error."""
    try:
        result = store.import_backup(payload)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json"}
    except UnsupportedSchema as err:
        return {"ok": False, "error": str(err)}
    except (TypeError, ValueError) as err:
        return {"ok": False, "error": str(err)}
    return {"ok": True, "step": result.step, "warnings": result.warnings}


class HomeAssistantStore:
    """Persist RuntimeStore through the Home Assistant Store helper."""

    def __init__(self, hass: Any, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self.runtime = RuntimeStore(entry_id)
        self._store = Store(hass, 1, self.runtime.key)

    async def async_load(self) -> None:
        """Load a previously saved document. Missing data keeps the defaults."""
        raw = await self._store.async_load()
        if not isinstance(raw, dict):
            return
        try:
            self.runtime = RuntimeStore(self.runtime.entry_id, raw)
        except (UnsupportedSchema, TypeError, ValueError):
            return

    async def async_save(self) -> None:
        """Write the current document."""
        await self._store.async_save(self.runtime.export_backup())
