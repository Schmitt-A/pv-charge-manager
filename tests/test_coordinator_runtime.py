from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.pv_charge_manager.coordinator import PVChargeManagerCoordinator


class FakeStates:
    """Small state registry for coordinator service tests."""

    def __init__(self) -> None:
        self.items = {
            "sensor.pv": SimpleNamespace(state="10", attributes={"unit_of_measurement": "kW"}),
            "sensor.home": SimpleNamespace(state="500", attributes={"unit_of_measurement": "W"}),
            "binary_sensor.connected": SimpleNamespace(state="on", attributes={}),
            "switch.wallbox": SimpleNamespace(state="off", attributes={}),
            "number.wallbox": SimpleNamespace(state="0", attributes={"unit_of_measurement": "A"}),
        }

    def get(self, entity_id):
        """Return a fake Home Assistant state."""
        return self.items.get(entity_id)


class FakeServices:
    """Record service calls and update the corresponding fake state."""

    def __init__(self, states: FakeStates) -> None:
        self.calls = []
        self.states = states

    async def async_call(self, domain, service, data, blocking=False):
        """Record and apply a switch or number service call."""
        self.calls.append((domain, service, data, blocking))
        entity_id = data["entity_id"]
        if domain == "switch":
            self.states.items[entity_id].state = "on" if service == "turn_on" else "off"
        else:
            self.states.items[entity_id].state = str(data["value"])


class FakeHass:
    """Minimal Home Assistant object used by the coordinator."""

    def __init__(self) -> None:
        self.states = FakeStates()
        self.services = FakeServices(self.states)


OPTIONS = {
    "pv_power_sensors": ["sensor.pv"],
    "home_consumption_sensor": "sensor.home",
    "wallbox_control_enabled": True,
    "wallbox_charging_switch": "switch.wallbox",
    "wallbox_current_number": "number.wallbox",
    "wallbox_connected_sensor": "binary_sensor.connected",
    "wallbox_start_delay_s": 0,
    "wallbox_stop_delay_s": 0,
    "wallbox_minimum_runtime_s": 0,
}


def test_wallbox_service_calls_start_then_stop_on_missing_pv() -> None:
    async def run_test() -> None:
        hass = FakeHass()
        coordinator = PVChargeManagerCoordinator(
            hass,
            logging.getLogger("test"),
            SimpleNamespace(options=OPTIONS),
        )

        first = await coordinator._async_update_data()

        assert first["wallbox_action"] == "start"
        assert [call[1] for call in hass.services.calls] == ["set_value", "turn_on"]

        hass.states.items["sensor.pv"].state = "unknown"
        second = await coordinator._async_update_data()

        assert second["available"] is False
        assert second["wallbox_action"] == "stop"
        assert hass.services.calls[-1][1] == "turn_off"

    asyncio.run(run_test())
