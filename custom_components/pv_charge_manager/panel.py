"""Panel snapshot. The browser renders this and does not calculate a plan."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from .controls import (
    NUMBER_SPECS,
    SELECTS,
    RejectedControl,
    read_always_charge,
    read_number,
    read_select,
    write_always_charge,
    write_number,
    write_select,
)
from .probe import EntitySample, probe_entity
from .setup_draft import SetupDraft

_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PROBE_LABELS = {
    "loaded": "geladen",
    "missing": "fehlt",
    "stale": "veraltet",
    "invalid": "ungültig",
    "optional_empty": "optional leer",
}
_MINIMUM = {
    "possible": "Die Mindestleistung wird erreicht.",
    "brief": "Die Mindestleistung kommt nur kurz.",
    "never": "Die Mindestleistung wird nicht erreicht.",
}
_BOOL_TRUE = {"true", "on", "1"}
_BOOL_FALSE = {"false", "off", "0"}


def build_panel_snapshot(
    data: dict[str, Any] | None,
    settings: dict[str, Any] | None,
    *,
    plans: list[dict[str, Any]] | None = None,
    step: str = "site",
    probe: list[dict[str, Any]] | None = None,
    entry_id: str | None = None,
    backup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the view model. Missing measurements stay empty instead of becoming zero."""
    state = data or {}
    stored = settings or {}
    sentence, detail = _sentence(state, stored)
    meta = state.get("preview_meta") if isinstance(state.get("preview_meta"), dict) else {}
    return {
        "entry_id": entry_id,
        "sentence": sentence,
        "detail": detail,
        "plan_status": state.get("plan_status"),
        "assumption": bool(meta.get("assumption")),
        "recommendation": state.get("battery_recommendation"),
        "night_reserve": state.get("night_reserve"),
        "battery_band": _band(
            state.get("battery_full_at_early"), state.get("battery_full_at_late")
        ),
        "vehicle_band": _band(state.get("vehicle_full_at"), state.get("vehicle_full_at")),
        "flow": {
            "pv_w": _optional_number(state.get("pv_power_w")),
            "home_w": _optional_number(state.get("home_consumption_w")),
            "battery_w": _optional_number(state.get("battery_charge_power_w")),
            "battery_soc": _optional_number(state.get("battery_soc")),
            "grid_import_w": _optional_number(state.get("grid_import_w")),
            "grid_export_w": _optional_number(state.get("grid_export_w")),
            "car_w": _optional_number(state.get("wallbox_power_w")),
        },
        "days": [
            {
                "id": "today",
                "title": "Heute",
                "chargeable_kwh": _present_number(state, "chargeable_kwh_today"),
                "hint": _MINIMUM.get(str(state.get("minimum_power_today"))),
            },
            {
                "id": "tomorrow",
                "title": "Morgen",
                "chargeable_kwh": _present_number(state, "chargeable_kwh_tomorrow"),
                "hint": None,
            },
        ],
        "controls": _controls(stored, plans or []),
        "probe": [_probe_row(row) for row in probe or []],
        "warnings": [str(item) for item in state.get("warnings") or []],
        "step": step,
        "wallbox_action": state.get("wallbox_action"),
        "recommended_current_a": _optional_number(state.get("recommended_current_a")),
        "backup": backup,
    }


def apply_panel_control(
    settings: dict[str, Any],
    plans: list[dict[str, Any]],
    key: str,
    value: Any,
) -> None:
    """Store one overview control. A rejected value leaves the plan unchanged."""
    if key == "departure":
        _write_departure(plans, value)
        return
    if key == "always_charge":
        write_always_charge(settings, _as_bool(value))
        return
    if key in SELECTS:
        write_select(settings, key, str(value))
        return
    if key in NUMBER_SPECS:
        write_number(settings, key, value)
        return
    raise RejectedControl(key)


def entity_map_for_probe(stored: dict[str, Any] | None, options: dict[str, Any] | None) -> dict:
    """Fill entity ids that the options already have when the store map is empty."""
    merged = dict(stored or {})
    for key, value in (options or {}).items():
        if merged.get(key) not in (None, "", []):
            continue
        if isinstance(value, (str, list)) and value:
            merged[key] = value
    return merged


def collect_probe(
    entity_map: dict[str, Any],
    settings: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify mapped entities. This does not write to a device."""
    draft = SetupDraft()
    draft.entity_map = dict(entity_map)
    draft.settings = dict(settings)
    hits = []
    for entity_id, kind, required in draft.mapped_ids("review"):
        hits.append(probe_entity(_sample(entity_id, kind, required, states.get(entity_id))))
    return [
        {
            "entity_id": hit.entity_id,
            "status": hit.status,
            "label": _PROBE_LABELS.get(hit.status, hit.status),
            "raw": hit.raw,
            "normalized": hit.normalized,
        }
        for hit in hits
    ]


def _sentence(data: dict[str, Any], settings: dict[str, Any]) -> tuple[str, str]:
    mode = settings.get("mode") or "smart"
    status = data.get("plan_status")
    meta = data.get("preview_meta") if isinstance(data.get("preview_meta"), dict) else {}
    missing = meta.get("vehicle_missing_kwh")
    if status is None and "chargeable_kwh_today" not in data:
        sentence = "Noch kein Plan. Die Prognose fehlt oder ist nicht lesbar."
        detail = "Ohne lesbare Prognose gibt es keine Stunden."
    elif mode == "off" or status == "off":
        sentence = "Laden ist aus. Die Vorschau bleibt sichtbar."
        detail = "Modus Aus"
    elif mode == "now":
        sentence = "Das Auto lädt sofort mit voller Leistung."
        detail = "Modus Sofort"
    elif status == "infeasible" and data.get("minimum_power_today") == "never":
        sentence = "Heute startet die Wallbox nicht. Kein Zeitraum erreicht die Mindestleistung."
        detail = "Mindestleistung nie erreicht"
    elif status == "infeasible":
        if isinstance(missing, int | float) and not isinstance(missing, bool) and missing > 0:
            sentence = (
                f"Heute reicht die Sonne nicht für das Autoziel. Es fehlen {_num(missing)} kWh."
            )
        else:
            sentence = "Heute reicht die Sonne nicht für das Autoziel."
        detail = "Plan nicht machbar"
    elif status == "needs_grid":
        sentence = "Das Autoziel braucht Netzstrom. Die Batterie stützt nur bis zum Puffer."
        detail = "Netz im Plan"
    elif status == "feasible":
        if data.get("vehicle_full_at"):
            sentence = f"Das Auto ist {_band(data.get('vehicle_full_at'), data.get('vehicle_full_at'))} am Ziel."
        else:
            sentence = (
                "Die Batterie ist "
                f"{_band(data.get('battery_full_at_early'), data.get('battery_full_at_late'))} voll."
            )
        detail = "Plan machbar"
    else:
        sentence = "Der Plan wird gerade gerechnet."
        detail = ""
    if (
        meta.get("assumption")
        and status not in {None, "off"}
        and mode != "off"
        and "chargeable_kwh_today" in data
    ):
        detail = f"{detail} Auto-Wert ist eine Annahme.".strip()
    return sentence, detail


def _controls(settings: dict[str, Any], plans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": read_select(settings, "mode"),
        "strategy": read_select(settings, "strategy"),
        "always_charge": read_always_charge(settings),
        "solar_share": read_number(settings, "solar_share"),
        "priority_soc": read_number(settings, "priority_soc"),
        "buffer_soc": read_number(settings, "buffer_soc"),
        "reserve_soc": read_number(settings, "reserve_soc"),
        "price_limit_eur": read_number(settings, "price_limit_eur"),
        "target_soc": read_number(settings, "target_soc"),
        "departure": _read_departure(plans, settings),
    }


def _read_departure(plans: list[dict[str, Any]], settings: dict[str, Any]) -> str:
    if plans and isinstance(plans[0], dict) and plans[0].get("departure"):
        return str(plans[0]["departure"])
    vehicle = settings.get("vehicle")
    if isinstance(vehicle, dict) and vehicle.get("departure"):
        return str(vehicle["departure"])
    return ""


def _write_departure(plans: list[dict[str, Any]], value: Any) -> None:
    text = "" if value is None else str(value).strip()
    if text == "":
        if plans and isinstance(plans[0], dict):
            plans[0].pop("departure", None)
            if not plans[0]:
                plans.pop(0)
        return
    if not _valid_departure(text):
        raise RejectedControl("departure")
    if plans and isinstance(plans[0], dict):
        plans[0]["departure"] = text
        return
    plans.clear()
    plans.append({"departure": text})


def _valid_departure(text: str) -> bool:
    if _CLOCK.match(text):
        return True
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str) and value.lower() in _BOOL_TRUE | _BOOL_FALSE:
        return value.lower() in _BOOL_TRUE
    raise RejectedControl("always_charge")


def _sample(
    entity_id: str,
    kind: str,
    required: bool,
    state: dict[str, Any] | None,
) -> EntitySample:
    if state is None:
        return EntitySample(entity_id, False, None, None, False, required, "-", "-", kind)
    raw = str(state.get("state", ""))
    age = state.get("age_s")
    age_s = float(age) if isinstance(age, int | float) and not isinstance(age, bool) else None
    if kind == "binary":
        return EntitySample(
            entity_id,
            True,
            raw,
            age_s,
            False,
            required,
            raw,
            raw if raw in {"on", "off"} else "",
            kind,
        )
    try:
        number = float(raw)
        numeric = math.isfinite(number)
    except (TypeError, ValueError):
        numeric = False
    return EntitySample(
        entity_id, True, raw, age_s, numeric, required, raw, raw if numeric else "", kind
    )


def _probe_row(row: dict[str, Any]) -> dict[str, str]:
    status = str(row.get("status") or "")
    return {
        "entity_id": str(row.get("entity_id") or ""),
        "status": status,
        "label": str(row.get("label") or _PROBE_LABELS.get(status, status)),
        "raw": str(row.get("raw") or ""),
        "normalized": str(row.get("normalized") or ""),
    }


def _band(early: Any, late: Any) -> str:
    start = _hhmm(early)
    end = _hhmm(late)
    if start and end:
        return f"gegen {start}" if start == end else f"zwischen {start} und {end}"
    if start:
        return f"frühestens {start}"
    if end:
        return f"spätestens {end}"
    return "an diesem Tag nicht"


def _hhmm(value: Any) -> str | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment.strftime("%H:%M")


def _present_number(data: dict[str, Any], key: str) -> float | None:
    if key not in data:
        return None
    return _optional_number(data.get(key))


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)


def _num(value: float) -> str:
    text = f"{float(value):.1f}".replace(".", ",")
    if text.endswith(",0"):
        return text[:-2]
    return text
