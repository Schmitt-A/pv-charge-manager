# Prioritized TODOs

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

## P3 - Planning and UI

- [ ] Add vehicle profiles and target SOC persistence.
- [ ] Add charge plan entity model.
- [ ] Add forecast optimizer using corrected real forecast slots.
- [ ] Persist historic forecast-vs-actual observations.
- [ ] Expose learned forecast correction factor per PV source.
- [ ] Connect forecast observations to the coordinator and charge-plan inputs.
- [ ] Add custom panel WebSocket commands.
- [ ] Build first operational Home Assistant panel.

## Backlog

- [ ] HACS release automation.
- [ ] Dynamic tariff source support.
- [ ] Multi-vehicle queueing.
- [ ] Historical forecast correction by season, weather class, weekday, and time of day.
- [ ] Documentation screenshots once the UI exists.
