# Backup and restore

Settings and learned state are portable JSON. A backup from an older app version must load in a newer version. Home Assistant backups remain separate; this file is the app-level copy that can be downloaded and read back in.

The configuration menu can save or load this file at every step, including an unfinished draft.

## Document

```json
{
  "schema_version": 1,
  "app_version": "0.4.0",
  "exported_at": "2026-10-05T21:40:00+02:00",
  "step": "battery",
  "settings": {},
  "plans": [],
  "entity_map": {},
  "learning": {}
}
```

`schema_version` is the only migration key. `app_version` is informational. `step` restores the menu position.

Included:

- vehicle profile, efficiencies, limits
- mode, solar share, always charge, strategy
- priority SOC, buffer, minimum reserve, max SOC, boost limit
- departure, weekly plan, late-charging window, price limit
- entity IDs for grid, home, PV, battery, forecast, price, wallbox, and vehicle
- learned forecast correction and the sample count per PV source
- incomplete draft steps

Excluded:

- tokens, passwords, and Home Assistant secrets
- live sensor values and raw history
- the current wallbox setpoint

## Versions

- Import accepts every `schema_version` up to the running app.
- Unknown future versions are rejected with the required app version.
- Each shipped schema has one migration step from the previous schema.
- Migrations are pure functions and keep the original file unchanged until import succeeds.
- Missing fields receive the current default and are listed in the import report.
- Entity IDs that no longer exist are kept and marked missing. They are not silently dropped.
- After import, every mapped entity is tested again before the menu continues.

## Entry points

- Save and load on every configuration step.
- Services `export_backup` and `import_backup`.
- Panel actions download and upload the same JSON.
- A copy can also be written under the Home Assistant config directory, outside the integration source tree.
