# Integration package instructions

## Scope

This package must stay compatible with Home Assistant custom integration loading.
Files in this directory are shipped to:

```text
/config/custom_components/pv_charge_manager/
```

## Design boundaries

- Home Assistant platform files may import Home Assistant APIs.
- Domain logic modules should not import Home Assistant.
- Use config flow and options flow for entity mapping; avoid YAML-only setup.
- Avoid direct device assumptions. Wallbox, vehicle, PV, grid, forecast, and
  battery entities must be selectable.
- Wallbox control is disabled by default. Do not add a service call that bypasses
  `wallbox.py` validation, debounce, minimum runtime, or manual override.

## Safety notes

Charging control can affect real hardware. Any future service or switch that
starts, stops, or changes current must include validation, min/max limits, and
clear fallback behavior when required sensors are unavailable.
