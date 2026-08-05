from __future__ import annotations

from custom_components.pv_charge_manager.allocation import (
    PvSource,
    allocate_power_by_tariff,
    allocated_opportunity_cost_eur_per_hour,
)


def test_allocate_power_by_lowest_feed_in_tariff_first() -> None:
    allocations = allocate_power_by_tariff(
        [
            PvSource("high_tariff", 5_000, 0.25),
            PvSource("low_tariff", 4_000, 0.08),
        ],
        requested_power_w=6_000,
    )

    assert [allocation.source_name for allocation in allocations] == ["low_tariff", "high_tariff"]
    assert [allocation.allocated_power_w for allocation in allocations] == [4_000, 2_000]


def test_allocated_opportunity_cost_eur_per_hour() -> None:
    allocations = allocate_power_by_tariff(
        [
            PvSource("a", 1_000, 0.10),
            PvSource("b", 1_000, 0.20),
        ],
        requested_power_w=2_000,
    )

    assert allocated_opportunity_cost_eur_per_hour(allocations) == 0.3
