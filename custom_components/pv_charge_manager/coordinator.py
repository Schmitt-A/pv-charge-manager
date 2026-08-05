"""Coordinator for PV Charge Manager runtime state."""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import timedelta
from logging import Logger
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .allocation import PvSource, allocate_power_by_tariff, allocated_opportunity_cost_eur_per_hour
from .calculation import ChargeLimits, PowerSnapshot, recommend_current
from .const import (
    CONF_BATTERY_CHARGE_POWER_SENSOR,
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
    DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH,
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_MIN_CURRENT_A,
    DEFAULT_PHASES,
    DEFAULT_RESERVE_POWER_W,
    DEFAULT_VOLTAGE_V,
    DOMAIN,
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
            "warnings": sorted(set(warnings)),
            "mapping": {
                "pv_power_sensors": pv_entity_ids,
                "forecast_sensors": list(options.get(CONF_FORECAST_SENSORS, [])),
                "home_consumption_sensor": options.get(CONF_HOME_CONSUMPTION_SENSOR),
                "grid_import_sensor": options.get(CONF_GRID_IMPORT_SENSOR),
                "grid_export_sensor": options.get(CONF_GRID_EXPORT_SENSOR),
                "battery_charge_power_sensor": battery_entity_id,
            },
        }

        if not available:
            return result

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
            result["warnings"] = sorted(set(result["warnings"] + [f"invalid_limits:{err}"]))
            return result

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
        return result

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

    def _read_optional_power(self, entity_id: str | None, warnings: list[str]) -> float | None:
        """Read an optional power entity."""
        if not entity_id:
            return 0.0
        return _read_power(self.hass, entity_id, warnings)


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
