"""Step draft for the configuration menu. No Home Assistant import."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .backup import ImportResult, default_settings, export_document, import_document
from .probe import EntitySample, ProbeHit, blocks_step, probe_entity

STEPS = ("site", "pv", "battery", "forecast", "wallbox", "vehicle", "review")

ENTITY_KEYS = (
    "grid_import_sensor",
    "grid_export_sensor",
    "home_consumption_sensor",
    "pv_power_sensors",
    "forecast_sensors",
    "battery_soc_sensor",
    "battery_charge_power_sensor",
    "price_sensor",
    "wallbox_charging_switch",
    "wallbox_current_number",
    "wallbox_connected_sensor",
    "wallbox_charging_power_sensor",
    "wallbox_manual_override_sensor",
    "vehicle_soc_sensor",
)
LIST_KEYS = {"pv_power_sensors", "forecast_sensors"}
ELECTRICAL_KEYS = (
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
)
VEHICLE_KEYS = (
    "name",
    "capacity_kwh",
    "target_soc_percent",
    "charging_efficiency",
    "maximum_current_a",
    "departure",
)
BINARY_KEYS = {
    "wallbox_charging_switch",
    "wallbox_connected_sensor",
    "wallbox_manual_override_sensor",
}
STEP_FIELDS: dict[str, tuple[str, ...]] = {
    "site": (
        "grid_import_sensor",
        "grid_export_sensor",
        "home_consumption_sensor",
        "reserve_power_w",
    ),
    "pv": ("pv_power_sensors", "feed_in_tariff_eur_per_kwh"),
    "battery": (
        "battery_soc_sensor",
        "battery_charge_power_sensor",
        "priority_soc",
        "buffer_soc",
        "reserve_soc",
        "battery_capacity_kwh",
        "max_soc",
    ),
    "forecast": (
        "forecast_sensors",
        "price_sensor",
        "strategy",
        "mode",
        "always_charge",
        "solar_share",
        "price_limit_eur",
    ),
    "wallbox": (
        "wallbox_charging_switch",
        "wallbox_current_number",
        "wallbox_connected_sensor",
        "wallbox_charging_power_sensor",
        "wallbox_manual_override_sensor",
        "voltage_v",
        "min_current_a",
        "max_current_a",
        "phases",
        "wallbox_control_enabled",
        "wallbox_start_delay_s",
        "wallbox_stop_delay_s",
        "wallbox_minimum_runtime_s",
    ),
    "vehicle": ("vehicle_soc_sensor", *VEHICLE_KEYS),
    "review": (),
}
OPTION_KEYS = (
    "pv_power_sensors",
    "forecast_sensors",
    "home_consumption_sensor",
    "grid_import_sensor",
    "grid_export_sensor",
    "battery_charge_power_sensor",
    "battery_soc_sensor",
    "price_sensor",
    "vehicle_soc_sensor",
    *ELECTRICAL_KEYS,
    "wallbox_charging_switch",
    "wallbox_current_number",
    "wallbox_connected_sensor",
    "wallbox_charging_power_sensor",
    "wallbox_manual_override_sensor",
)
_WALLBOX_REQUIRED = (
    "wallbox_charging_switch",
    "wallbox_current_number",
    "wallbox_connected_sensor",
)
_LABELS = {
    "de": {
        "loaded": "geladen",
        "missing": "fehlt",
        "stale": "veraltet",
        "invalid": "ungültig",
        "optional_empty": "optional leer",
    },
    "en": {
        "loaded": "loaded",
        "missing": "missing",
        "stale": "stale",
        "invalid": "invalid",
        "optional_empty": "optional empty",
    },
}


def next_step(step: str) -> str | None:
    """Return the following menu step."""
    index = STEPS.index(step)
    if index + 1 >= len(STEPS):
        return None
    return STEPS[index + 1]


def previous_step(step: str) -> str | None:
    """Return the previous menu step."""
    index = STEPS.index(step)
    if index == 0:
        return None
    return STEPS[index - 1]


@dataclass
class SetupDraft:
    """Mutable configuration draft shared by every menu step."""

    settings: dict[str, Any] = field(default_factory=default_settings)
    plans: list[dict[str, Any]] = field(default_factory=list)
    entity_map: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)
    step: str = "site"
    probe: list[ProbeHit] = field(default_factory=list)

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> SetupDraft:
        """Seed a draft from the flat options the coordinator already stores."""
        draft = cls()
        for key in ENTITY_KEYS:
            if key not in options:
                continue
            if key in LIST_KEYS:
                draft.entity_map[key] = _clean_entity(key, options.get(key))
            else:
                draft.entity_map[key] = options.get(key) or None
        for key in ELECTRICAL_KEYS:
            if key in options and options[key] is not None:
                draft.settings[key] = options[key]
        return draft

    def apply(self, step: str, fields: dict[str, Any]) -> list[str]:
        """Merge one step into the draft. Invalid limits are not stored."""
        if step not in STEPS:
            return ["invalid_step"]
        errors = _field_errors(fields, self.settings) if step == "wallbox" else []
        if errors:
            return errors
        vehicle = dict(self.settings.get("vehicle") or {})
        for key in STEP_FIELDS[step]:
            if key not in fields:
                continue
            value = fields[key]
            if key in VEHICLE_KEYS:
                vehicle[key] = value
            elif key in ENTITY_KEYS:
                self.entity_map[key] = _clean_entity(key, value)
            else:
                self.settings[key] = value
        if any(key in fields for key in VEHICLE_KEYS):
            self.settings["vehicle"] = vehicle
            if "departure" in fields:
                self.plans = [{"departure": fields["departure"]}] if fields["departure"] else []
        self.step = step
        return []

    def required_ids(self, step: str) -> set[str]:
        """Entity ids that must be usable before the step continues."""
        ids: set[str] = set()
        if step == "site":
            ids.update(_one(self.entity_map.get("grid_import_sensor")))
            ids.update(_one(self.entity_map.get("grid_export_sensor")))
        elif step == "pv":
            ids.update(self.entity_map.get("pv_power_sensors") or [])
        elif step == "battery":
            ids.update(_one(self.entity_map.get("battery_soc_sensor")))
        elif step == "wallbox" and self.settings.get("wallbox_control_enabled"):
            for key in _WALLBOX_REQUIRED:
                ids.update(_one(self.entity_map.get(key)))
        elif step == "review":
            for name in STEPS:
                if name != "review":
                    ids.update(self.required_ids(name))
        return {entity_id for entity_id in ids if entity_id}

    def missing_mappings(self, step: str) -> list[str]:
        """Required fields that are still empty. Stale entities are not included."""
        if step == "review":
            missing: list[str] = []
            for name in STEPS:
                if name != "review":
                    missing.extend(self.missing_mappings(name))
            return missing
        missing = []
        if step == "site":
            if not self.entity_map.get("grid_import_sensor"):
                missing.append("grid_import_sensor")
            if not self.entity_map.get("grid_export_sensor"):
                missing.append("grid_export_sensor")
        elif step == "pv" and not self.entity_map.get("pv_power_sensors"):
            missing.append("pv_power_sensors")
        elif step == "battery" and not self.entity_map.get("battery_soc_sensor"):
            missing.append("battery_soc_sensor")
        elif step == "wallbox" and self.settings.get("wallbox_control_enabled"):
            missing.extend(key for key in _WALLBOX_REQUIRED if not self.entity_map.get(key))
        return missing

    def record_probe(self, samples: list[EntitySample]) -> list[ProbeHit]:
        """Store the latest read-only probe for this draft."""
        self.probe = [probe_entity(sample) for sample in samples]
        return self.probe

    def continuation_error(self, step: str) -> str | None:
        """Return a form error when the step must not continue."""
        if (
            step == "wallbox"
            and self.settings.get("wallbox_control_enabled")
            and any(not self.entity_map.get(key) for key in _WALLBOX_REQUIRED)
        ):
            return "wallbox_control_requires_entities"
        if self.missing_mappings(step) or blocks_step(self.probe, self.required_ids(step)):
            return "required_missing"
        return None

    def load_json(self, payload: dict[str, Any]) -> ImportResult:
        """Replace the draft. Unknown entity ids are kept for the next probe."""
        result = import_document(payload)
        self.settings = result.settings
        self.plans = list(result.plans)
        self.entity_map = dict(result.entity_map)
        self.learning = dict(result.learning)
        self.step = result.step if result.step in STEPS else "site"
        self.probe = []
        return result

    def save_json(self) -> dict[str, Any]:
        """Export the current draft, including an unfinished step."""
        return export_document(
            self.settings,
            self.step,
            plans=self.plans,
            entity_map=self.entity_map,
            learning=self.learning,
        )

    def options_payload(self) -> dict[str, Any]:
        """Flat options the coordinator already understands. Plans stay in the store."""
        payload: dict[str, Any] = {}
        for key in OPTION_KEYS:
            if key in LIST_KEYS:
                payload[key] = list(self.entity_map.get(key) or [])
            elif key in ENTITY_KEYS:
                payload[key] = self.entity_map.get(key) or None
            elif key in self.settings:
                payload[key] = self.settings[key]
        return payload

    def mapped_ids(self, step: str) -> list[tuple[str, str, bool]]:
        """Entity id, kind and required flag for the entities visible on this step."""
        if step == "review":
            rows: list[tuple[str, str, bool]] = []
            seen: set[str] = set()
            for name in STEPS:
                if name == "review":
                    continue
                for row in self._rows(name):
                    if row[0] not in seen:
                        seen.add(row[0])
                        rows.append(row)
            return rows
        return self._rows(step)

    def _rows(self, step: str) -> list[tuple[str, str, bool]]:
        required = self.required_ids(step)
        rows: list[tuple[str, str, bool]] = []
        for key in STEP_FIELDS[step]:
            if key not in ENTITY_KEYS:
                continue
            kind = "binary" if key in BINARY_KEYS else "number"
            values = self.entity_map.get(key) or []
            if not isinstance(values, list):
                values = [values]
            for entity_id in values:
                if entity_id:
                    rows.append((str(entity_id), kind, str(entity_id) in required))
        return rows


def format_probe(hits: list[ProbeHit], language: str = "de") -> str:
    """Render probe hints. German uses the everyday status words."""
    labels = _LABELS.get(language, _LABELS["en"])
    if not hits:
        return "-"
    return "\n".join(
        f"{hit.entity_id}: {labels.get(hit.status, hit.status)} | {hit.raw} -> {hit.normalized}"
        for hit in hits
    )


def _field_errors(fields: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    phases = fields.get("phases", settings.get("phases", 3))
    if phases not in {1, 3}:
        return ["invalid_phases"]
    minimum = fields.get("min_current_a", settings.get("min_current_a"))
    maximum = fields.get("max_current_a", settings.get("max_current_a"))
    try:
        if minimum is not None and maximum is not None and float(maximum) < float(minimum):
            return ["max_current_below_minimum"]
    except (TypeError, ValueError):
        return ["max_current_below_minimum"]
    return []


def _clean_entity(key: str, value: Any) -> Any:
    if key in LIST_KEYS:
        if isinstance(value, str):
            value = [value]
        return [item for item in (value or []) if item]
    return value or None


def _one(value: Any) -> set[str]:
    if not value:
        return set()
    return {str(value)}
