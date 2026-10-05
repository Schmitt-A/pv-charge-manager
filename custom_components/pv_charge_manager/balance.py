"""Zero-export detection and the night-reserve recommendation.

Neither result changes the wallbox setpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta

CLAMP_W = 50.0
STEP = timedelta(minutes=15)
MORNING_HOUR = 7
GOOD_FACTOR = 1.12
BAD_FACTOR = 0.78


def zero_export_status(
    pv_w: float | None,
    home_w: float | None,
    battery_charge_w: float | None,
    grid_import_w: float | None,
    grid_export_w: float | None,
) -> dict[str, object]:
    """Detect an inverter that hides surplus by holding the meter near zero."""
    if None in {pv_w, home_w, battery_charge_w, grid_import_w, grid_export_w}:
        return {
            "zero_export": "unknown",
            "balance_surplus_w": None,
            "zero_export_detail": "Netzbezug bleibt führend. Die Bilanz ist unvollständig.",
        }
    balance = float(pv_w) - float(home_w) - float(battery_charge_w)
    meter_quiet = float(grid_export_w) <= CLAMP_W and float(grid_import_w) <= CLAMP_W
    if meter_quiet and balance > CLAMP_W:
        return {
            "zero_export": "active",
            "balance_surplus_w": round(balance, 1),
            "zero_export_detail": (
                "Nulleinspeisung. Die Bilanz hat noch Überschuss, der Zähler nicht."
            ),
        }
    return {
        "zero_export": "inactive",
        "balance_surplus_w": None,
        "zero_export_detail": "Der Zähler führt. Keine Nulleinspeisung erkannt.",
    }


def storage_outlook(
    *,
    now: datetime,
    battery_soc: float,
    battery_capacity_kwh: float,
    reserve_soc: float,
    home_w: float,
    battery_max_charge_w: float = 5000.0,
    battery_efficiency: float = 0.92,
    max_soc: float = 100.0,
    reserve_power_w: float = 300.0,
    forecast_w: list[float] | None = None,
    factor: float = 1.0,
    vehicle_efficiency: float | None = None,
) -> dict[str, object]:
    """Recommend whether the battery stays above the reserve until morning."""
    nominal = _walk(
        now=now,
        battery_soc=battery_soc,
        battery_capacity_kwh=battery_capacity_kwh,
        reserve_soc=reserve_soc,
        home_w=home_w,
        battery_max_charge_w=battery_max_charge_w,
        battery_efficiency=battery_efficiency,
        max_soc=max_soc,
        reserve_power_w=reserve_power_w,
        forecast_w=forecast_w,
        factor=factor,
    )
    early = _walk(
        now=now,
        battery_soc=battery_soc,
        battery_capacity_kwh=battery_capacity_kwh,
        reserve_soc=reserve_soc,
        home_w=home_w,
        battery_max_charge_w=battery_max_charge_w,
        battery_efficiency=battery_efficiency,
        max_soc=max_soc,
        reserve_power_w=reserve_power_w,
        forecast_w=forecast_w,
        factor=factor * GOOD_FACTOR,
    )
    late = _walk(
        now=now,
        battery_soc=battery_soc,
        battery_capacity_kwh=battery_capacity_kwh,
        reserve_soc=reserve_soc,
        home_w=home_w,
        battery_max_charge_w=battery_max_charge_w,
        battery_efficiency=battery_efficiency,
        max_soc=max_soc,
        reserve_power_w=reserve_power_w,
        forecast_w=forecast_w,
        factor=factor * BAD_FACTOR,
    )
    reserve_pct = round(reserve_soc)
    if nominal["short"]:
        sentence = (
            f"Die Nachtreserve reicht nicht. Unter {reserve_pct} Prozent "
            "müsste das Netz übernehmen."
        )
    else:
        sentence = f"Die Nachtreserve reicht. Morgen früh etwa {nominal['morning_soc']} Prozent."
    return {
        "night_reserve": sentence,
        "morning_soc": nominal["morning_soc"],
        "autonomy_hours": _autonomy_hours(battery_soc, battery_capacity_kwh, reserve_soc, home_w),
        "site_meta": {
            "sunset_soc": nominal["sunset_soc"],
            "morning_soc_early": early["morning_soc"],
            "morning_soc_late": late["morning_soc"],
            "reserve_soc": reserve_soc,
            "battery_efficiency": battery_efficiency,
            "vehicle_efficiency": vehicle_efficiency,
            "hit_reserve": nominal["short"],
        },
    }


def _walk(
    *,
    now: datetime,
    battery_soc: float,
    battery_capacity_kwh: float,
    reserve_soc: float,
    home_w: float,
    battery_max_charge_w: float,
    battery_efficiency: float,
    max_soc: float,
    reserve_power_w: float,
    forecast_w: list[float] | None,
    factor: float,
) -> dict[str, object]:
    stored = (battery_soc / 100) * battery_capacity_kwh
    reserve = (reserve_soc / 100) * battery_capacity_kwh
    maximum = (max_soc / 100) * battery_capacity_kwh
    sunset = stored
    short = False
    cursor = now
    morning = _next_morning(now)
    while cursor < morning:
        nxt = min(cursor + STEP, morning)
        hours = (nxt - cursor).total_seconds() / 3600
        pv_w = _pv_at(forecast_w, now, cursor) * factor
        surplus_w = pv_w - home_w - reserve_power_w
        if surplus_w > 0:
            gained = (min(surplus_w, battery_max_charge_w) / 1000) * hours * battery_efficiency
            stored = min(maximum, stored + gained)
        else:
            needed = max(0.0, (home_w - pv_w) / 1000) * hours
            available = max(0.0, stored - reserve)
            if needed > available + 0.001:
                short = True
            stored = max(reserve, stored - min(needed, available))
        if pv_w >= CLAMP_W:
            sunset = stored
        cursor = nxt
    return {
        "morning_soc": _pct(stored, battery_capacity_kwh),
        "sunset_soc": _pct(sunset, battery_capacity_kwh),
        "short": short,
    }


def _next_morning(now: datetime) -> datetime:
    morning = now.replace(hour=MORNING_HOUR, minute=0, second=0, microsecond=0)
    if now < morning:
        return morning
    return morning + timedelta(days=1)


def _pv_at(forecast_w: list[float] | None, now: datetime, moment: datetime) -> float:
    if not forecast_w:
        return 0.0
    start = now.replace(minute=0, second=0, microsecond=0)
    index = int((moment - start).total_seconds() // 3600)
    if index < 0 or index >= len(forecast_w):
        return 0.0
    return max(0.0, forecast_w[index])


def _autonomy_hours(soc: float, capacity: float, reserve_soc: float, home_w: float) -> float | None:
    if home_w <= CLAMP_W:
        return None
    above = ((soc - reserve_soc) / 100) * capacity
    if above <= 0:
        return 0.0
    return round(above / (home_w / 1000), 1)


def _pct(stored: float, capacity: float) -> int:
    if capacity <= 0:
        return 0
    return round(min(100, max(0, (stored / capacity) * 100)))
