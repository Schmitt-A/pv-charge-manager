# Configuration Model

Configuration happens in a dedicated menu, not in raw YAML. The example file in `examples/configuration.yaml` documents the data model only.

The menu is a step-by-step guide. Each step can be skipped and reopened. At every step the current JSON can be downloaded or loaded again. A later app version migrates older files, as described in [BACKUP.md](BACKUP.md).

Until the panel exists, the same steps run in the Home Assistant config and options flow. The panel then uses that flow's data and adds the preview.

## Steps

1. Site: name, grid import, grid export, home consumption.
2. PV sources: power, optional daily energy, forecast, feed-in tariff.
3. Home battery: SOC, charge and discharge power, capacity, priority SOC, buffer, minimum reserve.
4. Forecast and price: forecast series, optional price series, strategy.
5. Wallbox: switch, current number, connected sensor, limits. Control stays off.
6. Vehicle: SOC, capacity, efficiency, target, departure.
7. Review: summary, warnings, and the first calculated surplus.

A step is complete only after its test passes or the user explicitly continues with a warning. Missing optional entities do not block the step. Missing required entities do.

## Connection test and preview

Each mapped entity is tested immediately:

- reachable: entity exists and last update is not stale
- value: numeric preview for power, energy, SOC, current, and price
- unit and device class checked against the expected quantity
- state text for switches and binary sensors

The preview shows the raw value and the normalized value used by the calculation. Hints are explicit:

- loaded: value accepted
- missing: entity not found
- stale: no update inside the expected window
- invalid: not numeric, wrong unit, or out of range
- optional empty: step can continue

The test does not start charging and does not write to the wallbox or inverter.

## JSON at every step

Save writes the current draft, including incomplete steps and the schema version. Load replaces the draft, migrates older schemas, and returns to the same step. Unknown future schemas are rejected. After load, every mapped entity is tested again and the hints are shown before the user continues.

## Required entity groups

### Grid

- import power sensor
- export power sensor

### Home consumption

- direct consumption power sensor, or
- calculated fallback from PV, grid, battery, and wallbox values

### PV systems

Each PV source can have:

- name
- current power sensor
- daily energy sensor
- optional forecast sensor
- feed-in tariff in EUR/kWh
- priority for equal tariffs
- forecast learning enabled or disabled
- optional forecast correction bounds

### Forecast learning

The pure forecast model supports historic forecast observations per PV source:

```text
forecast kWh
actual yield kWh
observation interval
learned correction factor
sample count
```

The correction factor is applied to future forecast values before the optimizer selects charge windows. Runtime persistence and per-source observation capture are planned for version 0.4. Recommended defaults:

- learning rate: `0.25`
- minimum factor: `0.5`
- maximum factor: `1.3`
- minimum samples before full trust: `7`

### Battery

Useful fields:

- SOC sensor
- charge power sensor
- discharge power sensor
- capacity in kWh
- minimum SOC
- backup reserve
- priority SOC and buffer limit
- mode for EV battery discharge permission

### Wallbox

Required before active control:

- charging switch or start/stop controls
- current setpoint number
- active charging power sensor
- vehicle connected binary sensor
- min current
- max current
- phases

Active control is opt-in through `wallbox_control_enabled` and remains disabled until the charging switch, current number, and vehicle-connected binary sensor are mapped. Optional mappings are a charging-power sensor and a manual-override binary sensor.

Safety defaults:

- start delay: `120` seconds
- stop delay: `60` seconds
- minimum runtime: `600` seconds
- fallback: hold while wallbox state is unknown; stop after the minimum runtime when PV or grid inputs become unavailable

The controller writes the current target before starting the charging switch. It never writes when the state is unknown, manual override is active, required entities are missing, or control is disabled.

### Vehicle

- SOC sensor
- usable capacity in kWh
- target SOC
- charging efficiency
- maximum current
- departure time or weekly schedule

## Current calculated entities

The first roadmap milestone exposes these read-only sensors:

- PV surplus after home consumption, battery charging, and safety reserve
- recommended current within the configured electrical limits
- recommended charging power
- opportunity cost per hour based on the configured feed-in tariff

If a required sensor is unavailable, these sensors become unavailable and expose the reason in their `warnings` attributes. This is intentional: the integration does not guess a safe charging recommendation from missing input.

## Charging modes

Initial mode model:

- `off`: no automatic charging
- `now`: immediate charging within configured limits
- `smart`: surplus, selected price strategy, and charge plan
- `always_charge`: keep a minimum current and add surplus

## Validation rules

The menu warns or blocks on:

- missing required sensors
- non-numeric sensor values where power or energy is required
- maximum current below minimum current
- unsupported phase count
- target SOC below current SOC
- battery discharge modes without battery SOC mapping
- wallbox control entities without a safe fallback mode
- a loaded JSON whose schema is newer than the running app
