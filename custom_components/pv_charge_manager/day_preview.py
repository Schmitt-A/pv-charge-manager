"""Forecast day preview. No Home Assistant import and no wallbox writes."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .calculation import ChargeLimits, required_vehicle_energy_kwh
from .optimizer import ForecastSlot, build_charge_plan
from .preview import CHEAP_EUR, STEP, PreviewConfig, PreviewSlot, simulate_case

GOOD_FACTOR = 1.12
BAD_FACTOR = 0.78
TRUST_SAMPLES = 7
SLOT_HOURS = 1


def parse_number_series(raw: str) -> list[float] | None:
    """Read one number, a comma list, or a JSON list. Anything else is unreadable."""
    text = raw.strip()
    if not text or text in {"unknown", "unavailable", "none"}:
        return None
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list):
            return None
        return _finite(parsed)
    if "," in text:
        return _finite([part.strip() for part in text.split(",") if part.strip()])
    return _finite([text])


def sum_series(series: list[list[float]]) -> list[float]:
    """Add forecast series from several PV sources, index by index."""
    if not series:
        return []
    length = max(len(item) for item in series)
    return [sum(item[index] for item in series if index < len(item)) for index in range(length)]


def parse_departure(value: Any, now: datetime) -> datetime | None:
    """Read an ISO timestamp or a clock time. A clock time rolls to the next day."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=now.tzinfo)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=now.tzinfo)
    try:
        hour, minute = text.split(":", 1)
        candidate = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    except (TypeError, ValueError):
        return None
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def learned_factor(learning: dict[str, Any] | None) -> tuple[float, str]:
    """Keep the factor at 1 until seven samples exist. Trusted sources override the site."""
    data = learning or {}
    trusted = _trusted_source_factors(data.get("sources"))
    if trusted:
        average = sum(trusted) / len(trusted)
        return min(1.3, max(0.5, average)), "high"
    return _stored_factor(data)


def _stored_factor(data: dict[str, Any]) -> tuple[float, str]:
    try:
        samples = int(data.get("samples", data.get("sample_count", 0)) or 0)
    except (TypeError, ValueError):
        samples = 0
    if samples < TRUST_SAMPLES:
        return 1.0, "low"
    try:
        factor = float(data.get("factor", 1.0) or 1.0)
    except (TypeError, ValueError):
        factor = 1.0
    return min(1.3, max(0.5, factor)), "high"


def _trusted_source_factors(sources: Any) -> list[float]:
    if not isinstance(sources, dict):
        return []
    factors: list[float] = []
    for source in sources.values():
        if not isinstance(source, dict):
            continue
        factor, trust = _stored_factor(source)
        if trust == "high":
            factors.append(factor)
    return factors


def build_day_preview(
    *,
    forecast_w: list[float],
    home_w: float,
    now: datetime,
    battery_soc: float,
    battery_capacity_kwh: float,
    battery_max_charge_w: float = 5000.0,
    battery_efficiency: float = 0.92,
    priority_soc: float = 70.0,
    buffer_soc: float = 40.0,
    max_soc: float = 100.0,
    reserve_power_w: float = 300.0,
    vehicle_soc: float | None = None,
    vehicle_capacity_kwh: float | None = None,
    target_soc: float | None = None,
    vehicle_efficiency: float = 0.9,
    assumption: bool = True,
    min_power_w: float = 4140.0,
    max_power_w: float = 11040.0,
    always_charge: bool = False,
    use_price: bool = False,
    prices: list[float] | None = None,
    learning: dict[str, Any] | None = None,
    departure: datetime | None = None,
    limits: ChargeLimits | None = None,
    mode: str = "smart",
    solar_share: float = 100.0,
    cheap_eur: float = CHEAP_EUR,
    week: dict | None = None,
    late_hours: float | None = None,
) -> dict[str, Any]:
    """Build today and tomorrow from the supplied forecast. No invented curve."""
    if not forecast_w:
        raise ValueError("forecast series is empty")
    factor, trust = learned_factor(learning)
    slots = _slots(forecast_w, home_w, now, prices)
    has_vehicle = (
        vehicle_soc is not None and vehicle_capacity_kwh is not None and target_soc is not None
    )
    car_enabled, force_max = _mode_flags(mode)
    config = _config(
        battery_soc=battery_soc,
        battery_capacity_kwh=battery_capacity_kwh,
        battery_max_charge_w=battery_max_charge_w,
        battery_efficiency=battery_efficiency,
        priority_soc=priority_soc,
        buffer_soc=buffer_soc,
        max_soc=max_soc,
        reserve_power_w=reserve_power_w,
        vehicle_soc=vehicle_soc if has_vehicle else 0.0,
        vehicle_capacity_kwh=vehicle_capacity_kwh if has_vehicle else 1.0,
        target_soc=target_soc if has_vehicle else 0.0,
        vehicle_efficiency=vehicle_efficiency,
        min_power_w=min_power_w,
        max_power_w=max_power_w,
        always_charge=always_charge,
        use_price=use_price and has_vehicle,
        departure=departure,
        solar_share=solar_share,
        cheap_eur=cheap_eur,
        car_enabled=car_enabled,
        force_max=force_max and has_vehicle,
        week=week,
        late_hours=late_hours,
    )
    nominal = simulate_case(slots, config, factor)
    good = simulate_case(slots, config, factor * GOOD_FACTOR)
    bad = simulate_case(slots, config, factor * BAD_FACTOR)
    today = [slot for slot in slots if slot.start.date() == now.date()]
    tomorrow_day = now.date() + timedelta(days=1)
    tomorrow = [slot for slot in slots if slot.start.date() == tomorrow_day]
    today_case = simulate_case(today, config, factor) if today else None
    tomorrow_case = simulate_case(tomorrow, config, factor) if tomorrow else None
    result: dict[str, Any] = {
        "chargeable_kwh_today": today_case.chargeable_kwh if today_case else 0.0,
        "chargeable_kwh_tomorrow": tomorrow_case.chargeable_kwh if tomorrow_case else 0.0,
        "battery_full_at": _iso(nominal.battery_full_at),
        "battery_full_at_early": _iso(good.battery_full_at),
        "battery_full_at_late": _iso(bad.battery_full_at),
        "minimum_power_today": today_case.minimum_power if today_case else "never",
        "battery_recommendation": (
            f"Überschuss ans Auto erst ab {round(priority_soc)} Prozent. "
            f"Batteriestützung nur bis {round(buffer_soc)} Prozent."
        ),
        "preview_meta": {
            "forecast_trust": trust,
            "assumption": assumption or not has_vehicle,
            "learned_factor": factor,
            "battery_kwh": nominal.battery_kwh,
            "vehicle_kwh": nominal.vehicle_kwh if has_vehicle else 0.0,
            "grid_kwh": nominal.grid_kwh if has_vehicle else 0.0,
            "battery_support_kwh": nominal.battery_support_kwh if has_vehicle else 0.0,
            "vehicle_missing_kwh": nominal.vehicle_missing_kwh if has_vehicle else 0.0,
        },
    }
    if has_vehicle:
        result["vehicle_full_at"] = _iso(nominal.vehicle_target_at)
        theoretical = simulate_case(slots, replace(config, target_soc=100), factor)
        result["preview_meta"]["theoretical_full_at"] = _iso(theoretical.vehicle_target_at)
        result["plan_status"] = _plan_status(
            slots, config, factor, limits, use_price, always_charge, departure
        )
    return result


def _plan_status(
    slots: list[PreviewSlot],
    config: PreviewConfig,
    factor: float,
    limits: ChargeLimits | None,
    use_price: bool,
    always_charge: bool,
    departure: datetime | None,
) -> str:
    if not config.car_enabled:
        return "off"
    if config.force_max:
        return "needs_grid"
    if limits is None:
        case = simulate_case(slots, config, factor)
        if case.vehicle_missing_kwh <= 0.05 and case.grid_kwh <= 0.05:
            return "feasible"
        if use_price or always_charge:
            return "needs_grid"
        return "infeasible"
    required = required_vehicle_energy_kwh(
        config.vehicle_capacity_kwh,
        config.vehicle_soc,
        config.target_soc,
        config.vehicle_efficiency,
    )
    planned = build_charge_plan(_leftover(slots, config, factor, departure), required, limits)
    if planned.unmet_energy_kwh <= 0.05:
        return "feasible"
    if use_price or always_charge:
        return "needs_grid"
    return "infeasible"


def _mode_flags(mode: str) -> tuple[bool, bool]:
    """Return whether the car may charge, and whether it takes full power now."""
    if mode == "off":
        return False, False
    if mode == "now":
        return True, True
    return True, False


def _leftover(
    slots: list[PreviewSlot],
    config: PreviewConfig,
    factor: float,
    departure: datetime | None,
) -> list[ForecastSlot]:
    """Surplus that remains after the battery has taken power up to the priority."""
    stored = (config.battery_soc / 100) * config.battery_capacity_kwh
    priority = (config.priority_soc / 100) * config.battery_capacity_kwh
    maximum = (config.max_soc / 100) * config.battery_capacity_kwh
    planned: list[ForecastSlot] = []
    for slot in slots:
        if departure is not None and slot.start >= departure:
            break
        cursor = slot.start
        leftover_wh = 0.0
        hours = 0.0
        while cursor < slot.end:
            nxt = min(cursor + STEP, slot.end)
            step_hours = (nxt - cursor).total_seconds() / 3600
            surplus = max(0.0, slot.pv_w * factor - slot.home_w - config.reserve_power_w)
            if stored < priority - 0.001:
                take = min(surplus, config.battery_max_charge_w)
                stored = min(
                    maximum,
                    stored + (take / 1000) * step_hours * config.battery_efficiency,
                )
                leftover = surplus - take
            else:
                leftover = surplus
            leftover_wh += leftover * step_hours
            hours += step_hours
            cursor = nxt
        average = leftover_wh / hours if hours else 0.0
        price = slot.price_eur if config.use_price else None
        planned.append(ForecastSlot(slot.start, slot.end, average, price))
    return planned


def _slots(
    forecast_w: list[float],
    home_w: float,
    now: datetime,
    prices: list[float] | None,
) -> list[PreviewSlot]:
    start = now.replace(minute=0, second=0, microsecond=0)
    slots: list[PreviewSlot] = []
    for index, power in enumerate(forecast_w):
        begin = start + timedelta(hours=index * SLOT_HOURS)
        price = 0.3
        if prices:
            price = prices[index] if index < len(prices) else prices[-1]
        slots.append(PreviewSlot(begin, begin + timedelta(hours=SLOT_HOURS), power, home_w, price))
    return slots


def _config(**values: Any) -> PreviewConfig:
    return PreviewConfig(**values)


def _finite(values: list[Any]) -> list[float] | None:
    if not values:
        return None
    numbers: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number < 0:
            return None
        numbers.append(number)
    return numbers


def _iso(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()
