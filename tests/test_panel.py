"""Panel snapshot tests. They do not need Home Assistant and do not plan a charge."""

from __future__ import annotations

import pytest

from custom_components.pv_charge_manager.backup import default_settings
from custom_components.pv_charge_manager.controls import RejectedControl
from custom_components.pv_charge_manager.panel import (
    apply_panel_control,
    build_panel_snapshot,
    collect_probe,
    entity_map_for_probe,
)


def test_missing_forecast_is_not_zero() -> None:
    snapshot = build_panel_snapshot({"pv_power_w": 1500}, default_settings())
    assert snapshot["days"][0]["chargeable_kwh"] is None
    assert snapshot["days"][1]["chargeable_kwh"] is None
    assert snapshot["flow"]["grid_import_w"] is None
    assert "Prognose" in snapshot["sentence"]
    assert snapshot["recommended_current_a"] is None


def test_feasible_sentence_uses_the_band() -> None:
    snapshot = build_panel_snapshot(
        {
            "plan_status": "feasible",
            "chargeable_kwh_today": 12,
            "chargeable_kwh_tomorrow": 4,
            "vehicle_full_at": "2026-10-06T14:30:00+02:00",
            "battery_full_at_early": "2026-10-06T14:30:00+02:00",
            "battery_full_at_late": "2026-10-06T16:10:00+02:00",
            "preview_meta": {"assumption": True},
        },
        default_settings(),
    )
    assert "gegen 14:30" in snapshot["sentence"]
    assert snapshot["battery_band"] == "zwischen 14:30 und 16:10"
    assert snapshot["days"][0]["chargeable_kwh"] == 12
    assert "Annahme" in snapshot["detail"]


def test_no_sun_sentence_does_not_invent_a_setpoint() -> None:
    snapshot = build_panel_snapshot(
        {
            "plan_status": "infeasible",
            "minimum_power_today": "never",
            "chargeable_kwh_today": 0,
            "chargeable_kwh_tomorrow": 0,
            "recommended_current_a": 6,
        },
        default_settings(),
    )
    assert "Mindestleistung" in snapshot["sentence"]
    assert snapshot["recommended_current_a"] == 6
    assert snapshot["days"][0]["chargeable_kwh"] == 0


def test_rejected_control_keeps_the_previous_value() -> None:
    settings = default_settings()
    plans: list[dict] = []
    apply_panel_control(settings, plans, "mode", "now")
    with pytest.raises(RejectedControl):
        apply_panel_control(settings, plans, "mode", "boost")
    assert settings["mode"] == "now"
    apply_panel_control(settings, plans, "departure", "18:00")
    assert plans == [{"departure": "18:00"}]
    with pytest.raises(RejectedControl):
        apply_panel_control(settings, plans, "departure", "25:99")
    assert plans == [{"departure": "18:00"}]
    apply_panel_control(settings, plans, "always_charge", False)
    assert settings["always_charge"] is False


def test_options_fill_a_missing_entity_map() -> None:
    merged = entity_map_for_probe({}, {"grid_import_sensor": "sensor.grid", "phases": 3})
    assert merged == {"grid_import_sensor": "sensor.grid"}


def test_probe_uses_the_everyday_words() -> None:
    rows = collect_probe(
        {
            "grid_import_sensor": "sensor.grid_in",
            "grid_export_sensor": "sensor.grid_out",
        },
        default_settings(),
        {"sensor.grid_in": {"state": "100", "age_s": 5}},
    )
    by_id = {row["entity_id"]: row["label"] for row in rows}
    assert by_id["sensor.grid_in"] == "geladen"
    assert by_id["sensor.grid_out"] == "fehlt"


def test_week_and_late_window_roundtrip() -> None:
    settings = default_settings()
    plans: list[dict] = [{"departure": "18:00"}]
    apply_panel_control(settings, plans, "late_hours", 2)
    apply_panel_control(settings, plans, "week_mo_start", "08:00")
    apply_panel_control(settings, plans, "week_mo_end", "18:00")
    assert plans[0]["late_hours"] == 2
    assert plans[0]["week"]["mo"] == {"start": "08:00", "end": "18:00"}
    assert plans[0]["departure"] == "18:00"
    snapshot = build_panel_snapshot(
        {"balancing": "Der Zellenausgleich ist nicht fällig.", "recommended_current_a": 8},
        settings,
        plans=plans,
    )
    assert snapshot["controls"]["late_hours"] == 2
    assert snapshot["controls"]["week"]["di"] == {"start": "", "end": ""}
    assert "nicht fällig" in snapshot["balancing"]
    assert snapshot["recommended_current_a"] == 8
    apply_panel_control(settings, plans, "late_hours", 0)
    assert "late_hours" not in plans[0]
    with pytest.raises(RejectedControl):
        apply_panel_control(settings, plans, "week_di_start", "25:99")
    apply_panel_control(settings, plans, "week_mo_start", "")
    apply_panel_control(settings, plans, "week_mo_end", "")
    assert "week" not in plans[0]
    assert plans[0]["departure"] == "18:00"
