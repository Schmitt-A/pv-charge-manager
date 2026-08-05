from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.pv_charge_manager.calculation import ChargeLimits
from custom_components.pv_charge_manager.optimizer import ForecastSlot, build_charge_plan


def test_build_charge_plan_prefers_high_surplus_slots() -> None:
    start = datetime(2026, 1, 1, 10, 0)
    slots = [
        ForecastSlot(start, start + timedelta(hours=1), available_power_w=4_000),
        ForecastSlot(
            start + timedelta(hours=1), start + timedelta(hours=2), available_power_w=11_500
        ),
    ]

    plan = build_charge_plan(
        slots,
        required_energy_kwh=5,
        limits=ChargeLimits(minimum_current_a=6, maximum_current_a=16, phases=3),
    )

    assert plan.unmet_energy_kwh == 0
    assert len(plan.slots) == 1
    assert plan.slots[0].start == start + timedelta(hours=1)
    assert plan.slots[0].energy_kwh == 5
