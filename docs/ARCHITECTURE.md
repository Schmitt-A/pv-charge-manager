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
- `preview.py`: day preview for battery priority, car target, buffer and price.
- `day_preview.py`: turns a forecast series into today, tomorrow and the good/bad band.
- `probe.py`: read-only entity status, raw value and normalized value.
- `setup_draft.py`: step menu draft, JSON load and continuation rules.
- `backup.py`: versioned JSON export, import, and schema migrations.
- `storage.py`: persisted vehicle, plan, learning state and backup draft.
- `coordinator.py`: Home Assistant state gathering, validation, and update orchestration.
- `wallbox.py`: pure current validation, debounce, minimum-runtime, and fallback decisions.
- `sensor.py`: first read-only calculated sensors from coordinator state.
- platform files: future binary sensors, numbers, selects, switches, and buttons.
- `websocket.py`: future bridge for the custom frontend panel.

## Runtime model

The coordinator reads configured entity states every 30 seconds and builds a
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
recommended charge current and power
expected opportunity cost
wallbox control decision
diagnostic warnings
```

Inputs come only from Home Assistant entities and devices. The integration does
not open its own device protocol or account session.

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

The first implementation uses a global exponential moving correction factor in
pure domain code. A later version should persist observations and split the model
by PV system, season, weather class, and time of day so morning, noon, and evening
errors can be corrected differently.

Charge planning must consume the corrected forecast, not the raw forecast, once
enough historic observations are available. Learned factors are part of the JSON
backup.

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

Entities remain the first usable interface. The custom panel is a responsive
sidebar view for phone and desktop: energy flow, two-day preview, plan editor,
and backup actions. It uses the WebSocket API and never owns core charging state.
Layout follows the Home Assistant theme, stacks on narrow screens, and keeps the
main column usable at 360 pixels.

## Backup

`backup.py` exports and imports one JSON document keyed by `schema_version`.
Older schemas migrate forward. Newer schemas are rejected. Secrets and live
measurements are not included. See [BACKUP.md](BACKUP.md).

## Wallbox control boundary

The coordinator is the only Home Assistant-facing adapter that may call wallbox
services. `wallbox.py` remains pure and returns one of `hold`, `start`, `stop`,
or `set_current`. The coordinator applies a non-hold decision only when the user
explicitly enabled control and all required entities are mapped. Service failures
are converted to diagnostics and are not acknowledged as successful actions.
