# Prioritized TODOs

Agreed scope and coverage gaps: [FUNKTIONSPLAN.md](FUNKTIONSPLAN.md).
Configuration menu: [CONFIGURATION.md](CONFIGURATION.md).
Backup format: [BACKUP.md](BACKUP.md).

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
- [x] Add cloud smoothing filter for forecast/current fluctuations. The published surplus current stays raw; only the wallbox command is smoothed.
- [x] Add fallback behavior for missing PV, grid, or wallbox state.
- [x] Add service tests with mocked Home Assistant state.

## P3 - Guided configuration, charge plan, and backup

- [x] Replace the single options form with the step menu.
- [x] Test each mapped entity and show loaded, missing, stale, or invalid.
- [x] Preview raw and normalized values without writing to devices.
- [x] Allow JSON save and load on every step, then retest after load.
- [x] Add the single vehicle profile and target SOC persistence.
- [x] Add modes, always charge, and solar share as entities.
- [x] Add departure, weekly schedule, and late-charging window.
- [x] Add selectable forecast-only and forecast-plus-price strategies.
- [x] Persist a daily forecast-versus-actual sample for the summed PV power.
- [x] Split the learned forecast factor by PV source. A source applies only after seven samples; otherwise the site factor remains.
- [x] Expose learned correction and the good/bad band.
- [x] Add today and tomorrow chargeable-energy sensors.
- [x] Add battery and vehicle full times for plan target and theoretical full.
- [x] Mark unplugged vehicle results as assumptions.
- [x] Add the minimum-power hint and zero-export diagnostic.
- [x] Add efficiency, minimum reserve, night reserve, and feasibility sensors.
- [x] Recommend car surplus only above priority SOC and battery support down to the buffer.
- [x] Add schema version 1 JSON export and import, with a migration test.
- [ ] Keep inverter battery modes advisory until version 0.5. The battery is evaluated, not switched.

## P4 - Battery strategy control

- [ ] Map optional inverter services for hold, discharge lock, and grid charge.
- [ ] Apply priority SOC, buffer, and boost only when those services exist.
- [ ] Stop grid charging at max SOC.
- [x] Add the balancing reminder. Text only. It does not write to the inverter.

## P5 - Responsive panel

- [x] Add custom panel WebSocket commands.
- [x] Build the phone and desktop energy-flow and two-day forecast view.
- [ ] Move the step menu into the panel. JSON save and load are already there. The panel only shows the saved step name.
- [x] Add weekly plan editing in the panel. Departure can already be stored.
- [ ] Verify the main column at 360 pixels in a running Home Assistant. The stylesheet stays one column below 720 pixels.

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
