"""Tests for the store, backup sections and the configuration draft."""

from __future__ import annotations

import json

from custom_components.pv_charge_manager.backup import default_settings
from custom_components.pv_charge_manager.probe import EntitySample, probe_entity
from custom_components.pv_charge_manager.setup_draft import SetupDraft
from custom_components.pv_charge_manager.storage import RuntimeStore, apply_import


def test_export_then_import_keeps_the_same_state() -> None:
    store = RuntimeStore("entry-1")
    store.state.settings["mode"] = "off"
    store.state.settings["vehicle"] = {"name": "Auto", "capacity_kwh": 60, "secret": "hidden"}
    store.state.plans = [{"departure": "18:00"}]
    store.state.entity_map = {"pv_power_sensors": ["sensor.gone"]}
    store.state.learning = {"factor": 1.0, "samples": 2}
    store.state.step = "vehicle"

    document = store.export_backup()
    assert document["schema_version"] == 1
    assert "secret" not in document["settings"]["vehicle"]
    assert store.key == "pv_charge_manager.entry-1"

    other = RuntimeStore("entry-2")
    result = apply_import(other, json.dumps(document))
    assert result["ok"] is True
    assert result["warnings"] == []
    assert other.state.settings["mode"] == "off"
    assert other.state.settings["strategy"] == "forecast"
    assert other.state.settings["vehicle"]["name"] == "Auto"
    assert other.state.plans == [{"departure": "18:00"}]
    assert other.state.entity_map["pv_power_sensors"] == ["sensor.gone"]
    assert other.state.learning["samples"] == 2
    assert other.state.step == "vehicle"
    assert other.key == "pv_charge_manager.entry-2"


def test_import_rejects_broken_json_without_replacing_state() -> None:
    store = RuntimeStore("entry-1")
    store.state.step = "battery"
    result = apply_import(store, "{")
    assert result == {"ok": False, "error": "invalid_json"}
    assert store.state.step == "battery"
    rejected = apply_import(store, {"schema_version": 99, "settings": {}})
    assert rejected["ok"] is False
    assert store.state.step == "battery"


def test_draft_keeps_earlier_steps() -> None:
    draft = SetupDraft()
    assert (
        draft.apply(
            "site",
            {"grid_import_sensor": "sensor.grid_in", "grid_export_sensor": "sensor.grid_out"},
        )
        == []
    )
    assert draft.apply("pv", {"pv_power_sensors": ["sensor.pv"]}) == []
    assert draft.entity_map["grid_import_sensor"] == "sensor.grid_in"
    assert draft.step == "pv"


def test_invalid_phases_are_not_stored() -> None:
    draft = SetupDraft()
    assert draft.apply("wallbox", {"phases": 3, "min_current_a": 6, "max_current_a": 16}) == []
    assert draft.apply("wallbox", {"phases": 2}) == ["invalid_phases"]
    assert draft.settings["phases"] == 3


def test_loaded_json_keeps_unknown_entity_and_marks_it_missing() -> None:
    draft = SetupDraft()
    draft.load_json(
        {
            "schema_version": 1,
            "step": "pv",
            "settings": default_settings(),
            "entity_map": {"pv_power_sensors": ["sensor.gone"]},
            "plans": [],
            "learning": {},
        }
    )
    hits = draft.record_probe(
        [
            EntitySample(
                "sensor.gone",
                False,
                None,
                None,
                False,
                True,
                "kein Wert",
                "kein Wert",
            )
        ]
    )
    assert draft.step == "pv"
    assert hits[0].status == "missing"
    assert draft.entity_map["pv_power_sensors"] == ["sensor.gone"]
    assert draft.continuation_error("pv") == "required_missing"


def test_stale_entity_does_not_block_the_step() -> None:
    draft = SetupDraft()
    draft.apply("pv", {"pv_power_sensors": ["sensor.pv"]})
    draft.record_probe([EntitySample("sensor.pv", True, "10", 5000, True, True, "10", "10000")])
    assert draft.probe[0].status == "stale"
    assert draft.continuation_error("pv") is None


def test_binary_switch_on_is_loaded() -> None:
    hit = probe_entity(
        EntitySample("switch.wallbox", True, "on", 1, False, True, "on", "on", "binary")
    )
    assert hit.status == "loaded"
