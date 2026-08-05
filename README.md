# PV Charge Manager

PV Charge Manager is a Home Assistant custom integration for PV-aware EV
charging. It is planned as a focused alternative to EVCC for one specific Home
Assistant installation with multiple PV systems, different feed-in tariffs,
solar forecast data, a battery, wallbox control, and vehicle charging plans.

Repository: <https://github.com/Schmitt-A/pv-charge-manager>

## Status

This repository is ready for Codex-based development and early local testing.
It is not yet production-ready for unattended wallbox control.

Implemented now:

- Home Assistant custom integration skeleton
- config flow entry point
- manifest metadata for `Schmitt-A/pv-charge-manager`
- pure Python calculation modules
- tests for surplus, vehicle demand, tariff allocation, learned forecast
  correction, and charging window planning
- ruff, pytest, pre-commit, and GitHub Actions configuration
- architecture, configuration, roadmap, and task documentation

Planned next:

- full entity mapping through options flow
- coordinator-backed runtime state
- sensor, number, select, switch, button entities
- wallbox safety limits and current control
- custom Home Assistant frontend panel

## Installation for Home Assistant

For manual testing, copy this directory into your Home Assistant configuration:

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
  config_flow.py   Home Assistant config flow
  manifest.json    Integration metadata
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
integration keeps historic forecast-vs-actual observations and learns a bounded
correction factor. If the forecast was too low and the real yield was higher, the
future planning forecast is adjusted upward. If the forecast was too high, it is
adjusted downward. This corrected forecast is the intended input for charge-plan
optimization.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Configuration model](docs/CONFIGURATION.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [Prioritized TODOs](docs/TODO.md)

## License

MIT. See [LICENSE](LICENSE).
