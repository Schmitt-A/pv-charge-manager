# Codex instructions for PV Charge Manager

## Project intent

PV Charge Manager is a Home Assistant custom integration for PV-aware EV charging.
The repository is intentionally structured so Codex can work on it without needing
a running Home Assistant instance for every change.

## Repository map

- `custom_components/pv_charge_manager/` contains the Home Assistant integration.
- `apps/pv_charge_manager_installer/` contains the Home Assistant OS app
  installer. It must remain a narrow installer and must not control hardware.
- `custom_components/pv_charge_manager/calculation.py`, `allocation.py`,
  `forecast.py`, and `optimizer.py` contain pure Python domain logic.
- `tests/` covers the pure Python logic and should remain fast and independent.
- `docs/` contains architecture, setup, configuration, roadmap, and task notes.
- `examples/` contains Home Assistant-oriented example configuration.

## Development commands

Use these commands from the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pre-commit install
ruff check .
ruff format --check .
pytest
```

If Home Assistant runtime behavior is changed, also install the optional HA
dependencies:

```bash
python -m pip install -e ".[dev,ha]"
```

## Working rules

- Keep Home Assistant imports out of pure domain modules so tests can run quickly.
- Prefer small functions with explicit units in names, for example `_w`, `_kwh`,
  `_eur_per_kwh`, and `_a`.
- Do not hard-code entity IDs for a private installation. Put examples in
  `examples/` and make runtime mapping configurable through config/options flows.
- Add or update tests for calculation, allocation, forecast, and optimizer changes.
- Treat learned forecast correction as core planning behavior: charge planning
  should use calibrated forecast values once enough forecast-vs-actual history
  exists.
- Treat `manifest.json` and translations as user-facing release metadata.
- Keep README content aligned with the current implementation status. Do not claim
  production-ready charging control before wallbox safety logic is implemented.
- The app installer downloads the integration from the public `main` branch and
  writes to the mapped Home Assistant config directory. Keep its permissions and
  network behavior explicit in the app documentation.

## Current status

This is an early development repository. The Home Assistant integration shell is
installable, but the production control loop and full UI are roadmap items.
