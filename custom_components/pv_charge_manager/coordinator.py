"""Coordinator for PV Charge Manager runtime state."""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from logging import Logger
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .allocation import PvSource, allocate_power_by_tariff, allocated_opportunity_cost_eur_per_hour
from .calculation import ChargeLimits, PowerSnapshot, recommend_current
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
    DEFAULT_PHASES,
    DEFAULT_RESERVE_POWER_W,
    DEFAULT_VOLTAGE_V,
    DEFAULT_WALLBOX_MIN_RUNTIME_S,
    DEFAULT_WALLBOX_START_DELAY_S,
    DEFAULT_WALLBOX_STOP_DELAY_S,
    DOMAIN,
)
from .day_preview import build_day_preview, parse_departure, parse_number_series, sum_series
from .wallbox import (
    WallboxAction,
    WallboxControlConfig,
    WallboxController,
    WallboxDecision,
    WallboxState,
)


class PVChargeManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read configured Home Assistant entities and calculate recommendations."""

    def __init__(self, hass, logger: Logger, entry) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self._logger = logger
        self._wallbox_controller: WallboxController | None = None
        self._wallbox_config_error: str | None = None
        try:
            self._wallbox_controller = WallboxController(_wallbox_config(entry.options))
        except ValueError as err:
            self._wallbox_config_error = str(err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch states and return a conservative calculation snapshot."""
        options = self.entry.options
        warnings: list[str] = []
        pv_power_values: list[tuple[str, float]] = []
        pv_entity_ids = list(options.get(CONF_PV_POWER_SENSORS, []))

        if not pv_entity_ids:
            warnings.append("no_pv_power_sensor_configured")
        for entity_id in pv_entity_ids:
            value = _read_power(self.hass, entity_id, warnings)
            if value is None:
                continue
            pv_power_values.append((entity_id, value))

        if pv_entity_ids and len(pv_power_values) != len(pv_entity_ids):
            warnings.append("pv_power_sensor_unavailable")

        pv_power_w = sum(value for _, value in pv_power_values) if pv_power_values else None
        battery_entity_id = options.get(CONF_BATTERY_CHARGE_POWER_SENSOR)
        battery_reading_w = self._read_optional_power(battery_entity_id, warnings)

        if battery_reading_w is None and battery_entity_id:
            warnings.append("battery_charge_power_sensor_unavailable")
        battery_input_valid = not battery_entity_id or battery_reading_w is not None
        battery_charge_power_w = battery_reading_w if battery_reading_w is not None else 0.0
        home_consumption_w = self._read_home_consumption(
            options,
            warnings,
            pv_power_w or 0.0,
            battery_charge_power_w,
        )

        pv_inputs_valid = bool(pv_entity_ids) and len(pv_power_values) == len(pv_entity_ids)
        available = (
            pv_power_w is not None
            and home_consumption_w is not None
            and pv_inputs_valid
            and battery_input_valid
        )
        if not available:
            warnings.append("required_power_input_unavailable")

        result: dict[str, Any] = {
            "available": available,
            "pv_power_w": _round_or_none(pv_power_w),
            "home_consumption_w": _round_or_none(home_consumption_w),
            "battery_charge_power_w": _round_or_none(battery_charge_power_w),
            "surplus_power_w": None,
            "recommended_current_a": None,
            "recommended_charge_power_w": None,
            "opportunity_cost_eur_per_hour": None,
            "wallbox_action": WallboxAction.HOLD.value,
            "wallbox_reason": "control_disabled",
            "wallbox_target_current_a": None,
            "warnings": sorted(set(warnings)),
            "mapping": {
                "pv_power_sensors": pv_entity_ids,
                "forecast_sensors": list(options.get(CONF_FORECAST_SENSORS, [])),
                "home_consumption_sensor": options.get(CONF_HOME_CONSUMPTION_SENSOR),
                "grid_import_sensor": options.get(CONF_GRID_IMPORT_SENSOR),
                "grid_export_sensor": options.get(CONF_GRID_EXPORT_SENSOR),
                "battery_charge_power_sensor": battery_entity_id,
                "wallbox_control_enabled": bool(options.get(CONF_WALLBOX_CONTROL_ENABLED)),
                "wallbox_charging_switch": options.get(CONF_WALLBOX_CHARGING_SWITCH),
                "wallbox_current_number": options.get(CONF_WALLBOX_CURRENT_NUMBER),
                "wallbox_connected_sensor": options.get(CONF_WALLBOX_CONNECTED_SENSOR),
                "wallbox_charging_power_sensor": options.get(CONF_WALLBOX_CHARGING_POWER_SENSOR),
                "wallbox_manual_override_sensor": options.get(CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR),
            },
        }

        if not available:
            await self._update_wallbox(result, options, warnings)
            return self._finish(result, warnings)

        try:
            limits = ChargeLimits(
                minimum_current_a=float(options.get(CONF_MIN_CURRENT_A, DEFAULT_MIN_CURRENT_A)),
                maximum_current_a=float(options.get(CONF_MAX_CURRENT_A, DEFAULT_MAX_CURRENT_A)),
                phases=int(options.get(CONF_PHASES, DEFAULT_PHASES)),
                voltage_v=float(options.get(CONF_VOLTAGE_V, DEFAULT_VOLTAGE_V)),
            )
            recommendation = recommend_current(
                PowerSnapshot(
                    pv_power_w=pv_power_w,
                    home_consumption_w=home_consumption_w,
                    battery_charge_power_w=battery_charge_power_w,
                    reserve_power_w=float(
                        options.get(CONF_RESERVE_POWER_W, DEFAULT_RESERVE_POWER_W)
                    ),
                ),
                limits,
            )
        except (TypeError, ValueError) as err:
            result["available"] = False
            warnings.append(f"invalid_limits:{err}")
            await self._update_wallbox(result, options, warnings)
            return self._finish(result, warnings)

        result.update(
            {
                "surplus_power_w": round(recommendation.available_power_w, 3),
                "recommended_current_a": recommendation.current_a,
                "recommended_charge_power_w": recommendation.charge_power_w,
                "opportunity_cost_eur_per_hour": _opportunity_cost(
                    pv_power_values,
                    recommendation.charge_power_w,
                    float(
                        options.get(
                            CONF_FEED_IN_TARIFF_EUR_PER_KWH,
                            DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH,
                        )
                    ),
                ),
            }
        )
        await self._update_wallbox(result, options, warnings)
        return self._finish(result, warnings)

    async def _update_wallbox(
        self,
        result: dict[str, Any],
        options: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """Evaluate and, when explicitly enabled, apply one wallbox action."""
        if not options.get(CONF_WALLBOX_CONTROL_ENABLED):
            return
        if self._wallbox_controller is None:
            warnings.append(f"invalid_wallbox_config:{self._wallbox_config_error}")
            result["wallbox_reason"] = "invalid_wallbox_config"
            return

        required_entities = (
            CONF_WALLBOX_CHARGING_SWITCH,
            CONF_WALLBOX_CURRENT_NUMBER,
            CONF_WALLBOX_CONNECTED_SENSOR,
        )
        if any(not options.get(key) for key in required_entities):
            warnings.append("wallbox_control_not_configured")
            result["wallbox_reason"] = "wallbox_control_not_configured"
            return

        wallbox_state = self._read_wallbox_state(result, options, warnings)
        decision = self._wallbox_controller.evaluate(wallbox_state)
        result["wallbox_action"] = decision.action.value
        result["wallbox_reason"] = decision.reason
        result["wallbox_target_current_a"] = decision.target_current_a
        await self._apply_wallbox_decision(decision, wallbox_state.now, options, warnings)

    def _read_wallbox_state(
        self,
        result: dict[str, Any],
        options: dict[str, Any],
        warnings: list[str],
    ) -> WallboxState:
        """Read wallbox state without guessing when an entity is unavailable."""
        connected = _read_binary(self.hass, options.get(CONF_WALLBOX_CONNECTED_SENSOR), warnings)
        switch_entity_id = options.get(CONF_WALLBOX_CHARGING_SWITCH)
        charging_power_entity_id = options.get(CONF_WALLBOX_CHARGING_POWER_SENSOR)
        if charging_power_entity_id:
            charging_power_w = _read_power(self.hass, charging_power_entity_id, warnings)
            charging = None if charging_power_w is None else charging_power_w > 50
        else:
            charging = _read_binary(self.hass, switch_entity_id, warnings)

        manual_override = False
        manual_override_entity_id = options.get(CONF_WALLBOX_MANUAL_OVERRIDE_SENSOR)
        if manual_override_entity_id:
            override_state = _read_binary(self.hass, manual_override_entity_id, warnings)
            manual_override = override_state is None or override_state

        current_a = _read_current(self.hass, options.get(CONF_WALLBOX_CURRENT_NUMBER), warnings)
        return WallboxState(
            now=datetime.now(UTC),
            vehicle_connected=connected,
            charging=charging,
            current_a=current_a,
            inputs_available=bool(result.get("available")),
            recommended_current_a=result.get("recommended_current_a"),
            manual_override=manual_override,
        )

    async def _apply_wallbox_decision(
        self,
        decision: WallboxDecision,
        now: datetime,
        options: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """Apply a decision only after the pure controller has approved it."""
        try:
            if decision.action is WallboxAction.START:
                await self._set_wallbox_current(decision.target_current_a, options)
                await self.hass.services.async_call(
                    "switch",
                    "turn_on",
                    {ATTR_ENTITY_ID: options[CONF_WALLBOX_CHARGING_SWITCH]},
                    blocking=True,
                )
            elif decision.action is WallboxAction.STOP:
                await self.hass.services.async_call(
                    "switch",
                    "turn_off",
                    {ATTR_ENTITY_ID: options[CONF_WALLBOX_CHARGING_SWITCH]},
                    blocking=True,
                )
            elif decision.action is WallboxAction.SET_CURRENT:
                await self._set_wallbox_current(decision.target_current_a, options)
            else:
                return
        except Exception as err:
            warnings.append(f"wallbox_service_call_failed:{type(err).__name__}")
            self._logger.exception("PV Charge Manager wallbox service call failed")
            return

        self._wallbox_controller.acknowledge(decision, now)

    async def _set_wallbox_current(
        self,
        target_current_a: float | None,
        options: dict[str, Any],
    ) -> None:
        """Set the wallbox current before starting or while already charging."""
        if target_current_a is None:
            raise ValueError("wallbox current target is missing")
        await self.hass.services.async_call(
            "number",
            "set_value",
            {
                ATTR_ENTITY_ID: options[CONF_WALLBOX_CURRENT_NUMBER],
                "value": target_current_a,
            },
            blocking=True,
        )

    def _read_home_consumption(
        self,
        options: dict[str, Any],
        warnings: list[str],
        pv_power_w: float,
        battery_charge_power_w: float,
    ) -> float | None:
        """Read direct home consumption or calculate it from grid flow."""
        direct_entity_id = options.get(CONF_HOME_CONSUMPTION_SENSOR)
        if direct_entity_id:
            value = _read_power(self.hass, direct_entity_id, warnings)
            if value is None:
                warnings.append("home_consumption_sensor_unavailable")
            return value

        import_entity_id = options.get(CONF_GRID_IMPORT_SENSOR)
        export_entity_id = options.get(CONF_GRID_EXPORT_SENSOR)
        if not import_entity_id or not export_entity_id:
            warnings.append("no_home_consumption_sensor_or_grid_pair_configured")
            return None

        grid_import_w = _read_power(self.hass, import_entity_id, warnings)
        grid_export_w = _read_power(self.hass, export_entity_id, warnings)
        if grid_import_w is None or grid_export_w is None:
            warnings.append("grid_sensor_unavailable_for_home_fallback")
            return None

        return round(
            max(0.0, pv_power_w + grid_import_w - grid_export_w - battery_charge_power_w),
            3,
        )

    def _finish(self, result: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        """Attach the forecast preview. The wallbox setpoint is left untouched."""
        self._attach_flow(result)
        try:
            self._attach_day_preview(result, warnings)
        except (TypeError, ValueError, OverflowError) as err:
            warnings.append(f"forecast_preview_failed:{err}")
        result["warnings"] = sorted(set(warnings))
        return result

    def _attach_flow(self, result: dict[str, Any]) -> None:
        """Remember live watts for the panel. These values do not change the setpoint."""
        options = self.entry.options
        quiet: list[str] = []
        result["grid_import_w"] = _quiet_power(self.hass, options.get(CONF_GRID_IMPORT_SENSOR))
        result["grid_export_w"] = _quiet_power(self.hass, options.get(CONF_GRID_EXPORT_SENSOR))
        result["wallbox_power_w"] = _quiet_power(
            self.hass, options.get(CONF_WALLBOX_CHARGING_POWER_SENSOR)
        )
        result["battery_soc"] = _read_percent(
            self.hass, options.get(CONF_BATTERY_SOC_SENSOR), quiet
        )

    def _attach_day_preview(self, result: dict[str, Any], warnings: list[str]) -> None:
        """Read forecast entities and store the day preview next to the surplus."""
        options = self.entry.options
        entity_ids = list(options.get(CONF_FORECAST_SENSORS) or [])
        if not entity_ids:
            return
        series: list[list[float]] = []
        for entity_id in entity_ids:
            raw = _read_state_text(self.hass, entity_id, warnings)
            if raw is None:
                continue
            values = parse_number_series(raw)
            if values is None:
                warnings.append(f"invalid_forecast:{entity_id}")
                continue
            scaled = _scale_power(values, _state_unit(self.hass, entity_id))
            if scaled is None:
                warnings.append(f"unexpected_power_unit:{entity_id}")
                continue
            series.append(scaled)
        if not series:
            warnings.append("forecast_unavailable")
            return
        home_w = result.get("home_consumption_w")
        if home_w is None:
            warnings.append("forecast_preview_unavailable")
            return
        battery_soc = _read_percent(self.hass, options.get(CONF_BATTERY_SOC_SENSOR), warnings)
        if battery_soc is None:
            warnings.append("battery_soc_unavailable")
            return
        settings, learning, plans = _stored_state(getattr(self, "runtime_store", None))
        capacity = _optional_float(settings.get("battery_capacity_kwh"))
        if capacity is None or capacity <= 0:
            warnings.append("battery_capacity_missing")
            return
        vehicle_soc, assumption = _vehicle_soc(self.hass, options, settings, warnings)
        try:
            limits = ChargeLimits(
                minimum_current_a=float(options.get(CONF_MIN_CURRENT_A, DEFAULT_MIN_CURRENT_A)),
                maximum_current_a=float(options.get(CONF_MAX_CURRENT_A, DEFAULT_MAX_CURRENT_A)),
                phases=int(options.get(CONF_PHASES, DEFAULT_PHASES)),
                voltage_v=float(options.get(CONF_VOLTAGE_V, DEFAULT_VOLTAGE_V)),
            )
        except (TypeError, ValueError):
            limits = ChargeLimits()
        now = self._now()
        departure = _departure(plans, settings, now)
        preview = build_day_preview(
            forecast_w=sum_series(series),
            home_w=float(home_w),
            now=now,
            battery_soc=battery_soc,
            battery_capacity_kwh=capacity,
            battery_max_charge_w=_optional_float(settings.get("battery_max_charge_w")) or 5000.0,
            battery_efficiency=_optional_float(settings.get("battery_efficiency")) or 0.92,
            priority_soc=_setting_float(settings, "priority_soc", 70.0),
            buffer_soc=_setting_float(settings, "buffer_soc", 40.0),
            max_soc=_setting_float(settings, "max_soc", 100.0),
            reserve_power_w=float(options.get(CONF_RESERVE_POWER_W, DEFAULT_RESERVE_POWER_W)),
            vehicle_soc=vehicle_soc,
            vehicle_capacity_kwh=_vehicle_float(settings, "capacity_kwh"),
            target_soc=_vehicle_float(settings, "target_soc_percent"),
            vehicle_efficiency=_vehicle_float(settings, "charging_efficiency") or 0.9,
            assumption=assumption,
            min_power_w=limits.minimum_power_w,
            max_power_w=limits.maximum_power_w,
            always_charge=bool(settings.get("always_charge")),
            use_price=settings.get("strategy") == "forecast_price",
            prices=_price_series(self.hass, options, warnings),
            learning=learning,
            departure=departure,
            limits=limits,
            mode=_mode(settings),
            solar_share=_setting_float(settings, "solar_share", 100.0),
            cheap_eur=_setting_float(settings, "price_limit_eur", 0.12),
        )
        result.update(preview)

    def _now(self) -> datetime:
        """Use the Home Assistant time zone when it is configured."""
        tzname = getattr(getattr(self.hass, "config", None), "time_zone", None)
        if tzname:
            try:
                return datetime.now(ZoneInfo(str(tzname)))
            except ZoneInfoNotFoundError:
                pass
        return datetime.now(UTC)

    def _read_optional_power(self, entity_id: str | None, warnings: list[str]) -> float | None:
        """Read an optional power entity."""
        if not entity_id:
            return 0.0
        return _read_power(self.hass, entity_id, warnings)


def _mode(settings: dict[str, Any]) -> str:
    mode = settings.get("mode")
    if mode in {"off", "smart", "now"}:
        return str(mode)
    return "smart"


def _setting_float(settings: dict[str, Any], key: str, fallback: float) -> float:
    value = _optional_float(settings.get(key))
    return fallback if value is None else value


def _stored_state(store: Any) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    """Return settings, learning and plans from the runtime store."""
    if store is None:
        return {}, {}, []
    state = store.runtime.state
    return dict(state.settings), dict(state.learning), list(state.plans)


def _vehicle_soc(hass, options: dict[str, Any], settings: dict[str, Any], warnings: list[str]):
    """Return the car SOC. Without a measurement the value stays an assumption."""
    entity_id = options.get("vehicle_soc_sensor")
    measured = _read_percent(hass, entity_id, []) if entity_id else None
    connected = _read_binary(hass, options.get(CONF_WALLBOX_CONNECTED_SENSOR), warnings)
    if measured is None:
        stored = _vehicle_float(settings, "soc")
        return stored if stored is not None else 50.0, True
    return measured, connected is False


def _vehicle_float(settings: dict[str, Any], key: str) -> float | None:
    vehicle = settings.get("vehicle")
    if not isinstance(vehicle, dict):
        return None
    return _optional_float(vehicle.get(key))


def _departure(plans: list[Any], settings: dict[str, Any], now: datetime) -> datetime | None:
    raw = None
    if plans and isinstance(plans[0], dict):
        raw = plans[0].get("departure")
    if raw in {None, ""}:
        raw = _vehicle_value(settings, "departure")
    return parse_departure(raw, now)


def _vehicle_value(settings: dict[str, Any], key: str) -> Any:
    vehicle = settings.get("vehicle")
    if not isinstance(vehicle, dict):
        return None
    return vehicle.get(key)


def _price_series(hass, options: dict[str, Any], warnings: list[str]) -> list[float] | None:
    entity_id = options.get("price_sensor")
    if not entity_id:
        return None
    raw = _read_state_text(hass, entity_id, warnings)
    if raw is None:
        return None
    values = parse_number_series(raw)
    if values is None:
        warnings.append(f"invalid_price:{entity_id}")
    return values


def _read_state_text(hass, entity_id: str, warnings: list[str]) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable", ""}:
        warnings.append(f"unavailable:{entity_id}")
        return None
    return str(state.state)


def _state_unit(hass, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    if state is None:
        return ""
    return str(state.attributes.get("unit_of_measurement", ""))


def _scale_power(values: list[float], unit: str) -> list[float] | None:
    folded = unit.casefold()
    if folded == "kw":
        return [value * 1000 for value in values]
    if folded == "mw":
        return [value * 1_000_000 for value in values]
    if folded not in {"", "w"}:
        return None
    return values


def _read_percent(hass, entity_id: str | None, warnings: list[str]) -> float | None:
    """Read a percentage. Missing entities stay empty instead of becoming zero."""
    if not entity_id:
        return None
    raw = _read_state_text(hass, entity_id, warnings)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        warnings.append(f"non_numeric:{entity_id}")
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        warnings.append(f"invalid_soc:{entity_id}")
        return None
    return value


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _wallbox_config(options: dict[str, Any]) -> WallboxControlConfig:
    """Build validated wallbox control limits from config-entry options."""
    return WallboxControlConfig(
        minimum_current_a=float(options.get(CONF_MIN_CURRENT_A, DEFAULT_MIN_CURRENT_A)),
        maximum_current_a=float(options.get(CONF_MAX_CURRENT_A, DEFAULT_MAX_CURRENT_A)),
        start_delay_s=int(options.get(CONF_WALLBOX_START_DELAY_S, DEFAULT_WALLBOX_START_DELAY_S)),
        stop_delay_s=int(options.get(CONF_WALLBOX_STOP_DELAY_S, DEFAULT_WALLBOX_STOP_DELAY_S)),
        minimum_runtime_s=int(
            options.get(CONF_WALLBOX_MIN_RUNTIME_S, DEFAULT_WALLBOX_MIN_RUNTIME_S)
        ),
    )


def _read_binary(hass, entity_id: str | None, warnings: list[str]) -> bool | None:
    """Read an on/off entity and return None for unavailable state."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        warnings.append(f"unavailable:{entity_id}")
        return None
    if state.state not in {"on", "off"}:
        warnings.append(f"invalid_binary_state:{entity_id}")
        return None
    return state.state == "on"


def _read_current(hass, entity_id: str | None, warnings: list[str]) -> float | None:
    """Read a wallbox current number in amperes."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        warnings.append(f"unavailable:{entity_id}")
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        warnings.append(f"non_numeric:{entity_id}")
        return None
    if not math.isfinite(value) or value < 0:
        warnings.append(f"invalid_current:{entity_id}")
        return None
    unit = str(state.attributes.get("unit_of_measurement", "")).casefold()
    if unit not in {"", "a"}:
        warnings.append(f"unexpected_current_unit:{entity_id}")
        return None
    return value


def _quiet_power(hass, entity_id: str | None) -> float | None:
    """Read a display-only power value without adding a coordinator warning."""
    if not entity_id:
        return None
    return _round_or_none(_read_power(hass, entity_id, []))


def _read_power(hass, entity_id: str, warnings: list[str]) -> float | None:
    """Read a power sensor and normalize W/kW/MW to watts."""
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        warnings.append(f"unavailable:{entity_id}")
        return None

    try:
        value = float(state.state)
    except (TypeError, ValueError):
        warnings.append(f"non_numeric:{entity_id}")
        return None

    if not math.isfinite(value) or value < 0:
        warnings.append(f"invalid_power:{entity_id}")
        return None

    unit = str(state.attributes.get("unit_of_measurement", "")).casefold()
    if unit == "kw":
        value *= 1000
    elif unit == "mw":
        value *= 1_000_000
    elif unit not in {"", "w"}:
        warnings.append(f"unexpected_power_unit:{entity_id}")
        return None

    return value


def _opportunity_cost(
    pv_power_values: Iterable[tuple[str, float]],
    requested_power_w: float,
    feed_in_tariff_eur_per_kwh: float,
) -> float:
    """Calculate the hourly feed-in revenue sacrificed by charging."""
    sources = [
        PvSource(
            name=entity_id,
            available_power_w=value,
            feed_in_tariff_eur_per_kwh=feed_in_tariff_eur_per_kwh,
        )
        for entity_id, value in pv_power_values
    ]
    allocations = allocate_power_by_tariff(sources, requested_power_w)
    return allocated_opportunity_cost_eur_per_hour(allocations)


def _round_or_none(value: float | None) -> float | None:
    """Round an optional numeric value for state and diagnostics output."""
    return None if value is None else round(value, 3)
