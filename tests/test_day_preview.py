"""Tests for the forecast day preview. They do not need Home Assistant."""

from datetime import UTC, datetime, timedelta

from custom_components.pv_charge_manager.calculation import ChargeLimits
from custom_components.pv_charge_manager.day_preview import (
    build_day_preview,
    parse_number_series,
)

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
LIMITS = ChargeLimits()


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
        "limits": LIMITS,
    }
    values.update(overrides)
    return build_day_preview(**values)


def test_unreadable_forecast_is_not_a_series() -> None:
    assert parse_number_series("unknown") is None
    assert parse_number_series("keine zahl") is None
    assert parse_number_series("[1, -5]") is None
    assert parse_number_series("") is None


def test_forecast_accepts_json_comma_and_one_number() -> None:
    assert parse_number_series("[1000, 2000]") == [1000.0, 2000.0]
    assert parse_number_series("1000, 2000") == [1000.0, 2000.0]
    assert parse_number_series("1500") == [1500.0]


def test_few_samples_do_not_apply_the_learned_factor() -> None:
    low = _preview(learning={"factor": 1.3, "samples": 3})
    plain = _preview(learning={})
    assert low["chargeable_kwh_today"] == plain["chargeable_kwh_today"]
    assert low["preview_meta"]["forecast_trust"] == "low"
    assert low["preview_meta"]["learned_factor"] == 1.0


def test_seven_samples_scale_the_forecast() -> None:
    base = _preview(forecast_w=[5000.0] * 4, learning={"factor": 1.0, "samples": 7})
    scaled = _preview(forecast_w=[5000.0] * 4, learning={"factor": 1.2, "samples": 7})
    assert scaled["preview_meta"]["forecast_trust"] == "high"
    assert scaled["chargeable_kwh_today"] > base["chargeable_kwh_today"]


def test_good_battery_full_is_not_later_than_the_bad_one() -> None:
    result = _preview(
        vehicle_soc=80,
        target_soc=80,
        battery_soc=20,
        battery_max_charge_w=20000,
        departure=NOW,
        forecast_w=[8000.0] * 10,
    )
    early = result["battery_full_at_early"]
    late = result["battery_full_at_late"]
    assert early is not None and late is not None
    assert early <= late


def test_today_and_tomorrow_stay_separate() -> None:
    result = _preview(forecast_w=[1000.0] * 30, home_w=0, reserve_power_w=0)
    assert result["chargeable_kwh_today"] > 0
    assert result["chargeable_kwh_tomorrow"] > 0
    assert result["chargeable_kwh_today"] != result["chargeable_kwh_tomorrow"]


def test_no_sun_never_starts_and_is_infeasible() -> None:
    result = _preview(forecast_w=[0.0] * 6)
    assert result["minimum_power_today"] == "never"
    assert result["plan_status"] == "infeasible"
    assert result["vehicle_full_at"] is None


def test_enough_sun_is_feasible_without_touching_a_setpoint() -> None:
    result = _preview(
        battery_soc=80,
        priority_soc=70,
        vehicle_capacity_kwh=10,
        vehicle_soc=50,
        target_soc=60,
        forecast_w=[11000.0] * 6,
    )
    assert result["plan_status"] == "feasible"
    assert "recommended_current_a" not in result


def test_price_strategy_marks_a_short_day_as_grid() -> None:
    result = _preview(forecast_w=[0.0] * 4, use_price=True, prices=[0.08] * 4)
    assert result["plan_status"] == "needs_grid"


def test_missing_vehicle_sensor_is_an_assumption() -> None:
    result = _preview(assumption=True)
    assert result["preview_meta"]["assumption"] is True
    assert "70" in result["battery_recommendation"]
    assert "40" in result["battery_recommendation"]


def test_single_hour_does_not_invent_tomorrow() -> None:
    result = _preview(forecast_w=[4000.0])
    assert result["chargeable_kwh_tomorrow"] == 0.0
    assert result["chargeable_kwh_today"] > 0


def test_departure_keeps_the_plan_inside_the_window() -> None:
    soon = NOW + timedelta(minutes=30)
    blocked = _preview(departure=soon, forecast_w=[11000.0] * 8, battery_soc=80, priority_soc=70)
    open_plan = _preview(forecast_w=[11000.0] * 8, battery_soc=80, priority_soc=70)
    assert blocked["preview_meta"]["vehicle_kwh"] < open_plan["preview_meta"]["vehicle_kwh"]


def test_tuesday_schedule_blocks_the_car() -> None:
    closed = _preview(
        week={"mo": {"start": "00:00", "end": "23:59"}},
        battery_soc=90,
        priority_soc=50,
        forecast_w=[11000.0] * 6,
    )
    open_plan = _preview(battery_soc=90, priority_soc=50, forecast_w=[11000.0] * 6)
    assert closed["preview_meta"]["vehicle_kwh"] == 0
    assert open_plan["preview_meta"]["vehicle_kwh"] > 0


def test_late_window_keeps_a_cheap_hour_off_the_grid() -> None:
    shared = {
        "forecast_w": [0.0] * 4,
        "use_price": True,
        "prices": [0.05] * 4,
        "battery_soc": 80,
        "priority_soc": 70,
        "departure": NOW + timedelta(hours=12),
    }
    blocked = _preview(late_hours=2, **shared)
    open_plan = _preview(**shared)
    assert blocked["preview_meta"]["grid_kwh"] == 0
    assert open_plan["preview_meta"]["grid_kwh"] > 0


def test_a_trusted_source_replaces_the_site_factor() -> None:
    site = _preview(forecast_w=[5000.0] * 4, learning={"factor": 1.0, "samples": 7})
    sourced = _preview(
        forecast_w=[5000.0] * 4,
        learning={
            "factor": 1.0,
            "samples": 7,
            "sources": {"sensor.dach": {"factor": 0.8, "samples": 7}},
        },
    )
    ignored = _preview(
        forecast_w=[5000.0] * 4,
        learning={
            "factor": 1.2,
            "samples": 7,
            "sources": {"sensor.dach": {"factor": 0.8, "samples": 6}},
        },
    )
    assert sourced["preview_meta"]["learned_factor"] == 0.8
    assert sourced["chargeable_kwh_today"] < site["chargeable_kwh_today"]
    assert ignored["preview_meta"]["learned_factor"] == 1.2
