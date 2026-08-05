"""Pure wallbox control decisions for PV Charge Manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import floor, isfinite


class WallboxAction(StrEnum):
    """Actions that the Home Assistant adapter may apply."""

    HOLD = "hold"
    START = "start"
    STOP = "stop"
    SET_CURRENT = "set_current"


@dataclass(frozen=True, slots=True)
class WallboxControlConfig:
    """Safety and debounce limits for wallbox control."""

    minimum_current_a: float = 6.0
    maximum_current_a: float = 16.0
    current_step_a: float = 1.0
    start_delay_s: int = 120
    stop_delay_s: int = 60
    minimum_runtime_s: int = 600
    fallback_stop: bool = True

    def __post_init__(self) -> None:
        """Validate the control limits at construction time."""
        if self.minimum_current_a <= 0:
            raise ValueError("minimum_current_a must be greater than 0")
        if self.maximum_current_a < self.minimum_current_a:
            raise ValueError("maximum_current_a must be at least minimum_current_a")
        if self.current_step_a <= 0:
            raise ValueError("current_step_a must be greater than 0")
        if any(
            value < 0 for value in (self.start_delay_s, self.stop_delay_s, self.minimum_runtime_s)
        ):
            raise ValueError("wallbox delays and minimum runtime must not be negative")

    def normalize_current_a(self, requested_current_a: float | None) -> float:
        """Clamp a requested current to a safe EVSE step or return zero."""
        if requested_current_a is None:
            return 0.0
        if not isfinite(requested_current_a) or requested_current_a < 0:
            raise ValueError("requested_current_a must be finite and non-negative")
        if requested_current_a < self.minimum_current_a:
            return 0.0

        capped_current_a = min(requested_current_a, self.maximum_current_a)
        stepped_current_a = floor(capped_current_a / self.current_step_a) * self.current_step_a
        if stepped_current_a < self.minimum_current_a:
            return 0.0
        return round(stepped_current_a, 3)


@dataclass(frozen=True, slots=True)
class WallboxState:
    """Known wallbox and coordinator state at one point in time."""

    now: datetime
    vehicle_connected: bool | None
    charging: bool | None
    current_a: float | None
    inputs_available: bool
    recommended_current_a: float | None
    manual_override: bool = False


@dataclass(frozen=True, slots=True)
class WallboxDecision:
    """A safe control decision for the Home Assistant adapter."""

    action: WallboxAction
    target_current_a: float | None
    reason: str


class WallboxController:
    """Apply debounce and minimum-runtime rules to control decisions."""

    def __init__(self, config: WallboxControlConfig) -> None:
        self.config = config
        self._pending_start_at: datetime | None = None
        self._pending_stop_at: datetime | None = None
        self._session_started_at: datetime | None = None

    def evaluate(self, state: WallboxState) -> WallboxDecision:
        """Return the next safe action without performing any Home Assistant call."""
        if state.manual_override:
            self._clear_pending()
            return WallboxDecision(WallboxAction.HOLD, None, "manual_override")

        if state.vehicle_connected is None or state.charging is None:
            self._clear_pending()
            return WallboxDecision(WallboxAction.HOLD, None, "wallbox_state_unknown")

        if not state.vehicle_connected:
            self._clear_pending()
            if state.charging:
                return WallboxDecision(WallboxAction.STOP, None, "vehicle_disconnected")
            return WallboxDecision(WallboxAction.HOLD, None, "vehicle_disconnected")

        if not state.inputs_available:
            self._pending_start_at = None
            if state.charging and self.config.fallback_stop:
                return self._stop_decision(state.now, "required_input_unavailable")
            return WallboxDecision(WallboxAction.HOLD, None, "required_input_unavailable")

        target_current_a = self.config.normalize_current_a(state.recommended_current_a)
        if target_current_a == 0:
            self._pending_start_at = None
            if state.charging:
                return self._stop_decision(state.now, "insufficient_pv_surplus")
            self._clear_pending()
            return WallboxDecision(WallboxAction.HOLD, None, "insufficient_pv_surplus")

        self._pending_stop_at = None
        if not state.charging:
            return self._start_decision(state.now, target_current_a)

        self._pending_start_at = None
        if self._session_started_at is None:
            self._session_started_at = state.now
        if state.current_a is None or abs(state.current_a - target_current_a) >= 0.1:
            return WallboxDecision(WallboxAction.SET_CURRENT, target_current_a, "surplus_changed")
        return WallboxDecision(WallboxAction.HOLD, target_current_a, "current_within_target")

    def acknowledge(self, decision: WallboxDecision, now: datetime) -> None:
        """Record a successfully applied action so it is not repeated blindly."""
        if decision.action is WallboxAction.START:
            self._pending_start_at = None
            self._session_started_at = now
        elif decision.action is WallboxAction.STOP:
            self._clear_pending()
        elif decision.action is WallboxAction.SET_CURRENT:
            self._pending_stop_at = None

    def _start_decision(self, now: datetime, target_current_a: float) -> WallboxDecision:
        """Debounce a start request before returning START."""
        self._pending_stop_at = None
        if self._pending_start_at is None:
            self._pending_start_at = now
        elapsed_s = (now - self._pending_start_at).total_seconds()
        if elapsed_s < self.config.start_delay_s:
            return WallboxDecision(WallboxAction.HOLD, target_current_a, "start_debounce")
        return WallboxDecision(WallboxAction.START, target_current_a, "pv_surplus_available")

    def _stop_decision(self, now: datetime, reason: str) -> WallboxDecision:
        """Enforce minimum runtime and debounce before stopping."""
        self._session_started_at = self._session_started_at or now
        runtime_s = (now - self._session_started_at).total_seconds()
        if runtime_s < self.config.minimum_runtime_s:
            return WallboxDecision(WallboxAction.HOLD, None, "minimum_runtime")

        if self._pending_stop_at is None:
            self._pending_stop_at = now
        elapsed_s = (now - self._pending_stop_at).total_seconds()
        if elapsed_s < self.config.stop_delay_s:
            return WallboxDecision(WallboxAction.HOLD, None, "stop_debounce")
        return WallboxDecision(WallboxAction.STOP, None, reason)

    def _clear_pending(self) -> None:
        """Clear transient timers after an inactive or manual state."""
        self._pending_start_at = None
        self._pending_stop_at = None
        self._session_started_at = None
