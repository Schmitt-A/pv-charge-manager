"""Tests for the pure preview, backup and probe modules."""

from datetime import datetime, timedelta, timezone

from custom_components.pv_charge_manager.backup import (
    UnsupportedSchema,
    export_document,
    import_document,
)
from custom_components.pv_charge_manager.preview import (
    PreviewConfig,
    PreviewSlot,
    simulate_case,
)
from custom_components.pv_charge_manager.probe import (
    EntitySample,
    blocks_step,
    probe_entity,
)

START = datetime(2026, 10, 6, 4, 0, tzinfo=timezone.utc)


def _slot(hour: int, pv: float, price: float = 0.3) -> PreviewSlot:
    start = START + timedelta(hours=hour)
    return PreviewSlot(start, start + timedelta(hours=1), pv, 600, price)


def _config(**overrides: object) -> PreviewConfig:
    values: dict[str, object] = {
        "battery_soc": 46,
        "battery_capacity_kwh": 10,
        "battery_max_charge_w": 5000,
        "battery_efficiency": 0.92,
        "priority_soc": 70,
        "buffer_soc": 40,
        "max_soc": 95,
        "vehicle_soc": 40,
        "vehicle_capacity_kwh": 60,
        "target_soc": 55,
        "vehicle_efficiency": 0.9,
        "min_power_w": 4140,
        "max_power_w": 11040,
        "departure": START + timedelta(hours=12),
    }
    values.update(overrides)
    return PreviewConfig(**values)


def test_battery_fills_before_the_car() -> None:
    slots = [_slot(index, 7000) for index in range(8)]
    result = simulate_case(slots, _config(), 1)
    assert result.battery_kwh > 0
    assert result.vehicle_target_at is not None
    assert result.battery_priority_at <= result.vehicle_target_at
    assert result.minimum_power == "possible"


def test_no_slot_above_minimum_power() -> None:
    slots = [_slot(index, 500) for index in range(4)]
    result = simulate_case(slots, _config(), 1)
    assert result.minimum_power == "never"
    assert result.vehicle_kwh == 0


def test_good_case_is_not_later_than_the_bad_case() -> None:
    slots = [_slot(index, 7000) for index in range(8)]
    good = simulate_case(slots, _config(), 1.12)
    bad = simulate_case(slots, _config(), 0.78)
    assert good.chargeable_kwh >= bad.chargeable_kwh
    assert good.battery_priority_at is not None and bad.battery_priority_at is not None
    assert good.battery_priority_at <= bad.battery_priority_at


def test_always_charge_uses_the_buffer_then_the_grid() -> None:
    slots = [_slot(0, 0)]
    plain = simulate_case(
        slots,
        _config(battery_soc=80, priority_soc=70, departure=START + timedelta(hours=1)),
        1,
    )
    held = simulate_case(
        slots,
        _config(
            battery_soc=80,
            priority_soc=70,
            buffer_soc=40,
            always_charge=True,
            departure=START + timedelta(hours=1),
        ),
        1,
    )
    blocked = simulate_case(
        slots,
        _config(
            battery_soc=80,
            priority_soc=70,
            buffer_soc=80,
            always_charge=True,
            departure=START + timedelta(hours=1),
        ),
        1,
    )
    assert plain.vehicle_kwh == 0
    assert held.battery_support_kwh > 0
    assert blocked.battery_support_kwh == 0
    assert blocked.grid_kwh > held.grid_kwh


def test_price_adds_grid_energy_before_departure() -> None:
    slots = [_slot(0, 0, 0.08)]
    forecast = simulate_case(
        slots,
        _config(battery_soc=80, priority_soc=70, departure=START + timedelta(hours=1)),
        1,
    )
    priced = simulate_case(
        slots,
        _config(
            battery_soc=80,
            priority_soc=70,
            use_price=True,
            departure=START + timedelta(hours=1),
        ),
        1,
    )
    assert forecast.grid_kwh == 0
    assert priced.grid_kwh > 0
    assert priced.vehicle_kwh > forecast.vehicle_kwh


def test_backup_roundtrip_and_future_schema() -> None:
    document = export_document({"mode": "off", "token": "hidden"}, "pv")
    assert "token" not in document["settings"]
    loaded = import_document({"schema_version": 1, "settings": {"mode": "off"}, "step": "pv"})
    assert loaded.settings["mode"] == "off"
    assert loaded.step == "pv"
    assert loaded.warnings
    try:
        import_document({"schema_version": 99, "settings": {}})
    except UnsupportedSchema:
        return
    raise AssertionError("newer schema was accepted")


def test_probe_statuses_block_only_required_failures() -> None:
    missing = probe_entity(
        EntitySample("sensor.pv", False, None, None, False, True, "kein Wert", "kein Wert")
    )
    stale = probe_entity(EntitySample("sensor.haus", True, "1", 2000, True, True, "1", "1"))
    empty = probe_entity(
        EntitySample("sensor.preis", False, None, None, False, False, "kein Wert", "kein Wert")
    )
    assert missing.status == "missing"
    assert stale.status == "stale"
    assert empty.status == "optional_empty"
    assert blocks_step([missing], {"sensor.pv"})
    assert not blocks_step([stale], {"sensor.haus"})
