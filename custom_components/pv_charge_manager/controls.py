"""Dashboard inputs. They change the stored plan, not the wallbox setpoint."""

from __future__ import annotations

import math
from typing import Any

MODES = ("off", "smart", "now")
STRATEGIES = ("forecast", "forecast_price")
SELECTS = {"mode": MODES, "strategy": STRATEGIES}
NUMBER_SPECS = {
    "solar_share": (0.0, 100.0, 1.0),
    "priority_soc": (0.0, 100.0, 1.0),
    "buffer_soc": (0.0, 100.0, 1.0),
    "reserve_soc": (0.0, 100.0, 1.0),
    "price_limit_eur": (0.0, 2.0, 0.01),
    "target_soc": (0.0, 100.0, 1.0),
}
_SELECT_DEFAULTS = {"mode": "smart", "strategy": "forecast"}
_NUMBER_DEFAULTS = {
    "solar_share": 100.0,
    "priority_soc": 70.0,
    "buffer_soc": 40.0,
    "reserve_soc": 20.0,
    "price_limit_eur": 0.12,
    "target_soc": 80.0,
}


class RejectedControl(ValueError):
    """The dashboard sent a value outside the allowed range."""


def device_info(entry_id: str, title: str) -> dict[str, Any]:
    """Device registry payload shared by the input entities."""
    return {
        "identifiers": {("pv_charge_manager", entry_id)},
        "name": title,
        "manufacturer": "PV Charge Manager",
    }


def read_select(settings: dict[str, Any], key: str) -> str:
    """Return a stored choice, or the default when the stored value is unknown."""
    value = settings.get(key, _SELECT_DEFAULTS[key])
    if value not in SELECTS[key]:
        return _SELECT_DEFAULTS[key]
    return str(value)


def write_select(settings: dict[str, Any], key: str, value: str) -> None:
    """Store a mode or strategy. Unknown choices are rejected."""
    if key not in SELECTS or value not in SELECTS[key]:
        raise RejectedControl(key)
    settings[key] = value


def read_number(settings: dict[str, Any], key: str) -> float:
    """Return a stored number inside its limits."""
    low, high, _step = NUMBER_SPECS[key]
    raw = _raw_number(settings, key)
    if raw is None:
        return _NUMBER_DEFAULTS[key]
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _NUMBER_DEFAULTS[key]
    if not math.isfinite(value):
        return _NUMBER_DEFAULTS[key]
    return min(high, max(low, value))


def write_number(settings: dict[str, Any], key: str, value: float) -> None:
    """Store a number. Values outside the range are rejected and not rounded in."""
    spec = NUMBER_SPECS.get(key)
    if spec is None:
        raise RejectedControl(str(key))
    low, high, step = spec
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise RejectedControl(key) from err
    if not math.isfinite(number):
        raise RejectedControl(key)
    decimals = 0 if step >= 1 else 2
    number = round(number, decimals)
    if number < low or number > high:
        raise RejectedControl(key)
    if key == "target_soc":
        vehicle = settings.get("vehicle")
        if not isinstance(vehicle, dict):
            vehicle = {}
            settings["vehicle"] = vehicle
        vehicle["target_soc_percent"] = number
        return
    settings[key] = number


def read_always_charge(settings: dict[str, Any]) -> bool:
    """Return whether the car keeps the minimum power without sun."""
    return bool(settings.get("always_charge", False))


def write_always_charge(settings: dict[str, Any], value: bool) -> None:
    """Store the always-charge switch."""
    settings["always_charge"] = bool(value)


def _raw_number(settings: dict[str, Any], key: str) -> Any:
    if key != "target_soc":
        return settings.get(key)
    vehicle = settings.get("vehicle")
    if not isinstance(vehicle, dict):
        return None
    return vehicle.get("target_soc_percent")
