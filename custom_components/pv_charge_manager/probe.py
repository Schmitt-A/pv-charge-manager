"""Entity connection checks without a Home Assistant dependency."""

from __future__ import annotations

from dataclasses import dataclass

STATUSES = ("loaded", "missing", "stale", "invalid", "optional_empty")


@dataclass(frozen=True, slots=True)
class EntitySample:
    """One mapped entity as seen at configuration time."""

    entity_id: str
    present: bool
    state: str | None
    age_s: float | None
    numeric: bool
    required: bool
    raw: str
    normalized: str


@dataclass(frozen=True, slots=True)
class ProbeHit:
    """Result shown next to one entity."""

    entity_id: str
    status: str
    raw: str
    normalized: str


def probe_entity(sample: EntitySample, stale_after_s: float = 900) -> ProbeHit:
    """Classify one entity. The check never writes to a device."""
    if not sample.present or sample.state in {None, "", "unknown", "unavailable"}:
        status = "missing" if sample.required else "optional_empty"
    elif sample.age_s is not None and sample.age_s > stale_after_s:
        status = "stale"
    elif not sample.numeric:
        status = "invalid"
    else:
        status = "loaded"
    return ProbeHit(sample.entity_id, status, sample.raw, sample.normalized)


def blocks_step(hits: list[ProbeHit], required_ids: set[str]) -> bool:
    """A step continues only when every required entity is usable or stale."""
    return any(
        hit.entity_id in required_ids and hit.status in {"missing", "invalid"}
        for hit in hits
    )
