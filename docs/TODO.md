# Prioritized TODOs

Agreed scope and coverage gaps: [FUNKTIONSPLAN.md](FUNKTIONSPLAN.md).

## P0 - Repository readiness

- [x] Add Codex instructions.
- [x] Add pyproject, ruff, pytest, and pre-commit configuration.
- [x] Add CI workflow.
- [x] Add initial tests for pure calculations.
- [x] Update manifest URLs to `Schmitt-A/pv-charge-manager`.

## P1 - Installable integration MVP

- [x] Implement options flow for entity mapping.
- [x] Build coordinator state snapshot from Home Assistant states.
- [x] Add sensors for surplus, recommended current, and opportunity cost.
- [x] Add diagnostics for unavailable or invalid sensors.
- [x] Add validation and warning messages for unsafe configuration.

## P2 - Safe wallbox control

- [x] Define wallbox adapter abstraction for Home Assistant entities.
- [x] Add current limit validation.
- [x] Add start/stop debounce and minimum runtime.
- [ ] Add cloud smoothing filter for forecast/current fluctuations.
- [x] Add fallback behavior for missing PV, grid, or wallbox state.
- [x] Add service tests with mocked Home Assistant state.

## P3 - Charge plan and preview

- [ ] Add the single vehicle profile and target SOC persistence.
- [ ] Add modes, always charge, and solar share as entities.
- [ ] Add departure, weekly schedule, and late-charging window.
- [ ] Add selectable forecast-only and forecast-plus-price strategies.
- [ ] Persist historic forecast-vs-actual observations per PV source.
- [ ] Expose learned correction and the good/bad band.
- [ ] Add today and tomorrow chargeable-energy sensors.
- [ ] Add battery and vehicle full times for plan target and theoretical full.
- [ ] Mark unplugged vehicle results as assumptions.
- [ ] Add the minimum-power hint and zero-export diagnostic.
- [ ] Add efficiency, minimum reserve, night reserve, and feasibility sensors.
- [ ] Keep inverter battery modes advisory until version 0.5.

## P4 - Battery strategy control

- [ ] Map optional inverter services for hold, discharge lock, and grid charge.
- [ ] Apply priority SOC, buffer, and boost only when those services exist.
- [ ] Stop grid charging at max SOC.
- [ ] Add the balancing reminder.

## P5 - Panel

- [ ] Add custom panel WebSocket commands.
- [ ] Build the two-day forecast and charge-plan panel.

## Backlog

- [ ] HACS release automation.
- [ ] 1/3 phase switching and site export offset.
- [ ] Vehicle wakeup and range sensor.
- [ ] Grid-fee adders and fixed time-window prices.
- [ ] Multiple home batteries and export-to-grid mode.
- [ ] Statistics beyond the current session.
- [ ] Historical forecast correction by season, weather class, weekday, and time of day.
- [ ] Heating, extra charge points, circuit limits, and CO2 optimization.
- [ ] Documentation screenshots once the UI exists.
