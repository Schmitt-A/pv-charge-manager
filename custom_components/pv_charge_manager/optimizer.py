"""Charging window optimizer helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .calculation import ChargeLimits, current_for_power_a, power_for_current_w


@dataclass(frozen=True, slots=True)
class ForecastSlot:
    """Forecast surplus for a time interval."""

    start: datetime
    end: datetime
    available_power_w: float
    price_eur_per_kwh: float | None = None

    @property
    def duration_hours(self) -> float:
        """Return slot length in hours."""
        seconds = (self.end - self.start).total_seconds()
        return max(0.0, seconds / 3600)


@dataclass(frozen=True, slots=True)
class ScheduledSlot:
    """Planned charging interval."""

    start: datetime
    end: datetime
    current_a: float
    charge_power_w: float
    energy_kwh: float


@dataclass(frozen=True, slots=True)
class ChargePlan:
    """Result of a charge planning run."""

    slots: list[ScheduledSlot]
    planned_energy_kwh: float
    unmet_energy_kwh: float


def build_charge_plan(
    slots: list[ForecastSlot],
    required_energy_kwh: float,
    limits: ChargeLimits,
) -> ChargePlan:
    """Choose forecast slots that can satisfy the required charging energy."""
    if required_energy_kwh < 0:
        raise ValueError("required_energy_kwh must not be negative")

    remaining_energy_kwh = required_energy_kwh
    selected_slots: list[ScheduledSlot] = []

    for slot in _rank_slots(slots):
        _validate_slot(slot)
        if remaining_energy_kwh <= 0:
            break

        current_a = current_for_power_a(slot.available_power_w, limits)
        if current_a <= 0:
            continue

        charge_power_w = power_for_current_w(current_a, limits)
        possible_energy_kwh = (charge_power_w / 1000) * slot.duration_hours
        energy_kwh = min(remaining_energy_kwh, possible_energy_kwh)

        if energy_kwh <= 0:
            continue

        duration_hours = energy_kwh / (charge_power_w / 1000)
        selected_slots.append(
            ScheduledSlot(
                start=slot.start,
                end=slot.start + timedelta(hours=duration_hours),
                current_a=current_a,
                charge_power_w=charge_power_w,
                energy_kwh=round(energy_kwh, 3),
            )
        )
        remaining_energy_kwh -= energy_kwh

    planned_slots = sorted(selected_slots, key=lambda scheduled: scheduled.start)
    planned_energy_kwh = round(sum(slot.energy_kwh for slot in planned_slots), 3)
    return ChargePlan(
        slots=planned_slots,
        planned_energy_kwh=planned_energy_kwh,
        unmet_energy_kwh=round(max(0.0, required_energy_kwh - planned_energy_kwh), 3),
    )


def _rank_slots(slots: list[ForecastSlot]) -> list[ForecastSlot]:
    return sorted(
        slots,
        key=lambda slot: (
            slot.price_eur_per_kwh if slot.price_eur_per_kwh is not None else 0,
            -slot.available_power_w,
            slot.start,
        ),
    )


def _validate_slot(slot: ForecastSlot) -> None:
    if slot.end <= slot.start:
        raise ValueError("slot end must be after slot start")
    if slot.available_power_w < 0:
        raise ValueError("slot available_power_w must not be negative")
    if slot.price_eur_per_kwh is not None and slot.price_eur_per_kwh < 0:
        raise ValueError("slot price_eur_per_kwh must not be negative")
