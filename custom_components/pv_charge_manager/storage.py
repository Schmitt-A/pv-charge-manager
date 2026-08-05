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


@dataclass(slots=True)
class VehicleProfile:
    """Vehicle charging profile."""

    name: str
    capacity_kwh: float
    maximum_current_a: float = 16.0
    charging_efficiency: float = 0.9
    target_soc_percent: float = 80.0
