"""Zero-export and night-reserve tests. They do not change the wallbox current."""

from datetime import UTC, datetime

from custom_components.pv_charge_manager.balance import storage_outlook, zero_export_status
from custom_components.pv_charge_manager.panel import build_panel_snapshot

NOW = datetime(2026, 10, 6, 20, 0, tzinfo=UTC)


def test_zero_export_uses_the_balance_without_a_setpoint() -> None:
    status = zero_export_status(4000, 800, 500, 0, 0)
    assert status["zero_export"] == "active"
    assert status["balance_surplus_w"] == 2700
    assert "recommended_current_a" not in status
    assert "surplus_power_w" not in status


def test_missing_balance_keeps_the_grid_in_the_lead() -> None:
    status = zero_export_status(None, 800, 0, 0, 0)
    assert status["zero_export"] == "unknown"
    assert status["balance_surplus_w"] is None
    assert "Netzbezug" in status["zero_export_detail"]


def test_real_export_is_not_zero_export() -> None:
    status = zero_export_status(4000, 800, 0, 0, 2500)
    assert status["zero_export"] == "inactive"
    assert status["balance_surplus_w"] is None


def test_night_reserve_holds_when_the_battery_covers_the_house() -> None:
    outlook = storage_outlook(
        now=NOW,
        battery_soc=80,
        battery_capacity_kwh=10,
        reserve_soc=20,
        home_w=100,
        reserve_power_w=0,
        forecast_w=None,
    )
    assert outlook["morning_soc"] > 20
    assert "reicht" in outlook["night_reserve"]
    assert "nicht" not in outlook["night_reserve"]
    assert outlook["autonomy_hours"] == 60.0


def test_night_reserve_stops_at_the_reserve() -> None:
    outlook = storage_outlook(
        now=NOW,
        battery_soc=50,
        battery_capacity_kwh=10,
        reserve_soc=20,
        home_w=500,
        forecast_w=None,
    )
    assert outlook["morning_soc"] == 20
    assert outlook["site_meta"]["hit_reserve"] is True
    assert "nicht" in outlook["night_reserve"]
    assert outlook["autonomy_hours"] == 6.0


def test_good_morning_is_not_below_the_bad_one() -> None:
    common = {
        "now": NOW,
        "battery_soc": 40,
        "battery_capacity_kwh": 10,
        "reserve_soc": 20,
        "home_w": 100,
        "battery_max_charge_w": 500,
        "battery_efficiency": 1,
        "reserve_power_w": 0,
        "forecast_w": [600.0] * 12,
    }
    outlook = storage_outlook(**common, factor=1.0)
    assert outlook["site_meta"]["morning_soc_early"] >= outlook["site_meta"]["morning_soc_late"]
    assert outlook["morning_soc"] >= outlook["site_meta"]["morning_soc_late"]


def test_panel_shows_the_night_sentence_and_keeps_the_current() -> None:
    snapshot = build_panel_snapshot(
        {
            "night_reserve": "Die Nachtreserve reicht. Morgen früh etwa 60 Prozent.",
            "recommended_current_a": 6,
            "plan_status": "feasible",
            "chargeable_kwh_today": 1,
            "vehicle_full_at": "2026-10-06T18:00:00+00:00",
        },
        {"mode": "smart"},
    )
    assert snapshot["night_reserve"].startswith("Die Nachtreserve")
    assert snapshot["recommended_current_a"] == 6
