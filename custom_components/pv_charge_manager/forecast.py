"""Forecast correction helpers for PV Charge Manager."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForecastObservation:
    """Historic forecast and actual production for one learning sample."""

    forecast_kwh: float
    actual_kwh: float
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class ForecastCalibration:
    """Learned correction state for future solar forecasts."""

    factor: float = 1.0
    learning_rate: float = 0.25
    minimum_factor: float = 0.5
    maximum_factor: float = 1.3
    sample_count: int = 0

    def update(self, observation: ForecastObservation) -> ForecastCalibration:
        """Return an updated model from one historic forecast observation."""
        _validate_model(self)
        _validate_observation(observation)

        observed_factor = correction_factor(
            observation.forecast_kwh,
            observation.actual_kwh,
            default=self.factor,
            minimum=self.minimum_factor,
            maximum=self.maximum_factor,
        )
        effective_rate = min(1.0, self.learning_rate * observation.weight)
        updated_factor = self.factor + ((observed_factor - self.factor) * effective_rate)

        return ForecastCalibration(
            factor=round(min(max(updated_factor, self.minimum_factor), self.maximum_factor), 3),
            learning_rate=self.learning_rate,
            minimum_factor=self.minimum_factor,
            maximum_factor=self.maximum_factor,
            sample_count=self.sample_count + 1,
        )

    def correct_energy_kwh(self, forecast_kwh: float) -> float:
        """Apply the learned model to an energy forecast."""
        return corrected_energy_kwh(forecast_kwh, self.factor)

    def correct_power_series_w(self, values_w: list[float]) -> list[float]:
        """Apply the learned model to a power forecast series."""
        return corrected_power_series_w(values_w, self.factor)


def train_calibration_model(
    observations: list[ForecastObservation],
    *,
    initial_model: ForecastCalibration | None = None,
) -> ForecastCalibration:
    """Build a calibration model from historic forecast observations."""
    model = initial_model or ForecastCalibration()
    for observation in observations:
        model = model.update(observation)
    return model


def correction_factor(
    forecast_kwh: float,
    actual_kwh: float,
    *,
    default: float = 1.0,
    minimum: float = 0.5,
    maximum: float = 1.2,
) -> float:
    """Calculate a bounded correction factor from forecast and actual energy."""
    if forecast_kwh < 0:
        raise ValueError("forecast_kwh must not be negative")
    if actual_kwh < 0:
        raise ValueError("actual_kwh must not be negative")
    if not 0 < minimum <= maximum:
        raise ValueError("minimum and maximum must define a positive range")

    if forecast_kwh == 0:
        return default

    factor = actual_kwh / forecast_kwh
    return round(min(max(factor, minimum), maximum), 3)


def corrected_energy_kwh(forecast_kwh: float, factor: float) -> float:
    """Apply a correction factor to an energy forecast."""
    if forecast_kwh < 0:
        raise ValueError("forecast_kwh must not be negative")
    if factor < 0:
        raise ValueError("factor must not be negative")
    return round(forecast_kwh * factor, 3)


def corrected_power_series_w(values_w: list[float], factor: float) -> list[float]:
    """Apply a correction factor to a power forecast series."""
    if factor < 0:
        raise ValueError("factor must not be negative")
    if any(value < 0 for value in values_w):
        raise ValueError("forecast power values must not be negative")
    return [round(value * factor, 3) for value in values_w]


def _validate_model(model: ForecastCalibration) -> None:
    if model.factor < 0:
        raise ValueError("factor must not be negative")
    if not 0 < model.learning_rate <= 1:
        raise ValueError("learning_rate must be greater than 0 and at most 1")
    if not 0 < model.minimum_factor <= model.maximum_factor:
        raise ValueError("minimum_factor and maximum_factor must define a positive range")
    if not model.minimum_factor <= model.factor <= model.maximum_factor:
        raise ValueError("factor must be within the configured bounds")
    if model.sample_count < 0:
        raise ValueError("sample_count must not be negative")


def _validate_observation(observation: ForecastObservation) -> None:
    if observation.forecast_kwh < 0:
        raise ValueError("forecast_kwh must not be negative")
    if observation.actual_kwh < 0:
        raise ValueError("actual_kwh must not be negative")
    if observation.weight <= 0:
        raise ValueError("weight must be greater than 0")
