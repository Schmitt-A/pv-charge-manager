"""Versioned JSON backup. Older schemas migrate. Newer schemas are rejected."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1
SECRET_KEYS = ("token", "password", "secret")


class UnsupportedSchema(ValueError):
    """Raised when a backup was written by a newer app."""


@dataclass(slots=True)
class ImportResult:
    """Migrated backup plus warnings for fields that fell back to defaults."""

    settings: dict[str, Any]
    step: str
    warnings: list[str] = field(default_factory=list)


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
    settings: dict[str, Any], step: str, now: datetime | None = None
) -> dict[str, Any]:
    """Build a schema-1 document. Secrets are not copied."""
    clean = {key: value for key, value in settings.items() if key not in SECRET_KEYS}
    moment = now or datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": "0.4.0",
        "exported_at": moment.isoformat(),
        "step": step,
        "settings": clean,
    }


def migrate(document: dict[str, Any], target: int = SCHEMA_VERSION) -> dict[str, Any]:
    """Move a document forward to the target schema."""
    version = int(document.get("schema_version", 1))
    if version > target:
        raise UnsupportedSchema(f"Schema {version} ist neuer als diese App.")
    settings = default_settings()
    settings.update(document.get("settings") or {})
    for key in SECRET_KEYS:
        settings.pop(key, None)
    return {
        "schema_version": target,
        "app_version": str(document.get("app_version", "0.4.0")),
        "exported_at": str(document.get("exported_at", "")),
        "step": str(document.get("step", "site")),
        "settings": settings,
    }


def import_document(payload: dict[str, Any]) -> ImportResult:
    """Validate, migrate and report missing fields."""
    if not isinstance(payload, dict):
        raise TypeError("Die Datei ist kein JSON-Objekt.")
    raw = {key: value for key, value in payload.items() if key not in SECRET_KEYS}
    incoming = raw.get("settings") or {}
    warnings = [
        f"Feld {key} fehlte und nutzt den Standard."
        for key in default_settings()
        if key not in incoming
    ]
    migrated = migrate(raw)
    return ImportResult(
        settings=migrated["settings"], step=migrated["step"], warnings=warnings
    )
