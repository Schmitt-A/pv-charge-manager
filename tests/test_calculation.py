from __future__ import annotations

from math import inf

import pytest

from custom_components.pv_charge_manager.calculation import (
    ChargeLimits,
    PowerSnapshot,
    available_surplus_power_w,
    charging_duration_hours,
    current_for_power_a,
    power_for_current_w,
    recommend_current,
    required_vehicle_energy_kwh,
)


def test_available_surplus_power_w_subtracts_home_battery_and_reserve() -> None:
    snapshot = PowerSnapshot(
        pv_power_w=18_500,
        home_consumption_w=3_200,
        battery_charge_power_w=4_000,
        reserve_power_w=300,
    )

    assert available_surplus_power_w(snapshot) == 11_000


def test_current_for_power_uses_valid_evse_step_without_exceeding_power() -> None:
    limits = ChargeLimits(minimum_current_a=6, maximum_current_a=16, phases=3)

    assert current_for_power_a(11_000, limits) == 15
    assert power_for_current_w(15, limits) == 10_350


def test_recommend_current_returns_zero_below_minimum_power() -> None:
    recommendation = recommend_current(
        PowerSnapshot(pv_power_w=2_000, home_consumption_w=500, reserve_power_w=300),
        ChargeLimits(minimum_current_a=6, maximum_current_a=16, phases=3),
    )

    assert recommendation.current_a == 0
    assert recommendation.charge_power_w == 0


def test_required_vehicle_energy_kwh_accounts_for_charging_losses() -> None:
    assert required_vehicle_energy_kwh(77, 35, 80, charging_efficiency=0.9) == 38.5


def test_charging_duration_hours_handles_zero_power() -> None:
    assert charging_duration_hours(0, 0) == 0
    assert charging_duration_hours(5, 0) == inf


def test_invalid_soc_is_rejected() -> None:
    with pytest.raises(ValueError):
        required_vehicle_energy_kwh(77, -1, 80)
