"""Config and options flow for PV Charge Manager."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .backup import UnsupportedSchema
from .const import (
    CONF_NAME,
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
from .probe import EntitySample
from .setup_draft import STEPS, SetupDraft, format_probe, next_step, previous_step


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
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=DEFAULT_NAME): str}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return PVChargeManagerOptionsFlow()


class PVChargeManagerOptionsFlow(config_entries.OptionsFlow):
    """Step through site, PV, battery, forecast, wallbox, vehicle and review."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Open the draft on the saved step."""
        step = self._draft().step if self._draft().step in STEPS else "site"
        return await getattr(self, f"async_step_{step}")()

    async def async_step_site(self, user_input: dict[str, Any] | None = None):
        """Map grid and home consumption."""
        return await self._handle("site", user_input)

    async def async_step_pv(self, user_input: dict[str, Any] | None = None):
        """Map PV power."""
        return await self._handle("pv", user_input)

    async def async_step_battery(self, user_input: dict[str, Any] | None = None):
        """Map the home battery and its limits."""
        return await self._handle("battery", user_input)

    async def async_step_forecast(self, user_input: dict[str, Any] | None = None):
        """Map forecast and price, and choose the strategy."""
        return await self._handle("forecast", user_input)

    async def async_step_wallbox(self, user_input: dict[str, Any] | None = None):
        """Map the wallbox. Control stays off unless the user enables it."""
        return await self._handle("wallbox", user_input)

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None):
        """Store the single vehicle profile."""
        return await self._handle("vehicle", user_input)

    async def async_step_review(self, user_input: dict[str, Any] | None = None):
        """Show the probe summary and save options plus the store."""
        return await self._handle("review", user_input)

    def _draft(self) -> SetupDraft:
        draft = getattr(self, "_setup_draft", None)
        if draft is None:
            draft = SetupDraft.from_options(dict(self.config_entry.options))
            item = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
            store = item.get("store") if isinstance(item, dict) else None
            if store is not None:
                _merge_store(draft, store.runtime.state)
            self._setup_draft = draft
        return draft

    async def _handle(self, step: str, user_input: dict[str, Any] | None):
        draft = self._draft()
        errors: dict[str, str] = {}
        if user_input is not None:
            raw_json = user_input.get("load_json") or ""
            if isinstance(raw_json, str) and raw_json.strip():
                try:
                    draft.load_json(json.loads(raw_json))
                except json.JSONDecodeError:
                    errors["base"] = "invalid_backup"
                except UnsupportedSchema:
                    errors["base"] = "unsupported_schema"
                except (TypeError, ValueError):
                    errors["base"] = "invalid_backup"
                else:
                    target = draft.step if draft.step in STEPS else "site"
                    draft.step = target
                    await self._save_store()
                    return await getattr(self, f"async_step_{target}")()
            elif user_input.get("go_back"):
                field_errors = draft.apply(step, _fields(step, user_input))
                if field_errors:
                    errors["base"] = field_errors[0]
                else:
                    draft.step = previous_step(step) or step
                    await self._save_store()
                    return await getattr(self, f"async_step_{draft.step}")()
            else:
                field_errors = draft.apply(step, _fields(step, user_input))
                if field_errors:
                    errors["base"] = field_errors[0]
                else:
                    self._record_probe(step)
                    continuation = None if step == "review" else draft.continuation_error(step)
                    if continuation:
                        errors["base"] = continuation
                        await self._save_store()
                    elif step == "review":
                        draft.step = "review"
                        await self._save_store()
                        return self.async_create_entry(title="", data=draft.options_payload())
                    else:
                        draft.step = next_step(step) or step
                        await self._save_store()
                        return await getattr(self, f"async_step_{draft.step}")()
        self._record_probe(step)
        return self.async_show_form(
            step_id=step,
            data_schema=_schema(step, draft),
            errors=errors,
            description_placeholders={
                "probe": format_probe(draft.probe, _language(self.hass)),
                "save_json": json.dumps(draft.save_json(), ensure_ascii=False, indent=2),
            },
        )

    def _record_probe(self, step: str) -> None:
        now = datetime.now(UTC)
        samples: list[EntitySample] = []
        for entity_id, kind, required in self._draft().mapped_ids(step):
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {"unknown", "unavailable"}:
                samples.append(
                    EntitySample(
                        entity_id,
                        False,
                        None if state is None else str(state.state),
                        None,
                        False,
                        required,
                        "kein Wert" if state is None else str(state.state),
                        "kein Wert",
                        kind,
                    )
                )
                continue
            numeric, normalized = _normalize_state(state)
            samples.append(
                EntitySample(
                    entity_id,
                    True,
                    str(state.state),
                    _age_seconds(state, now),
                    numeric,
                    required,
                    str(state.state),
                    normalized,
                    kind,
                )
            )
        self._draft().record_probe(samples)

    async def _save_store(self) -> None:
        from .storage import HomeAssistantStore

        draft = self._draft()
        bucket = self.hass.data.setdefault(DOMAIN, {})
        item = bucket.get(self.config_entry.entry_id)
        store = item.get("store") if isinstance(item, dict) else None
        if store is None:
            store = HomeAssistantStore(self.hass, self.config_entry.entry_id)
            await store.async_load()
            if isinstance(item, dict):
                item["store"] = store
        store.runtime.state.settings = dict(draft.settings)
        store.runtime.state.plans = list(draft.plans)
        store.runtime.state.entity_map = dict(draft.entity_map)
        store.runtime.state.learning = dict(draft.learning)
        store.runtime.state.step = draft.step
        await store.async_save()


def _merge_store(draft: SetupDraft, state: Any) -> None:
    """Overlay vehicle, plan and learning. Entity ids stay with the live options."""
    for key, value in dict(state.settings).items():
        if key not in ELECTRICAL_OVERLAY or key not in draft.settings:
            draft.settings[key] = value
    if state.plans:
        draft.plans = list(state.plans)
    if state.learning:
        draft.learning = dict(state.learning)
    if state.step in STEPS:
        draft.step = state.step


ELECTRICAL_OVERLAY = {
    "reserve_power_w",
    "feed_in_tariff_eur_per_kwh",
    "voltage_v",
    "min_current_a",
    "max_current_a",
    "phases",
    "wallbox_control_enabled",
    "wallbox_start_delay_s",
    "wallbox_stop_delay_s",
    "wallbox_minimum_runtime_s",
}


def _fields(step: str, user_input: dict[str, Any]) -> dict[str, Any]:
    from .setup_draft import ENTITY_KEYS, LIST_KEYS, STEP_FIELDS

    fields: dict[str, Any] = {}
    for key in STEP_FIELDS[step]:
        if key in user_input:
            fields[key] = user_input[key]
        elif key in ENTITY_KEYS:
            fields[key] = [] if key in LIST_KEYS else None
    return fields


def _schema(step: str, draft: SetupDraft) -> vol.Schema:
    entity_map = draft.entity_map
    settings = draft.settings
    vehicle = dict(settings.get("vehicle") or {})
    fields: dict[Any, Any] = {}
    if step == "site":
        fields.update(
            {
                vol.Optional(
                    "grid_import_sensor",
                    default=entity_map.get("grid_import_sensor"),
                ): _sensor_selector(),
                vol.Optional(
                    "grid_export_sensor",
                    default=entity_map.get("grid_export_sensor"),
                ): _sensor_selector(),
                vol.Optional(
                    "home_consumption_sensor",
                    default=entity_map.get("home_consumption_sensor"),
                ): _sensor_selector(),
                vol.Required(
                    "reserve_power_w",
                    default=settings.get("reserve_power_w", DEFAULT_RESERVE_POWER_W),
                ): _number(0, 10_000, 10),
            }
        )
    elif step == "pv":
        fields.update(
            {
                vol.Optional(
                    "pv_power_sensors",
                    default=list(entity_map.get("pv_power_sensors") or []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Required(
                    "feed_in_tariff_eur_per_kwh",
                    default=settings.get(
                        "feed_in_tariff_eur_per_kwh", DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH
                    ),
                ): _number(0, 2, 0.001),
            }
        )
    elif step == "battery":
        fields.update(
            {
                vol.Optional(
                    "battery_soc_sensor",
                    default=entity_map.get("battery_soc_sensor"),
                ): _sensor_selector(),
                vol.Optional(
                    "battery_charge_power_sensor",
                    default=entity_map.get("battery_charge_power_sensor"),
                ): _sensor_selector(),
                vol.Required("priority_soc", default=settings.get("priority_soc", 70)): _number(
                    0, 100, 1
                ),
                vol.Required("buffer_soc", default=settings.get("buffer_soc", 40)): _number(
                    0, 100, 1
                ),
                vol.Required("reserve_soc", default=settings.get("reserve_soc", 20)): _number(
                    0, 100, 1
                ),
                vol.Required(
                    "battery_capacity_kwh",
                    default=settings.get("battery_capacity_kwh", 10),
                ): _number(0, 200, 0.1),
                vol.Required("max_soc", default=settings.get("max_soc", 100)): _number(0, 100, 1),
            }
        )
    elif step == "forecast":
        fields.update(
            {
                vol.Optional(
                    "forecast_sensors",
                    default=list(entity_map.get("forecast_sensors") or []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional("price_sensor", default=entity_map.get("price_sensor")): (
                    _sensor_selector()
                ),
                vol.Required("strategy", default=settings.get("strategy", "forecast")): (
                    _choice(["forecast", "forecast_price"])
                ),
                vol.Required("mode", default=settings.get("mode", "smart")): (
                    _choice(["off", "smart", "now"])
                ),
                vol.Required("always_charge", default=bool(settings.get("always_charge", False))): (
                    selector.BooleanSelector()
                ),
                vol.Required("solar_share", default=settings.get("solar_share", 100)): _number(
                    0, 100, 5
                ),
                vol.Required("price_limit_eur", default=settings.get("price_limit_eur", 0.12)): (
                    _number(0, 2, 0.01)
                ),
            }
        )
    elif step == "wallbox":
        fields.update(
            {
                vol.Optional(
                    "wallbox_charging_switch",
                    default=entity_map.get("wallbox_charging_switch"),
                ): _switch_selector(),
                vol.Optional(
                    "wallbox_current_number",
                    default=entity_map.get("wallbox_current_number"),
                ): _number_entity_selector(),
                vol.Optional(
                    "wallbox_connected_sensor",
                    default=entity_map.get("wallbox_connected_sensor"),
                ): _binary_sensor_selector(),
                vol.Optional(
                    "wallbox_charging_power_sensor",
                    default=entity_map.get("wallbox_charging_power_sensor"),
                ): _sensor_selector(),
                vol.Optional(
                    "wallbox_manual_override_sensor",
                    default=entity_map.get("wallbox_manual_override_sensor"),
                ): _binary_sensor_selector(),
                vol.Required(
                    "voltage_v", default=settings.get("voltage_v", DEFAULT_VOLTAGE_V)
                ): _number(100, 500, 1),
                vol.Required(
                    "min_current_a",
                    default=settings.get("min_current_a", DEFAULT_MIN_CURRENT_A),
                ): _number(1, 63, 1),
                vol.Required(
                    "max_current_a",
                    default=settings.get("max_current_a", DEFAULT_MAX_CURRENT_A),
                ): _number(1, 63, 1),
                vol.Required("phases", default=settings.get("phases", DEFAULT_PHASES)): _number(
                    1, 3, 2
                ),
                vol.Required(
                    "wallbox_control_enabled",
                    default=bool(settings.get("wallbox_control_enabled", False)),
                ): selector.BooleanSelector(),
                vol.Required(
                    "wallbox_start_delay_s",
                    default=settings.get("wallbox_start_delay_s", DEFAULT_WALLBOX_START_DELAY_S),
                ): _number(0, 3600, 10),
                vol.Required(
                    "wallbox_stop_delay_s",
                    default=settings.get("wallbox_stop_delay_s", DEFAULT_WALLBOX_STOP_DELAY_S),
                ): _number(0, 3600, 10),
                vol.Required(
                    "wallbox_minimum_runtime_s",
                    default=settings.get(
                        "wallbox_minimum_runtime_s", DEFAULT_WALLBOX_MIN_RUNTIME_S
                    ),
                ): _number(0, 86_400, 60),
            }
        )
    elif step == "vehicle":
        fields.update(
            {
                vol.Optional(
                    "vehicle_soc_sensor",
                    default=entity_map.get("vehicle_soc_sensor"),
                ): _sensor_selector(),
                vol.Required("name", default=vehicle.get("name", "Auto")): selector.TextSelector(),
                vol.Required("capacity_kwh", default=vehicle.get("capacity_kwh", 60)): _number(
                    1, 200, 0.1
                ),
                vol.Required(
                    "target_soc_percent",
                    default=vehicle.get("target_soc_percent", 80),
                ): _number(1, 100, 1),
                vol.Required(
                    "charging_efficiency",
                    default=vehicle.get("charging_efficiency", 0.9),
                ): _number(0.5, 1, 0.01),
                vol.Required(
                    "maximum_current_a",
                    default=vehicle.get("maximum_current_a", 16),
                ): _number(6, 32, 1),
                vol.Optional("departure", default=vehicle.get("departure", "")): (
                    selector.TextSelector()
                ),
            }
        )
    fields[vol.Optional("load_json", default="")] = selector.TextSelector(
        selector.TextSelectorConfig(multiline=True)
    )
    fields[vol.Optional("go_back", default=False)] = selector.BooleanSelector()
    return vol.Schema(fields)


def _number(minimum: float, maximum: float, step: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=minimum, max=maximum, step=step, mode="box")
    )


def _choice(options: list[str]) -> selector.SelectSelector:
    return selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode="dropdown"))


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


def _language(hass: Any) -> str:
    config = getattr(hass, "config", None)
    language = getattr(config, "language", "en") or "en"
    return language if language in {"de", "en"} else "en"


def _normalize_state(state: Any) -> tuple[bool, str]:
    raw = str(state.state)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return False, raw
    attributes = getattr(state, "attributes", {}) or {}
    unit = str(attributes.get("unit_of_measurement", "")).casefold()
    if unit == "kw":
        value *= 1000
    elif unit == "mw":
        value *= 1_000_000
    return True, str(round(value, 3))


def _age_seconds(state: Any, now: datetime) -> float | None:
    updated = getattr(state, "last_updated", None)
    if updated is None:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return (now - updated).total_seconds()
