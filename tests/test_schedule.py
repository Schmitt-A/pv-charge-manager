"""Weekly window and late grid window. They do not write to a device."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.pv_charge_manager.schedule import grid_window_open, schedule_open

BERLIN = ZoneInfo("Europe/Berlin")
MONDAY = datetime(2026, 10, 5, 10, 0, tzinfo=BERLIN)
TUESDAY = datetime(2026, 10, 6, 10, 0, tzinfo=BERLIN)


def test_only_monday_closes_tuesday() -> None:
    week = {"mo": {"start": "08:00", "end": "18:00"}}
    assert schedule_open(MONDAY, week) is True
    assert schedule_open(TUESDAY, week) is False
    assert schedule_open(TUESDAY, None) is True
    assert schedule_open(TUESDAY, {}) is True
    assert schedule_open(MONDAY, {"mo": {"start": "08:00"}}) is True


def test_overnight_window_uses_the_clock() -> None:
    week = {"di": {"start": "22:00", "end": "06:00"}}
    late = TUESDAY.replace(hour=23)
    noon = TUESDAY.replace(hour=12)
    assert schedule_open(late, week) is True
    assert schedule_open(noon, week) is False


def test_late_window_waits_until_departure() -> None:
    departure = TUESDAY.replace(hour=18)
    assert grid_window_open(TUESDAY, departure, 2) is False
    assert grid_window_open(departure - timedelta(hours=2), departure, 2) is True
    assert grid_window_open(TUESDAY, departure, 0) is True
    assert grid_window_open(TUESDAY, None, 2) is True
