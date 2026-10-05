"""Day preview: battery priority, car target, buffer, price and always-charge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

CHEAP_EUR = 0.12
STEP = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class PreviewSlot:
    """One forecast interval."""

    start: datetime
    end: datetime
    pv_w: float
    home_w: float
    price_eur: float = 0.3


@dataclass(frozen=True, slots=True)
class PreviewConfig:
    """Limits for one preview run. Powers are watts, energies are kWh, SOC is percent."""

    battery_soc: float
    battery_capacity_kwh: float
    battery_max_charge_w: float
    battery_efficiency: float
    priority_soc: float
    buffer_soc: float
    max_soc: float
    vehicle_soc: float
    vehicle_capacity_kwh: float
    target_soc: float
    vehicle_efficiency: float
    min_power_w: float
    max_power_w: float
    reserve_power_w: float = 300.0
    always_charge: bool = False
    use_price: bool = False
    departure: datetime | None = None


@dataclass(frozen=True, slots=True)
class PreviewCase:
    """Result for one forecast factor."""

    chargeable_kwh: float
    battery_kwh: float
    vehicle_kwh: float
    grid_kwh: float
    battery_support_kwh: float
    battery_priority_at: datetime | None
    battery_full_at: datetime | None
    vehicle_target_at: datetime | None
    battery_reachable_soc: int
    vehicle_reachable_soc: int
    vehicle_missing_kwh: float
    minimum_power: str


def simulate_case(
    slots: list[PreviewSlot], config: PreviewConfig, factor: float
) -> PreviewCase:
    """Fill the battery to the priority first, then the vehicle."""
    stored = _kwh(config.battery_soc, config.battery_capacity_kwh)
    priority = _kwh(config.priority_soc, config.battery_capacity_kwh)
    maximum = _kwh(config.max_soc, config.battery_capacity_kwh)
    buffer = _kwh(config.buffer_soc, config.battery_capacity_kwh)
    vehicle = _kwh(config.vehicle_soc, config.vehicle_capacity_kwh)
    target = _kwh(config.target_soc, config.vehicle_capacity_kwh)
    full = config.vehicle_capacity_kwh

    battery_kwh = vehicle_kwh = chargeable = grid_kwh = support_kwh = 0.0
    above_min_hours = 0.0
    priority_at = slots[0].start if slots and stored >= priority else None
    full_at = slots[0].start if slots and stored >= maximum else None
    target_at = slots[0].start if slots and vehicle >= target else None

    for slot in slots:
        if slot.end <= slot.start:
            raise ValueError("slot end must be after slot start")
        surplus_w = max(0.0, slot.pv_w * factor - slot.home_w - config.reserve_power_w)
        cheap = config.use_price and slot.price_eur <= CHEAP_EUR
        cursor = slot.start
        while cursor < slot.end:
            nxt = min(cursor + STEP, slot.end)
            hours = (nxt - cursor).total_seconds() / 3600
            car_allowed = config.departure is None or cursor < config.departure
            if surplus_w >= config.min_power_w:
                above_min_hours += hours
            chargeable += (surplus_w / 1000) * hours

            battery_charge_w = 0.0
            from_surplus = 0.0
            if stored < priority - 0.001:
                battery_charge_w = min(surplus_w, config.battery_max_charge_w)
            else:
                if car_allowed:
                    from_surplus = min(surplus_w, config.max_power_w)
                leftover = max(0.0, surplus_w - from_surplus)
                if stored < maximum:
                    battery_charge_w = min(leftover, config.battery_max_charge_w)

            from_battery = 0.0
            from_grid = 0.0
            if car_allowed and vehicle < target - 0.001:
                desired = from_surplus
                if config.always_charge:
                    desired = max(desired, config.min_power_w)
                if cheap and stored >= priority - 0.02:
                    desired = config.max_power_w
                extra = max(0.0, desired - from_surplus)
                if extra > 0 and battery_charge_w == 0 and stored > buffer + 0.001:
                    available_w = ((stored - buffer) * 1000) / hours
                    from_battery = min(extra, available_w, config.battery_max_charge_w)
                    extra -= from_battery
                from_grid = extra

            stored = min(
                maximum,
                stored + (battery_charge_w / 1000) * hours * config.battery_efficiency,
            )
            stored = max(0.0, stored - (from_battery / 1000) * hours)
            battery_kwh += (battery_charge_w / 1000) * hours * config.battery_efficiency
            support_kwh += (from_battery / 1000) * hours
            if priority_at is None and stored >= priority - 0.02:
                priority_at = cursor
            if full_at is None and stored >= maximum - 0.02:
                full_at = cursor

            vehicle_power_w = from_surplus + from_battery + from_grid
            if car_allowed and vehicle < full and vehicle_power_w > 0:
                vehicle = min(
                    full,
                    vehicle
                    + (vehicle_power_w / 1000) * hours * config.vehicle_efficiency,
                )
                vehicle_kwh += (vehicle_power_w / 1000) * hours
                grid_kwh += (from_grid / 1000) * hours
                if target_at is None and vehicle >= target - 0.02:
                    target_at = cursor
            cursor = nxt

    missing = max(0.0, target - vehicle)
    missing_kwh = (
        missing / config.vehicle_efficiency if config.vehicle_efficiency else 0.0
    )
    if above_min_hours >= 2:
        minimum = "possible"
    elif above_min_hours > 0:
        minimum = "brief"
    else:
        minimum = "never"

    return PreviewCase(
        chargeable_kwh=round(chargeable, 1),
        battery_kwh=round(battery_kwh, 1),
        vehicle_kwh=round(vehicle_kwh, 1),
        grid_kwh=round(grid_kwh, 1),
        battery_support_kwh=round(support_kwh, 1),
        battery_priority_at=priority_at,
        battery_full_at=full_at,
        vehicle_target_at=target_at,
        battery_reachable_soc=_pct(stored, config.battery_capacity_kwh),
        vehicle_reachable_soc=_pct(vehicle, config.vehicle_capacity_kwh),
        vehicle_missing_kwh=round(missing_kwh, 1),
        minimum_power=minimum,
    )


def _kwh(soc: float, capacity: float) -> float:
    return (soc / 100) * capacity


def _pct(stored: float, capacity: float) -> int:
    if capacity <= 0:
        return 0
    return round(min(100, max(0, (stored / capacity) * 100)))
