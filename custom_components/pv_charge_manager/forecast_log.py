"""Remember one forecast day and turn it into a learning sample.

The wallbox setpoint is not part of this record.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .forecast import ForecastCalibration, ForecastObservation

MAX_GAP_S = 120.0
MIN_DAY_S = 3600.0
FULL_DAY_S = 6 * 3600.0
_SAVE_WH = 1.0


def record_forecast(
    learning: dict[str, Any],
    *,
    now: datetime,
    pv_w: float | None,
    hour_forecast_w: float | None,
) -> bool:
    """Add this reading to the open day. A finished day updates the stored factor."""
    if now.tzinfo is None:
        return False
    day = now.date().isoformat()
    hour = f"{now.hour:02d}"
    changed = False
    if learning.get("day") not in {None, day}:
        _close_day(learning)
        learning["hours"] = {}
        learning["day"] = day
        learning["_saved_wh"] = 0.0
        changed = True
    if learning.get("day") is None:
        learning["day"] = day
        changed = True
    hours = learning.get("hours")
    if not isinstance(hours, dict):
        hours = {}
        learning["hours"] = hours
        changed = True
    slot = hours.get(hour)
    if not isinstance(slot, dict):
        slot = {"forecast_w": None, "actual_wh": 0.0, "seconds": 0.0}
        hours[hour] = slot
        changed = True
    if slot.get("forecast_w") is None and _above_zero(hour_forecast_w):
        slot["forecast_w"] = float(hour_forecast_w)
        changed = True
    seen = _parse_time(learning.get("seen_at"))
    measured = _non_negative(pv_w)
    if seen is not None and measured is not None:
        elapsed = min(MAX_GAP_S, max(0.0, (now - seen).total_seconds()))
        if elapsed > 0:
            slot["actual_wh"] = float(slot.get("actual_wh") or 0) + measured * elapsed / 3600
            slot["seconds"] = float(slot.get("seconds") or 0) + elapsed
            if float(slot["actual_wh"]) - float(learning.get("_saved_wh") or 0) >= _SAVE_WH:
                learning["_saved_wh"] = _total_actual(hours)
                changed = True
    if measured is not None:
        learning["seen_at"] = now.isoformat()
    return changed


def _close_day(learning: dict[str, Any]) -> None:
    hours = learning.get("hours")
    if not isinstance(hours, dict):
        return
    forecast_wh = 0.0
    actual_wh = 0.0
    seconds = 0.0
    for slot in hours.values():
        if not isinstance(slot, dict):
            continue
        elapsed = float(slot.get("seconds") or 0)
        seconds += elapsed
        actual_wh += float(slot.get("actual_wh") or 0)
        forecast_w = slot.get("forecast_w")
        if forecast_w is not None and elapsed > 0:
            forecast_wh += float(forecast_w) * elapsed / 3600
    if seconds < MIN_DAY_S or forecast_wh <= 0:
        return
    model = _model(learning).update(
        ForecastObservation(
            forecast_kwh=forecast_wh / 1000,
            actual_kwh=actual_wh / 1000,
            weight=min(1.0, seconds / FULL_DAY_S),
        )
    )
    learning["factor"] = model.factor
    learning["samples"] = model.sample_count
    learning["sample_count"] = model.sample_count
    history = learning.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "day": learning.get("day"),
            "forecast_kwh": round(forecast_wh / 1000, 3),
            "actual_kwh": round(actual_wh / 1000, 3),
        }
    )
    learning["history"] = history[-30:]


def _model(learning: dict[str, Any]) -> ForecastCalibration:
    factor = _bounded(learning.get("factor"), 1.0)
    try:
        samples = int(learning.get("samples", learning.get("sample_count", 0)) or 0)
    except (TypeError, ValueError):
        samples = 0
    return ForecastCalibration(factor=factor, sample_count=max(0, samples))


def _bounded(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number:
        return fallback
    return min(1.3, max(0.5, number))


def _above_zero(value: Any) -> bool:
    number = _non_negative(value)
    return number is not None and number > 0


def _non_negative(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number != number:
        return None
    return number


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment


def _total_actual(hours: dict[str, Any]) -> float:
    total = 0.0
    for slot in hours.values():
        if isinstance(slot, dict):
            total += float(slot.get("actual_wh") or 0)
    return total
