"""Config and options flow for PV Charge Manager."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_POWER_SENSOR,
    CONF_BATTERY_SOC_SENSOR,
    CONF_FEED_IN_TARIFF_EUR_PER_KWH,
    CONF_FORECAST_SENSORS,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_HOME_CONSUMPTION_SENSOR,
    CONF_MAX_CURRENT_A,
    CONF_MIN_CURRENT_A,
    CONF_NAME,
    CONF_PHASES,
    CONF_PV_POWER_SENSORS,
    CONF_RESERVE_POWER_W,
    CONF_VOLTAGE_V,
    CONF_WALLBOX_CHARGING_POWER_SENSOR,
    CONF_WALLBOX_CHARGING_SWITCH,
    CONF_WALLBOX_CONNECTED_SENSOR,
    CONF_WALLBOX_CONTROL_ENABLED,
    CONF_WALLBOX_CURRENT_NUMBER,
    CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR,
    CONF_WALLBOX_MIN_RUNTIME_S,
    CONF_WALLBOX_START_DELAY_S,
    CONF_WALLBOX_STOP_DELAY_S,
    DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH,
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_MIN_CURRENT_A,
    DEFAULT_NAME,
    DEFAULT_PHASES,
    DEFAULT_RESERVE_POWER_W,
    DEFAULT_VOLTAGE_V,
    DEFAULT_WALLBOX_MIN_RUNTIME_S,
    DEFAULT_WALLBOX_START_DELAY_S,
    DEFAULT_WALLBOX_STOP_DELAY_S,
    DOMAIN,
)


class PVChargeManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Charge Manager."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create the initial config entry."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_NAME: user_input[CONF_NAME]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return PVChargeManagerOptionsFlow()


class PVChargeManagerOptionsFlow(config_entries.OptionsFlow):
    """Configure entity mapping and electrical limits."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage entity mapping and calculation options."""
        if user_input is not None:
            normalized = _normalize_input(user_input)
            errors = _validate_options(normalized)
            if not errors:
                return self.async_create_entry(title="", data=normalized)
        else:
            normalized = dict(self.config_entry.options)
            errors = {}

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(normalized),
            errors=errors,
        )


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the Home Assistant options form schema."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_PV_POWER_SENSORS,
                default=options.get(CONF_PV_POWER_SENSORS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(
                CONF_FORECAST_SENSORS,
                default=options.get(CONF_FORECAST_SENSORS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(
                CONF_HOME_CONSUMPTION_SENSOR,
                default=options.get(CONF_HOME_CONSUMPTION_SENSOR),
            ): _sensor_selector(),
            vol.Optional(
                CONF_GRID_IMPORT_SENSOR,
                default=options.get(CONF_GRID_IMPORT_SENSOR),
            ): _sensor_selector(),
            vol.Optional(
                CONF_GRID_EXPORT_SENSOR,
                default=options.get(CONF_GRID_EXPORT_SENSOR),
            ): _sensor_selector(),
            vol.Optional(
                CONF_BATTERY_CHARGE_POWER_SENSOR,
                default=options.get(CONF_BATTERY_CHARGE_POWER_SENSOR),
            ): _sensor_selector(),
            vol.Optional(
                CONF_BATTERY_SOC_SENSOR,
                default=options.get(CONF_BATTERY_SOC_SENSOR),
            ): _sensor_selector(),
            vol.Required(
                CONF_RESERVE_POWER_W,
                default=options.get(CONF_RESERVE_POWER_W, DEFAULT_RESERVE_POWER_W),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10_000, step=10)),
            vol.Required(
                CONF_FEED_IN_TARIFF_EUR_PER_KWH,
                default=options.get(
                    CONF_FEED_IN_TARIFF_EUR_PER_KWH,
                    DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH,
                ),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=2, step=0.001)),
            vol.Required(
                CONF_VOLTAGE_V,
                default=options.get(CONF_VOLTAGE_V, DEFAULT_VOLTAGE_V),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=100, max=500, step=1)),
            vol.Required(
                CONF_MIN_CURRENT_A,
                default=options.get(CONF_MIN_CURRENT_A, DEFAULT_MIN_CURRENT_A),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=63, step=1)),
            vol.Required(
                CONF_MAX_CURRENT_A,
                default=options.get(CONF_MAX_CURRENT_A, DEFAULT_MAX_CURRENT_A),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=63, step=1)),
            vol.Required(
                CONF_PHASES,
                default=options.get(CONF_PHASES, DEFAULT_PHASES),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=3, step=2)),
            vol.Required(
                CONF_WALLBOX_CONTROL_ENABLED,
                default=options.get(CONF_WALLBOX_CONTROL_ENABLED, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_WALLBOX_CHARGING_SWITCH,
                default=options.get(CONF_WALLBOX_CHARGING_SWITCH),
            ): _switch_selector(),
            vol.Optional(
                CONF_WALLBOX_CURRENT_NUMBER,
                default=options.get(CONF_WALLBOX_CURRENT_NUMBER),
            ): _number_entity_selector(),
            vol.Optional(
                CONF_WALLBOX_CONNECTED_SENSOR,
                default=options.get(CONF_WALLBOX_CONNECTED_SENSOR),
            ): _binary_sensor_selector(),
            vol.Optional(
                CONF_WALLBOX_CHARGING_POWER_SENSOR,
                default=options.get(CONF_WALLBOX_CHARGING_POWER_SENSOR),
            ): _sensor_selector(),
            vol.Optional(
                CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR,
                default=options.get(CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR),
            ): _binary_sensor_selector(),
            vol.Required(
                CONF_WALLBOX_START_DELAY_S,
                default=options.get(CONF_WALLBOX_START_DELAY_S, DEFAULT_WALLBOX_START_DELAY_S),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=3600, step=10)),
            vol.Required(
                CONF_WALLBOX_STOP_DELAY_S,
                default=options.get(CONF_WALLBOX_STOP_DELAY_S, DEFAULT_WALLBOX_STOP_DELAY_S),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=3600, step=10)),
            vol.Required(
                CONF_WALLBOX_MIN_RUNTIME_S,
                default=options.get(CONF_WALLBOX_MIN_RUNTIME_S, DEFAULT_WALLBOX_MIN_RUNTIME_S),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=86_400, step=60)),
        }
    )


def _sensor_selector() -> selector.EntitySelector:
    """Return a selector for one numeric Home Assistant sensor."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _switch_selector() -> selector.EntitySelector:
    """Return a selector for the wallbox charging switch."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))


def _number_entity_selector() -> selector.EntitySelector:
    """Return a selector for the wallbox current number entity."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="number"))


def _binary_sensor_selector() -> selector.EntitySelector:
    """Return a selector for a wallbox binary sensor."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor"))


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector output before it is stored in the config entry."""
    normalized = dict(user_input)
    for key in (CONF_PV_POWER_SENSORS, CONF_FORECAST_SENSORS):
        value = normalized.get(key, [])
        if isinstance(value, str):
            value = [value]
        normalized[key] = [entity_id for entity_id in value if entity_id]

    for key in (
        CONF_HOME_CONSUMPTION_SENSOR,
        CONF_GRID_IMPORT_SENSOR,
        CONF_GRID_EXPORT_SENSOR,
        CONF_BATTERY_CHARGE_POWER_SENSOR,
        CONF_BATTERY_SOC_SENSOR,
        CONF_WALLBOX_CHARGING_SWITCH,
        CONF_WALLBOX_CURRENT_NUMBER,
        CONF_WALLBOX_CONNECTED_SENSOR,
        CONF_WALLBOX_CHARGING_POWER_SENSOR,
        CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR,
    ):
        if not normalized.get(key):
            normalized[key] = None

    return normalized


def _validate_options(options: dict[str, Any]) -> dict[str, str]:
    """Return user-facing validation errors for unsafe electrical limits."""
    if options[CONF_MAX_CURRENT_A] < options[CONF_MIN_CURRENT_A]:
        return {"base": "max_current_below_minimum"}
    if options[CONF_PHASES] not in {1, 3}:
        return {"base": "invalid_phases"}
    if options.get(CONF_WALLBOX_CONTROL_ENABLED) and any(
        not options.get(key)
        for key in (
            CONF_WALLBOX_CHARGING_SWITCH,
            CONF_WALLBOX_CURRENT_NUMBER,
            CONF_WALLBOX_CONNECTED_SENSOR,
        )
    ):
        return {"base": "wallbox_control_requires_entities"}
    return {}
