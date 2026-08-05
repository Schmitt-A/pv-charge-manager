# PV Charge Manager

PV Charge Manager is a Home Assistant custom integration for PV-aware EV
charging. It is planned as a focused alternative to EVCC for one specific Home
Assistant installation with multiple PV systems, different feed-in tariffs,
solar forecast data, a battery, wallbox control, and vehicle charging plans.

Repository: <https://github.com/Schmitt-A/pv-charge-manager>

## Status

This repository is ready for Codex-based development and early Home Assistant
testing. It is not yet production-ready for unattended wallbox control.

Implemented now:

- Home Assistant custom integration skeleton
- config flow and options flow for entity mapping and electrical limits
- coordinator-backed runtime snapshot with conservative unavailable-state handling
- sensors for PV surplus, recommended current, recommended charge power, and
  opportunity cost
- manifest metadata for `Schmitt-A/pv-charge-manager`
- pure Python calculation modules
- tests for surplus, vehicle demand, tariff allocation, learned forecast
  correction, and charging window planning
- ruff, pytest, pre-commit, and GitHub Actions configuration
- architecture, configuration, roadmap, and task documentation

Planned next:

- wallbox safety limits and current control
- custom Home Assistant frontend panel

## Installation for Home Assistant

### Home Assistant OS app repository

This is the simplest installation path for Home Assistant OS. Home Assistant
apps are not available with Home Assistant Container, Core, or supervised
installations.

1. Open `Settings -> Apps -> Install app`.
2. Open the three-dot menu and select `Repositories`.
3. Add this repository URL:

   ```text
   https://github.com/Schmitt-A/pv-charge-manager
   ```

4. Install `PV Charge Manager integration` and start it once.
5. Restart Home Assistant.
6. Open `Settings -> Devices & services -> Add integration` and select `PV Charge Manager`.
7. Open the integration options and map the PV, home-consumption, grid, and
   optional battery sensors.

The installer app downloads the current `main` branch and writes only the
integration directory below the Home Assistant configuration directory. After
an app update, restart the app and then Home Assistant. Do not install the same
integration through both this app and HACS at the same time.

### HACS

For Home Assistant Container, Core, or supervised installations, add this
repository as a custom HACS integration repository:

```text
https://github.com/Schmitt-A/pv-charge-manager
```

Then download `PV Charge Manager` under `HACS -> Integrations` and restart
Home Assistant.

### Manual installation

Copy this directory into your Home Assistant configuration:

```text
custom_components/pv_charge_manager/
```

Target path:

```text
/config/custom_components/pv_charge_manager/
```

Restart Home Assistant and add the integration through:

```text
Settings -> Devices & services -> Add integration -> PV Charge Manager
```

### Important limitation

The app repository is a convenience installer for Home Assistant OS. It does
not run a separate forecasting service and it does not control the wallbox. The
forecast learning model and charge planning are currently pure, testable domain
logic; persistence and runtime integration are planned in the roadmap.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pre-commit install
```

Run checks:

```bash
ruff check .
ruff format --check .
pytest
```

For Home Assistant runtime work:

```bash
python -m pip install -e ".[dev,ha]"
```

## Project layout

```text
custom_components/pv_charge_manager/
  calculation.py   Pure surplus and vehicle energy calculations
  allocation.py    Economic allocation by feed-in tariff
  forecast.py      Forecast correction helpers
  optimizer.py     Charging window planning helpers
  config_flow.py   Home Assistant config and options flows
  coordinator.py   State snapshot and derived runtime values
  sensor.py        Initial calculated sensors
  manifest.json    Integration metadata
apps/
  pv_charge_manager_installer/  Home Assistant OS app installer
docs/
  ARCHITECTURE.md
  CONFIGURATION.md
  DEVELOPMENT.md
  ROADMAP.md
  TODO.md
examples/
  configuration.yaml
tests/
```

## Core idea

PV Charge Manager calculates how much power can be used for EV charging without
violating local priorities:

```text
available charging power =
PV production
- home consumption
- planned battery charging
- safety reserve
```

When several PV systems have different feed-in tariffs, the integration uses
economic allocation for reporting and decisions. The source with the lowest
opportunity cost is assigned to EV charging first. This is a balance-sheet model;
physical electrons are not routed by inverter.

For solar forecast planning, the raw forecast should not be trusted blindly. The
domain model keeps historic forecast-vs-actual observations and learns a bounded
correction factor. If the forecast was too low and the real yield was higher, the
future planning forecast is adjusted upward. If the forecast was too high, it is
adjusted downward. This corrected forecast is the intended input for charge-plan
optimization. Persisting observations per PV source is a later roadmap item.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Configuration model](docs/CONFIGURATION.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [Prioritized TODOs](docs/TODO.md)

## License

MIT. See [LICENSE](LICENSE).
