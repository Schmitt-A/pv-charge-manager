# Development Guide

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pre-commit install
```

## Checks

```bash
ruff check .
ruff format --check .
pytest
```

## Home Assistant runtime work

Install optional Home Assistant dependencies only when you need to run the
integration inside a local Home Assistant environment:

```bash
python -m pip install -e ".[dev,ha]"
```

Copy or symlink the custom integration into a Home Assistant config directory:

```text
/config/custom_components/pv_charge_manager/
```

The Home Assistant OS app installer lives in
`apps/pv_charge_manager_installer/`. It is intentionally tested as a repository
structure and shell script, while the actual integration behavior remains in
`custom_components/pv_charge_manager/`.

## Coding conventions

- Use explicit units in names.
- Keep Home Assistant API calls in integration-facing files.
- Keep calculation modules pure and testable.
- Add tests for every behavior change in pure domain logic.
- Keep wallbox writes behind validation and a mode check.

## Release checklist

Before tagging a release:

1. `ruff check .`
2. `ruff format --check .`
3. `pytest`
4. Update `custom_components/pv_charge_manager/manifest.json`.
5. Update `README.md` status and installation notes.
6. Update `apps/pv_charge_manager_installer/config.yaml` when the installer
   behavior or supported Home Assistant version changes.
7. Update `docs/ROADMAP.md` and `docs/TODO.md`.
8. Create a GitHub release with a clear Home Assistant compatibility note.
