from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.pv_charge_manager.wallbox import (
    WallboxAction,
    WallboxControlConfig,
    WallboxController,
    WallboxState,
)


def make_state(
    now: datetime,
    *,
    charging: bool | None = False,
    connected: bool | None = True,
    current_a: float | None = None,
    inputs_available: bool = True,
    recommended_current_a: float | None = 10.0,
    manual_override: bool = False,
) -> WallboxState:
    return WallboxState(
        now=now,
        vehicle_connected=connected,
        charging=charging,
        current_a=current_a,
        inputs_available=inputs_available,
        recommended_current_a=recommended_current_a,
        manual_override=manual_override,
    )


def test_normalize_current_clamps_and_uses_evse_steps() -> None:
    config = WallboxControlConfig(minimum_current_a=6, maximum_current_a=16, current_step_a=1)

    assert config.normalize_current_a(5.9) == 0
    assert config.normalize_current_a(12.8) == 12
    assert config.normalize_current_a(20) == 16


def test_start_requires_a_stable_surplus_before_starting() -> None:
    start = datetime(2026, 1, 1, 10, 0)
    controller = WallboxController(
        WallboxControlConfig(start_delay_s=60, stop_delay_s=0, minimum_runtime_s=0)
    )

    assert controller.evaluate(make_state(start)).action is WallboxAction.HOLD
    assert controller.evaluate(make_state(start + timedelta(seconds=59))).reason == "start_debounce"
    decision = controller.evaluate(make_state(start + timedelta(seconds=60)))

    assert decision.action is WallboxAction.START
    assert decision.target_current_a == 10


def test_stop_honors_minimum_runtime_and_stop_delay() -> None:
    start = datetime(2026, 1, 1, 10, 0)
    controller = WallboxController(
        WallboxControlConfig(start_delay_s=0, stop_delay_s=60, minimum_runtime_s=300)
    )
    start_decision = controller.evaluate(make_state(start))
    controller.acknowledge(start_decision, start)

    assert (
        controller.evaluate(
            make_state(
                start + timedelta(seconds=299), charging=True, current_a=10, recommended_current_a=0
            )
        ).reason
        == "minimum_runtime"
    )
    assert (
        controller.evaluate(
            make_state(
                start + timedelta(seconds=300), charging=True, current_a=10, recommended_current_a=0
            )
        ).reason
        == "stop_debounce"
    )
    assert (
        controller.evaluate(
            make_state(
                start + timedelta(seconds=359), charging=True, current_a=10, recommended_current_a=0
            )
        ).action
        is WallboxAction.HOLD
    )
    assert (
        controller.evaluate(
            make_state(
                start + timedelta(seconds=360), charging=True, current_a=10, recommended_current_a=0
            )
        ).action
        is WallboxAction.STOP
    )


def test_missing_inputs_can_fall_back_to_stop_without_guessing() -> None:
    now = datetime(2026, 1, 1, 10, 0)
    controller = WallboxController(
        WallboxControlConfig(start_delay_s=0, stop_delay_s=0, minimum_runtime_s=0)
    )

    decision = controller.evaluate(
        make_state(
            now, charging=True, current_a=10, inputs_available=False, recommended_current_a=None
        )
    )

    assert decision.action is WallboxAction.STOP
    assert decision.reason == "required_input_unavailable"


def test_unknown_wallbox_state_and_manual_override_never_issue_a_command() -> None:
    now = datetime(2026, 1, 1, 10, 0)
    controller = WallboxController(WallboxControlConfig())

    assert controller.evaluate(make_state(now, charging=None)).action is WallboxAction.HOLD
    assert (
        controller.evaluate(make_state(now, charging=True, manual_override=True)).action
        is WallboxAction.HOLD
    )


def test_invalid_requested_current_is_rejected() -> None:
    with pytest.raises(ValueError):
        WallboxControlConfig().normalize_current_a(float("nan"))
