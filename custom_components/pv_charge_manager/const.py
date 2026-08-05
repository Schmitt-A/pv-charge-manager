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
CONF_PV_POWER_SENSORS: Final = "pv_power_sensors"
CONF_FORECAST_SENSORS: Final = "forecast_sensors"
CONF_RESERVE_POWER_W: Final = "reserve_power_w"
CONF_FEED_IN_TARIFF_EUR_PER_KWH: Final = "feed_in_tariff_eur_per_kwh"
CONF_VOLTAGE_V: Final = "voltage_v"
CONF_MIN_CURRENT_A: Final = "min_current_a"
CONF_MAX_CURRENT_A: Final = "max_current_a"
CONF_PHASES: Final = "phases"

DEFAULT_RESERVE_POWER_W: Final = 300.0
DEFAULT_VOLTAGE_V: Final = 230.0
DEFAULT_MIN_CURRENT_A: Final = 6.0
DEFAULT_MAX_CURRENT_A: Final = 16.0
DEFAULT_PHASES: Final = 3
DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH: Final = 0.08

SENSOR_KEYS: Final = (
    "surplus_power",
    "recommended_current",
    "recommended_charge_power",
    "opportunity_cost",
)
