# Architecture

## Goal

PV Charge Manager should become a Home Assistant-native controller for local EV
charging decisions. The integration consumes existing Home Assistant entities,
calculates surplus and charge plans, exposes derived entities, and later controls
a wallbox through configured Home Assistant entities.

## Components

```text
Home Assistant states
  -> PV Charge Manager coordinator
  -> pure domain calculations
  -> Home Assistant entities and services
  -> optional custom frontend panel
```

## Package boundaries

- `calculation.py`: surplus power, current conversion, vehicle energy demand.
- `allocation.py`: balance-sheet allocation of PV sources by feed-in tariff.
- `forecast.py`: learning forecast calibration and corrected power series.
- `optimizer.py`: charging window selection from forecast slots.
- `coordinator.py`: Home Assistant state gathering and update orchestration.
- platform files: sensors, binary sensors, numbers, selects, switches, buttons.
- `websocket.py`: future bridge for the custom frontend panel.

## Runtime model

The coordinator will read configured entity states every update cycle and build a
normalized snapshot:

```text
grid import/export
home consumption
PV sources
battery SOC and charge/discharge power
solar forecast
wallbox state
vehicle state
```

The calculation layer then produces:

```text
available surplus power
recommended charge current
planned charge windows
expected opportunity cost
target SOC feasibility
diagnostic warnings
```

## Economic allocation

Different PV systems can have different feed-in tariffs. The integration treats
EV charging as a balance-sheet allocation problem:

```text
1. use PV source with lowest feed-in tariff first
2. then next cheapest PV source
3. then battery or grid only if the selected mode allows it
```

This does not describe physical routing. It describes which production is
economically assigned to the EV load.

## Learning forecast calibration

The solar forecast must be corrected from historic behavior before it is used
for charge planning. Each completed forecast interval creates one observation:

```text
historic observation =
forecast energy for the interval
actual PV yield for the same interval
```

The model keeps a bounded correction factor:

```text
corrected forecast = raw forecast * learned correction factor
```

Behavior:

- if forecast and actual yield matched, the factor stays stable
- if the forecast was too low and actual yield was higher, the factor moves up
- if the forecast was too high and actual yield was lower, the factor moves down
- each update uses a learning rate so one unusual day cannot dominate the model

The first implementation uses a global exponential moving correction factor. A
later version should split the model by PV system, season, weather class, and
time of day so morning, noon, and evening errors can be corrected differently.

Charge planning must consume the corrected forecast, not the raw forecast, once
enough historic observations are available.

## Safety boundaries

Wallbox control must not be implemented as a direct formula output. Future
control logic needs these guardrails:

- configured minimum and maximum current
- one-phase or three-phase validation
- minimum runtime and stop delay to avoid rapid switching
- fallback to stop or hold current when required sensors are unavailable
- explicit mode selection before grid or battery power is used
- clear diagnostic state for blocked charging

## Frontend strategy

The first usable UI should be the Home Assistant config/options flow plus normal
entities. A custom panel should be added only after the backend model is stable.
The panel should use the WebSocket API and never own core charging state itself.
