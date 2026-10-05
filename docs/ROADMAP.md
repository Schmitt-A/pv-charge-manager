# Roadmap

The agreed scope is one wallbox, one home battery, and one vehicle. Measurements
come only from Home Assistant entities and devices. Configuration is a separate
step menu with a live data preview and JSON save/load on every step. See
[CONFIGURATION.md](CONFIGURATION.md). Heating, smart plugs, heat pumps, and
extra charge points are out of the next slice. Battery strategy is calculated
now and applied to the inverter only in a later version. See
[FUNKTIONSPLAN.md](FUNKTIONSPLAN.md).

## Version 0.1 - Energy monitor

Goal: installable integration that reads mapped entities and exposes useful
derived sensors without controlling the wallbox.

- config flow entry
- options flow for grid, home, PV, battery, and forecast entity mapping
- coordinator state snapshot with 30-second refresh
- surplus power sensor
- recommended current and charge power sensors
- opportunity cost sensor
- diagnostics and warning attributes for missing or invalid input
- tests for core calculations

## Version 0.2 - Wallbox control

Goal: controlled PV surplus charging with conservative hardware safety rules.

- wallbox entity mapping
- start/stop control
- current setpoint control
- minimum runtime
- stop delay
- start delay and stable-surplus debounce
- cloud smoothing filter
- fallback behavior for unavailable sensors
- manual override handling

## Version 0.3 - Guided setup and charge plans

Goal: one vehicle profile and a charge plan, without new inverter writes.

- step menu for site, PV, battery, forecast, wallbox, vehicle, and review
- immediate connection test with raw and normalized preview
- hints for loaded, missing, stale, and invalid values
- JSON save and load on every step, followed by a retest
- vehicle profile: capacity, phases, current limits, wallbox-to-battery efficiency
- SOC mapping, with estimated SOC marked between polls
- modes off, smart, and now
- always-charge switch and solar-share setpoint
- target SOC or session energy goal
- departure time and one weekly schedule
- late-charging window before departure
- selectable strategy: forecast only, or forecast plus dynamic price
- continuous block, or cheapest slots when a price series exists
- session energy and PV share
- JSON backup export and import for schema version 1

## Version 0.4 - Forecast preview

Goal: show what today and tomorrow can charge, and when battery or car reach
the selected target.

- quarter-hour or hourly forecast slots
- learned forecast correction per PV source, with a minimum sample threshold
- good and bad forecast band, earliest and latest full time
- today and tomorrow chargeable energy, split after battery priority
- plan target and theoretical full, both visible
- unplugged car preview marked as an assumption
- minimum-power hint: possible, brief, or never
- zero-export balance fallback and minimum battery reserve
- surplus-to-car recommendation only above priority SOC
- battery-support recommendation down to the buffer limit
- night-reserve recommendation and morning SOC
- target-time feasibility, including the bad forecast case
- household consumption baseline

## Version 0.5 - Battery strategy control

Goal: apply the calculated storage strategy when the inverter exposes the
required services.

- priority SOC, charge buffer, and boost release
- discharge lock during immediate and planned grid charging
- grid charging up to max SOC when the price is under the limit
- balancing reminder
- no write when the inverter capability is unknown

## Version 0.6 - Responsive panel

Goal: a phone and desktop sidebar panel. It does not own charging state.

- energy flow for grid, PV, home, battery, and wallbox
- two-day forecast with the good and bad band
- visible priority, buffer, and reserve limits
- the same step menu, preview, and JSON actions
- vehicle and charge plan editor
- recommendation text for surplus start and battery support
- stacked layout at 360 pixels, Home Assistant light and dark theme
- diagnostics page with the decision reason
- WebSocket commands

## Later

- 1/3 phase switching when the wallbox supports it
- site offset for a small export setpoint
- vehicle wakeup and range sensor
- grid-fee adders and fixed time-window prices
- capacity-weighted average for multiple home batteries
- battery export-to-grid mode
- session statistics beyond the current session
- seasonal forecast correction
- heating, smart plugs, and heat pumps
- second charge point, circuit limits, and CO2 optimization
- advisory whole-home optimizer
