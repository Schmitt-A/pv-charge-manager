"""Storage model helpers for PV Charge Manager."""

from __future__ import annotations

from dataclasses import dataclass, field


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
