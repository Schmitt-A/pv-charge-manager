# Roadmap

## Version 0.1 - Energy monitor

Goal: installable integration that reads mapped entities and exposes useful
derived sensors without controlling the wallbox.

- config flow entry
- options flow for grid, home, PV, battery, and forecast entity mapping
- coordinator state snapshot with 30-second refresh
- surplus power sensor
- recommended current and charge power sensors
- opportunity cost sensor
- diagnostics and warning attributes for missing or invalid input
- tests for core calculations

## Version 0.2 - Wallbox control

Goal: controlled PV surplus charging with conservative hardware safety rules.

- wallbox entity mapping
- start/stop control
- current setpoint control
- minimum runtime
- stop delay
- cloud smoothing filter
- fallback behavior for unavailable sensors
- manual override handling

## Version 0.3 - Vehicle and charge plans

Goal: vehicle-aware planning.

- vehicle profiles
- SOC mapping
- target SOC
- departure time
- weekly schedules
- energy demand calculation
- immediate charge mode
- minimum charge mode

## Version 0.4 - Forecast optimization

Goal: use forecast windows to decide when charging should happen.

- quarter-hour or hourly forecast slots
- connect the learned forecast correction to runtime observations
- per-PV-source correction factors
- minimum sample threshold before the corrected forecast receives full trust
- household consumption baseline
- charge window optimizer
- target-time feasibility sensor

## Version 0.5 - Custom UI

Goal: Home Assistant sidebar panel for configuration and operation.

- overview page
- energy flow view
- vehicle page
- charge plan editor
- forecast page
- diagnostics page
- WebSocket commands

## Later

- dynamic electricity tariff integration
- multi-vehicle support
- seasonal household prediction
- forecast learning by season, weather class, and time of day
- battery aging constraints
- advanced cost reports
