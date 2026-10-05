"""Sensor platform for PV Charge Manager."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PVChargeManagerCoordinator

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="surplus_power_w",
        translation_key="surplus_power",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="recommended_current_a",
        translation_key="recommended_current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="recommended_charge_power_w",
        translation_key="recommended_charge_power",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="opportunity_cost_eur_per_hour",
        translation_key="opportunity_cost",
        native_unit_of_measurement="EUR/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wallbox_action",
        translation_key="wallbox_action",
    ),
    SensorEntityDescription(
        key="chargeable_kwh_today",
        translation_key="chargeable_kwh_today",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="chargeable_kwh_tomorrow",
        translation_key="chargeable_kwh_tomorrow",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery_full_at",
        translation_key="battery_full_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="battery_full_at_early",
        translation_key="battery_full_at_early",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="battery_full_at_late",
        translation_key="battery_full_at_late",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="vehicle_full_at",
        translation_key="vehicle_full_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="plan_status",
        translation_key="plan_status",
    ),
    SensorEntityDescription(
        key="minimum_power_today",
        translation_key="minimum_power_today",
    ),
    SensorEntityDescription(
        key="battery_recommendation",
        translation_key="battery_recommendation",
    ),
)

PREVIEW_KEYS = {
    "chargeable_kwh_today",
    "chargeable_kwh_tomorrow",
    "battery_full_at",
    "battery_full_at_early",
    "battery_full_at_late",
    "vehicle_full_at",
    "plan_status",
    "minimum_power_today",
    "battery_recommendation",
}
TIMESTAMP_KEYS = {
    "battery_full_at",
    "battery_full_at_early",
    "battery_full_at_late",
    "vehicle_full_at",
}


async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up PV Charge Manager sensors."""
    coordinator: PVChargeManagerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        PVChargeManagerSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PVChargeManagerSensor(CoordinatorEntity[PVChargeManagerCoordinator], SensorEntity):
    """Expose one calculated PV Charge Manager value."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, entry, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "PV Charge Manager",
        }

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the latest calculated value."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key in TIMESTAMP_KEYS and isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return value

    @property
    def available(self) -> bool:
        """Keep surplus sensors unavailable without inputs. Preview sensors follow their own key."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        if self.entity_description.key == "wallbox_action":
            return True
        if self.entity_description.key in PREVIEW_KEYS:
            return self.native_value is not None
        return bool(self.coordinator.data.get("available") and self.native_value is not None)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose diagnostics without putting them in the sensor state."""
        if not self.coordinator.data:
            return {}
        attributes: dict[str, object] = {
            "warnings": self.coordinator.data.get("warnings", []),
            "mapping": self.coordinator.data.get("mapping", {}),
        }
        if self.entity_description.key in PREVIEW_KEYS:
            meta = self.coordinator.data.get("preview_meta")
            if isinstance(meta, dict):
                attributes.update(meta)
        return attributes
