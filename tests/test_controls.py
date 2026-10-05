"""Tests for the dashboard inputs. They do not need Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.pv_charge_manager.backup import default_settings
from custom_components.pv_charge_manager.controls import (
    RejectedControl,
    read_always_charge,
    read_number,
    read_select,
    write_always_charge,
    write_number,
    write_select,
)
from custom_components.pv_charge_manager.day_preview import build_day_preview

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def _preview(**overrides: object) -> dict:
    values: dict[str, object] = {
        "forecast_w": [7000.0] * 8,
        "home_w": 600.0,
        "now": NOW,
        "battery_soc": 46.0,
        "battery_capacity_kwh": 10.0,
        "priority_soc": 70.0,
        "buffer_soc": 40.0,
        "max_soc": 95.0,
        "vehicle_soc": 40.0,
        "vehicle_capacity_kwh": 60.0,
        "target_soc": 55.0,
        "assumption": False,
    }
    values.update(overrides)
    return build_day_preview(**values)


def test_rejected_value_keeps_the_previous_setting() -> None:
    settings = default_settings()
    write_select(settings, "mode", "now")
    with pytest.raises(RejectedControl):
        write_select(settings, "mode", "boost")
    assert settings["mode"] == "now"
    assert read_select(settings, "strategy") == "forecast"
    with pytest.raises(RejectedControl):
        write_number(settings, "buffer_soc", 140)
    assert settings["buffer_soc"] == 40
    write_number(settings, "target_soc", 90)
    assert settings["vehicle"]["target_soc_percent"] == 90.0
    write_number(settings, "price_limit_eur", 0)
    assert settings["price_limit_eur"] == 0.0
    write_always_charge(settings, True)
    assert read_always_charge(settings) is True


def test_unknown_stored_choice_falls_back_without_writing() -> None:
    settings = {"mode": "boost", "strategy": "forecast"}
    assert read_select(settings, "mode") == "smart"
    assert settings["mode"] == "boost"
    assert read_number({}, "priority_soc") == 70.0


def test_mode_off_does_not_charge_the_car_or_the_setpoint() -> None:
    charging = _preview(battery_soc=80, priority_soc=70)
    paused = _preview(battery_soc=80, priority_soc=70, mode="off")
    assert paused["plan_status"] == "off"
    assert paused["preview_meta"]["vehicle_kwh"] == 0
    assert charging["preview_meta"]["vehicle_kwh"] > 0
    assert "recommended_current_a" not in paused


def test_mode_now_uses_full_power_from_the_grid() -> None:
    result = _preview(forecast_w=[0.0] * 4, battery_soc=80, priority_soc=70, mode="now")
    assert result["plan_status"] == "needs_grid"
    assert result["preview_meta"]["grid_kwh"] > 0


def test_lower_solar_share_counts_a_short_surplus() -> None:
    tight = _preview(forecast_w=[5000.0] * 6, home_w=600, solar_share=100)
    half = _preview(forecast_w=[5000.0] * 6, home_w=600, solar_share=50)
    assert tight["minimum_power_today"] == "never"
    assert half["minimum_power_today"] == "possible"


def test_price_limit_decides_which_hour_is_cheap() -> None:
    common = {
        "forecast_w": [0.0] * 4,
        "use_price": True,
        "prices": [0.10] * 4,
        "battery_soc": 80,
        "priority_soc": 70,
    }
    cheap = _preview(**common, cheap_eur=0.12)
    strict = _preview(**common, cheap_eur=0.05)
    assert cheap["preview_meta"]["grid_kwh"] > 0
    assert cheap["plan_status"] == "needs_grid"
    assert strict["preview_meta"]["grid_kwh"] == 0
