"""Forecast memory tests. They do not need Home Assistant."""

from datetime import UTC, datetime, timedelta

from custom_components.pv_charge_manager.forecast_log import record_forecast, record_sources

START = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _fill(learning: dict, day: int, *, pv_w: float, forecast_w: float) -> None:
    moment = START.replace(day=day)
    record_forecast(learning, now=moment, pv_w=pv_w, hour_forecast_w=forecast_w)
    for _ in range(120):
        moment += timedelta(seconds=30)
        record_forecast(learning, now=moment, pv_w=pv_w, hour_forecast_w=forecast_w)


def test_a_short_gap_does_not_invent_energy() -> None:
    learning: dict = {}
    record_forecast(learning, now=START, pv_w=0, hour_forecast_w=1000)
    record_forecast(learning, now=START + timedelta(hours=5), pv_w=5000, hour_forecast_w=1000)
    assert learning["hours"]["08"]["actual_wh"] < 200
    assert learning.get("samples", 0) == 0


def test_a_short_day_does_not_become_a_sample() -> None:
    learning: dict = {}
    record_forecast(learning, now=START, pv_w=1000, hour_forecast_w=2000)
    record_forecast(learning, now=START + timedelta(seconds=30), pv_w=1000, hour_forecast_w=2000)
    record_forecast(learning, now=START + timedelta(days=1), pv_w=0, hour_forecast_w=1000)
    assert learning.get("samples", 0) == 0


def test_seven_closed_days_move_the_factor() -> None:
    learning: dict = {}
    for day in range(1, 8):
        _fill(learning, day, pv_w=1000, forecast_w=2000)
    record_forecast(
        learning,
        now=datetime(2026, 10, 8, 8, 0, tzinfo=UTC),
        pv_w=0,
        hour_forecast_w=1000,
    )
    assert learning["samples"] == 7
    assert learning["factor"] < 1
    assert len(learning["history"]) == 7
    assert "recommended_current_a" not in learning


def test_naive_time_is_ignored() -> None:
    learning: dict = {}
    assert (
        record_forecast(learning, now=datetime(2026, 10, 1, 8, 0), pv_w=1000, hour_forecast_w=1000)
        is False
    )
    assert learning == {}


def test_sources_keep_separate_hours() -> None:
    learning: dict = {}
    sources = [
        {"id": "sensor.dach", "pv_w": 1000, "hour_w": 2000},
        {"id": "sensor.garage", "pv_w": 100, "hour_w": 50},
    ]
    record_sources(learning, now=START, sources=sources)
    record_sources(learning, now=START + timedelta(seconds=30), sources=sources)
    roof = learning["sources"]["sensor.dach"]["hours"]["08"]
    garage = learning["sources"]["sensor.garage"]["hours"]["08"]
    assert roof["forecast_w"] == 2000
    assert garage["forecast_w"] == 50
    assert roof["actual_wh"] > garage["actual_wh"]
