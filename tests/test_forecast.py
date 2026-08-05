from __future__ import annotations

import pytest

from custom_components.pv_charge_manager.forecast import (
    ForecastCalibration,
    ForecastObservation,
    corrected_energy_kwh,
    corrected_power_series_w,
    correction_factor,
    train_calibration_model,
)


def test_correction_factor_is_bounded() -> None:
    assert correction_factor(40, 34) == 0.85
    assert correction_factor(40, 10) == 0.5
    assert correction_factor(40, 60) == 1.2


def test_corrected_energy_kwh() -> None:
    assert corrected_energy_kwh(30, 0.85) == 25.5


def test_corrected_power_series_w() -> None:
    assert corrected_power_series_w([1_000, 2_000], 0.85) == [850, 1_700]


def test_calibration_stays_neutral_when_forecast_matches_actual_yield() -> None:
    model = ForecastCalibration().update(ForecastObservation(forecast_kwh=40, actual_kwh=40))

    assert model.factor == 1.0
    assert model.sample_count == 1


def test_calibration_adjusts_up_when_actual_yield_exceeds_forecast() -> None:
    model = ForecastCalibration(learning_rate=0.5).update(
        ForecastObservation(forecast_kwh=40, actual_kwh=48)
    )

    assert model.factor == 1.1
    assert model.correct_energy_kwh(30) == 33
    assert model.correct_power_series_w([1_000, 2_000]) == [1_100, 2_200]


def test_calibration_adjusts_down_when_actual_yield_is_below_forecast() -> None:
    model = ForecastCalibration(learning_rate=0.5).update(
        ForecastObservation(forecast_kwh=40, actual_kwh=32)
    )

    assert model.factor == 0.9
    assert model.correct_energy_kwh(30) == 27


def test_train_calibration_model_uses_historic_observations_in_order() -> None:
    model = train_calibration_model(
        [
            ForecastObservation(forecast_kwh=40, actual_kwh=48),
            ForecastObservation(forecast_kwh=40, actual_kwh=32),
        ],
        initial_model=ForecastCalibration(learning_rate=0.5),
    )

    assert model.factor == 0.95
    assert model.sample_count == 2


def test_invalid_calibration_weight_is_rejected() -> None:
    with pytest.raises(ValueError):
        ForecastCalibration().update(ForecastObservation(40, 40, weight=0))
