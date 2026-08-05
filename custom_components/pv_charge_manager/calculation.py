"""Pure calculation helpers for PV Charge Manager."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, inf


@dataclass(frozen=True, slots=True)
class PowerSnapshot:
    """Power values for one calculation cycle."""

    pv_power_w: float
    home_consumption_w: float
    battery_charge_power_w: float = 0.0
    reserve_power_w: float = 300.0


@dataclass(frozen=True, slots=True)
class ChargeLimits:
    """Electrical limits for an EV charging session."""

    minimum_current_a: float = 6.0
    maximum_current_a: float = 16.0
    phases: int = 3
    voltage_v: float = 230.0
    current_step_a: float = 1.0

    @property
    def minimum_power_w(self) -> float:
        """Return minimum valid charging power."""
        return self.minimum_current_a * self.phases * self.voltage_v

    @property
    def maximum_power_w(self) -> float:
        """Return maximum valid charging power."""
        return self.maximum_current_a * self.phases * self.voltage_v


@dataclass(frozen=True, slots=True)
class CurrentRecommendation:
    """Recommended EVSE current and resulting power."""

    available_power_w: float
    current_a: float
    charge_power_w: float


def available_surplus_power_w(snapshot: PowerSnapshot) -> float:
    """Calculate currently available PV surplus power in watt."""
    _ensure_non_negative(snapshot.pv_power_w, "pv_power_w")
    _ensure_non_negative(snapshot.home_consumption_w, "home_consumption_w")
    _ensure_non_negative(snapshot.battery_charge_power_w, "battery_charge_power_w")
    _ensure_non_negative(snapshot.reserve_power_w, "reserve_power_w")

    surplus_w = (
        snapshot.pv_power_w
        - snapshot.home_consumption_w
        - snapshot.battery_charge_power_w
        - snapshot.reserve_power_w
    )
    return max(0.0, surplus_w)


def current_for_power_a(power_w: float, limits: ChargeLimits) -> float:
    """Convert available power to a valid EVSE current."""
    _ensure_non_negative(power_w, "power_w")
    _validate_limits(limits)

    if power_w < limits.minimum_power_w:
        return 0.0

    raw_current_a = power_w / (limits.voltage_v * limits.phases)
    capped_current_a = min(raw_current_a, limits.maximum_current_a)
    stepped_current_a = floor(capped_current_a / limits.current_step_a) * limits.current_step_a
    return round(max(limits.minimum_current_a, stepped_current_a), 3)


def power_for_current_w(current_a: float, limits: ChargeLimits) -> float:
    """Convert EVSE current to charging power."""
    _ensure_non_negative(current_a, "current_a")
    _validate_limits(limits)

    if current_a == 0:
        return 0.0

    if current_a < limits.minimum_current_a:
        raise ValueError("current_a must be 0 or at least the configured minimum current")

    capped_current_a = min(current_a, limits.maximum_current_a)
    return round(capped_current_a * limits.voltage_v * limits.phases, 3)


def recommend_current(snapshot: PowerSnapshot, limits: ChargeLimits) -> CurrentRecommendation:
    """Calculate a charging recommendation from the current power snapshot."""
    available_power_w = available_surplus_power_w(snapshot)
    current_a = current_for_power_a(available_power_w, limits)
    charge_power_w = power_for_current_w(current_a, limits)
    return CurrentRecommendation(
        available_power_w=available_power_w,
        current_a=current_a,
        charge_power_w=charge_power_w,
    )


def required_vehicle_energy_kwh(
    capacity_kwh: float,
    current_soc_percent: float,
    target_soc_percent: float,
    charging_efficiency: float = 0.9,
) -> float:
    """Calculate required grid-side energy to reach the target state of charge."""
    _ensure_positive(capacity_kwh, "capacity_kwh")
    _ensure_soc(current_soc_percent, "current_soc_percent")
    _ensure_soc(target_soc_percent, "target_soc_percent")

    if not 0 < charging_efficiency <= 1:
        raise ValueError("charging_efficiency must be greater than 0 and at most 1")

    if target_soc_percent <= current_soc_percent:
        return 0.0

    vehicle_energy_kwh = capacity_kwh * ((target_soc_percent - current_soc_percent) / 100)
    return round(vehicle_energy_kwh / charging_efficiency, 3)


def charging_duration_hours(required_energy_kwh: float, charge_power_w: float) -> float:
    """Calculate required charging duration in hours."""
    _ensure_non_negative(required_energy_kwh, "required_energy_kwh")
    _ensure_non_negative(charge_power_w, "charge_power_w")

    if required_energy_kwh == 0:
        return 0.0

    if charge_power_w == 0:
        return inf

    return round(required_energy_kwh / (charge_power_w / 1000), 3)


def _ensure_non_negative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _ensure_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _ensure_soc(value: float, name: str) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


def _validate_limits(limits: ChargeLimits) -> None:
    _ensure_positive(limits.minimum_current_a, "minimum_current_a")
    _ensure_positive(limits.maximum_current_a, "maximum_current_a")
    _ensure_positive(limits.voltage_v, "voltage_v")
    _ensure_positive(limits.current_step_a, "current_step_a")

    if limits.phases not in {1, 3}:
        raise ValueError("phases must be 1 or 3")

    if limits.maximum_current_a < limits.minimum_current_a:
        raise ValueError("maximum_current_a must be at least minimum_current_a")
