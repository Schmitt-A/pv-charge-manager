"""Versioned JSON backup. Older schemas migrate. Newer schemas are rejected."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1
SECRET_KEYS = ("token", "password", "secret")
_OPTIONAL_SECTIONS = ("plans", "entity_map", "learning")


class UnsupportedSchema(ValueError):
    """Raised when a backup was written by a newer app."""


@dataclass(slots=True)
class ImportResult:
    """Migrated backup plus warnings for fields that fell back to defaults."""

    settings: dict[str, Any]
    step: str
    warnings: list[str] = field(default_factory=list)
    plans: list[dict[str, Any]] = field(default_factory=list)
    entity_map: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)


def default_settings() -> dict[str, Any]:
    """Return the settings a missing backup field falls back to."""
    return {
        "mode": "smart",
        "strategy": "forecast",
        "always_charge": False,
        "solar_share": 100,
        "priority_soc": 70,
        "buffer_soc": 40,
        "reserve_soc": 20,
    }


def export_document(
    settings: dict[str, Any],
    step: str,
    now: datetime | None = None,
    *,
    plans: list[dict[str, Any]] | None = None,
    entity_map: dict[str, Any] | None = None,
    learning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-1 document. Secrets are not copied."""
    moment = now or datetime.now(UTC)
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": "0.4.0",
        "exported_at": moment.isoformat(),
        "step": step,
        "settings": _clean(settings),
        "plans": _clean(list(plans or [])),
        "entity_map": _clean(dict(entity_map or {})),
        "learning": _clean(dict(learning or {})),
    }


def migrate(document: dict[str, Any], target: int = SCHEMA_VERSION) -> dict[str, Any]:
    """Move a document forward to the target schema."""
    version = int(document.get("schema_version", 1))
    if version > target:
        raise UnsupportedSchema(f"Schema {version} ist neuer als diese App.")
    settings = default_settings()
    incoming = document.get("settings") or {}
    if isinstance(incoming, dict):
        settings.update(incoming)
    plans = document.get("plans") or []
    if isinstance(document.get("plan"), dict) and not plans:
        plans = [document["plan"]]
    if not isinstance(plans, list):
        plans = []
    entity_map = document.get("entity_map") or {}
    learning = document.get("learning") or {}
    return {
        "schema_version": target,
        "app_version": str(document.get("app_version", "0.4.0")),
        "exported_at": str(document.get("exported_at", "")),
        "step": str(document.get("step", "site")),
        "settings": _clean(settings),
        "plans": _clean(plans),
        "entity_map": _clean(entity_map if isinstance(entity_map, dict) else {}),
        "learning": _clean(learning if isinstance(learning, dict) else {}),
    }


def import_document(payload: dict[str, Any]) -> ImportResult:
    """Validate, migrate and report missing fields."""
    if not isinstance(payload, dict):
        raise TypeError("Die Datei ist kein JSON-Objekt.")
    raw = _clean(payload)
    incoming = raw.get("settings") or {}
    if not isinstance(incoming, dict):
        incoming = {}
    warnings = [
        f"Feld {key} fehlte und nutzt den Standard."
        for key in default_settings()
        if key not in incoming
    ]
    warnings.extend(
        f"Feld {key} fehlte und nutzt den Standard." for key in _OPTIONAL_SECTIONS if key not in raw
    )
    migrated = migrate(raw)
    return ImportResult(
        settings=migrated["settings"],
        step=migrated["step"],
        warnings=warnings,
        plans=list(migrated["plans"]),
        entity_map=dict(migrated["entity_map"]),
        learning=dict(migrated["learning"]),
    )


def _clean(value: Any) -> Any:
    """Drop secret keys from mappings and lists without mutating the input."""
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items() if key not in SECRET_KEYS}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value
