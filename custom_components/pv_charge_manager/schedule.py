"""Weekly charge window and the late price window. No device writes."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

WEEKDAYS = ("mo", "di", "mi", "do", "fr", "sa", "so")
_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def schedule_open(moment: datetime, week: dict[str, Any] | None) -> bool:
    """An empty week allows every hour. A listed day allows only its clock window."""
    if not week:
        return True
    raw = week.get(WEEKDAYS[moment.weekday()])
    if not isinstance(raw, dict):
        return False
    start = _minutes(raw.get("start"))
    end = _minutes(raw.get("end"))
    if start is None or end is None:
        return True
    minute = moment.hour * 60 + moment.minute
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end


def grid_window_open(
    moment: datetime,
    departure: datetime | None,
    late_hours: float | None,
) -> bool:
    """Surplus may charge early. Grid and full-power charging wait for the late window."""
    if late_hours is None or late_hours <= 0 or departure is None:
        return True
    return moment >= departure - timedelta(hours=float(late_hours))


def _minutes(value: Any) -> int | None:
    if not isinstance(value, str) or not _CLOCK.match(value):
        return None
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)
