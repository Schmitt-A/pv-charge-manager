"""Economic allocation helpers for PV Charge Manager."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PvSource:
    """A PV source with power and feed-in tariff metadata."""

    name: str
    available_power_w: float
    feed_in_tariff_eur_per_kwh: float
    priority: int = 100


@dataclass(frozen=True, slots=True)
class PowerAllocation:
    """Allocated power from one source."""

    source_name: str
    allocated_power_w: float
    feed_in_tariff_eur_per_kwh: float


def allocate_power_by_tariff(
    sources: list[PvSource],
    requested_power_w: float,
) -> list[PowerAllocation]:
    """Allocate requested load to the cheapest PV opportunity cost first."""
    if requested_power_w < 0:
        raise ValueError("requested_power_w must not be negative")

    remaining_power_w = requested_power_w
    allocations: list[PowerAllocation] = []

    ordered_sources = sorted(
        sources,
        key=lambda source: (
            source.feed_in_tariff_eur_per_kwh,
            source.priority,
            source.name.casefold(),
        ),
    )

    for source in ordered_sources:
        _validate_source(source)
        if remaining_power_w <= 0:
            break

        allocated_power_w = min(source.available_power_w, remaining_power_w)
        if allocated_power_w <= 0:
            continue

        allocations.append(
            PowerAllocation(
                source_name=source.name,
                allocated_power_w=round(allocated_power_w, 3),
                feed_in_tariff_eur_per_kwh=source.feed_in_tariff_eur_per_kwh,
            )
        )
        remaining_power_w -= allocated_power_w

    return allocations


def allocated_opportunity_cost_eur_per_hour(allocations: list[PowerAllocation]) -> float:
    """Calculate hourly feed-in revenue that is not earned due to EV charging."""
    cost = sum(
        (allocation.allocated_power_w / 1000) * allocation.feed_in_tariff_eur_per_kwh
        for allocation in allocations
    )
    return round(cost, 4)


def _validate_source(source: PvSource) -> None:
    if not source.name:
        raise ValueError("source name must not be empty")
    if source.available_power_w < 0:
        raise ValueError("available_power_w must not be negative")
    if source.feed_in_tariff_eur_per_kwh < 0:
        raise ValueError("feed_in_tariff_eur_per_kwh must not be negative")
