"""Constants for PV Charge Manager."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "pv_charge_manager"
NAME: Final = "PV Charge Manager"

PLATFORMS: Final = [
    "sensor",
    "binary_sensor",
    "number",
    "select",
    "switch",
    "button",
]

CONF_NAME: Final = "name"
DEFAULT_NAME: Final = NAME

CONF_GRID_IMPORT_SENSOR: Final = "grid_import_sensor"
CONF_GRID_EXPORT_SENSOR: Final = "grid_export_sensor"
CONF_HOME_CONSUMPTION_SENSOR: Final = "home_consumption_sensor"
CONF_BATTERY_SOC_SENSOR: Final = "battery_soc_sensor"
CONF_BATTERY_CHARGE_POWER_SENSOR: Final = "battery_charge_power_sensor"
CONF_RESERVE_POWER_W: Final = "reserve_power_w"

DEFAULT_RESERVE_POWER_W: Final = 300.0
DEFAULT_VOLTAGE_V: Final = 230.0
DEFAULT_MIN_CURRENT_A: Final = 6.0
DEFAULT_MAX_CURRENT_A: Final = 16.0
DEFAULT_PHASES: Final = 3
