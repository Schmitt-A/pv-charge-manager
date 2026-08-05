# Configuration Model

PV Charge Manager is configured through the Home Assistant config and options
flows. The example YAML in `examples/configuration.yaml` documents the data
model and entity naming, not a production YAML interface.

After the integration is installed, open its `Configure` action and map the
entities used by the calculation. A valid calculation needs at least one PV
power sensor and either a home-consumption sensor or both grid import and grid
export sensors.

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

The correction factor is applied to future forecast values before the optimizer
selects charge windows. Runtime persistence and per-source observation capture
are planned for version 0.4. Recommended defaults:

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

If a required sensor is unavailable, these sensors become unavailable and expose
the reason in their `warnings` attributes. This is intentional: the integration
does not guess a safe charging recommendation from missing input.

## Charging modes

Initial mode model:

- `off`: no automatic charging
- `now`: immediate charging within configured limits
- `pv_surplus`: charge only from calculated PV surplus
- `pv_minimum`: keep a minimum current and add surplus
- `target_time`: calculate latest start to reach target SOC
- `forecast_optimized`: distribute charging into forecast windows

## Validation rules

The options flow should reject or warn about:

- missing required sensors
- non-numeric sensor values where power or energy is required
- maximum current below minimum current
- unsupported phase count
- target SOC below current SOC
- battery discharge modes without battery SOC mapping
- wallbox control entities without a safe fallback mode
