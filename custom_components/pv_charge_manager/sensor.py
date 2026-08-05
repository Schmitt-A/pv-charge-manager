"""Sensor platform for PV Charge Manager."""

from __future__ import annotations

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
)


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
    def native_value(self) -> float | None:
        """Return the latest calculated value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Only publish recommendations when all required inputs are valid."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("available")
            and self.native_value is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose diagnostics without putting them in the sensor state."""
        if not self.coordinator.data:
            return {}
        return {
            "warnings": self.coordinator.data.get("warnings", []),
            "mapping": self.coordinator.data.get("mapping", {}),
        }
