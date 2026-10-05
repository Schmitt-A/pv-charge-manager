# Umsetzungsplan

Stand: 2026-10-05. Dieser Plan beschreibt die nächsten Codeänderungen. Der fachliche Umfang bleibt [FUNKTIONSPLAN.md](FUNKTIONSPLAN.md).

Jeder Schritt ist ein eigener Commit, bleibt ohne Home Assistant lauffähig testbar, und ändert die Wallbox-Entscheidung erst, wenn die neuen Sensoren stimmen.

Schritte 1 bis 7 sind umgesetzt. Der Wallbox-Sollwert bleibt `recommended_current_a`. Offen sind danach nur noch die Punkte unter „Ausdrücklich später“ und die nicht abgehakten Einträge in [TODO.md](TODO.md).

## Ist-Stand

Bereits verdrahtet:

- [config_flow.py](../custom_components/pv_charge_manager/config_flow.py) legt nur den Namen an. Die Optionen laufen in den Schritten `site`, `pv`, `battery`, `forecast`, `wallbox`, `vehicle` und `review`. Jeder Schritt prüft die zugeordneten Entitäten, zeigt Rohwert und normalisierten Wert und kann JSON laden oder speichern. Die Prüfung schreibt nicht an Wallbox oder Wechselrichter.
- [coordinator.py](../custom_components/pv_charge_manager/coordinator.py) liest PV, Hauslast, Batterieladeleistung und Wallbox. Er rechnet Überschuss, Strom, Leistung und Opportunitätskosten. Liegt eine lesbare Prognose vor, hängt er die Tagesvorschau an: heute, morgen, Vollladezeiten im guten und schlechten Fall, Planstatus und die Batterie-Empfehlung. Unter sieben Lernproben bleibt der Faktor 1. Die Wallbox wird nur bei `wallbox_control_enabled` geschrieben. Der Sollwert bleibt `recommended_current_a`.
- [sensor.py](../custom_components/pv_charge_manager/sensor.py) veröffentlicht Überschuss, Sollwert und die Tagesvorschau.
- [calculation.py](../custom_components/pv_charge_manager/calculation.py), [forecast.py](../custom_components/pv_charge_manager/forecast.py), [optimizer.py](../custom_components/pv_charge_manager/optimizer.py), [preview.py](../custom_components/pv_charge_manager/preview.py), [backup.py](../custom_components/pv_charge_manager/backup.py), [probe.py](../custom_components/pv_charge_manager/probe.py), [setup_draft.py](../custom_components/pv_charge_manager/setup_draft.py) und [wallbox.py](../custom_components/pv_charge_manager/wallbox.py) sind reine Module mit Tests.
- [storage.py](../custom_components/pv_charge_manager/storage.py) hält Fahrzeug, Plan, Lernzustand und den Backup-Entwurf unter `pv_charge_manager.{entry_id}`.
- [controls.py](../custom_components/pv_charge_manager/controls.py) prüft Modus, Strategie, Solaranteil, Ziel, Priorität, Puffer, Mindestreserve, Preisgrenze und Immer laden. Die Werte liegen im Store. `select.py`, `number.py`, `switch.py` und `button.py` speichern sie und rechnen neu. Die Wallbox-Steuerung bleibt in den Optionen. Der Sollwert bleibt `recommended_current_a`. Aus lädt das Auto in der Vorschau nicht. Sofort nimmt die volle Leistung. Der Solaranteil ändert die Mindestleistungs-Schwelle. Die Preisgrenze entscheidet, welche Stunde günstig ist.
- [__init__.py](../custom_components/pv_charge_manager/__init__.py) lädt den Store vor dem Coordinator, registriert `export_backup`, `import_backup` und `recalculate` und hängt das Panel in die Seitenleiste. `start_boost` schreibt nur eine Warnung.
- [panel.py](../custom_components/pv_charge_manager/panel.py) baut die Übersicht aus dem Coordinator-Stand und dem Store. [frontend/pv-charge-manager.js](../custom_components/pv_charge_manager/frontend/pv-charge-manager.js) zeigt Satz, Fluss, zwei Tageskarten, die Regler, die Probe-Hinweise und die JSON-Schaltflächen. Der Browser rechnet keinen Plan. `websocket.py` liefert den Snapshot und speichert eine Regleränderung.

Vorhanden, aber nicht angeschlossen:

- `ForecastCalibration` sammelt noch keine neuen Stichproben. Der Coordinator wendet nur einen bereits gespeicherten Faktor an, und erst ab sieben Proben.
- `binary_sensor.py` ist ein leerer Platzhalter.
- Es gibt einen gemeinsamen Einspeisetarif, keine Tarife je PV-Quelle.

## Schritt 1: Vorschau als reines Modul

Neue Datei `preview.py`. Kein Home Assistant.

Eingabe:

- Slots mit Start, Ende, PV-Leistung, Hauslast.
- Batterie: SOC, Kapazität, maximale Ladeleistung, Wirkungsgrad, Prioritäts-SOC, Puffergrenze, Mindestreserve, Max-SOC.
- Fahrzeug: Kapazität, SOC oder angenommener SOC, Ziel-SOC, Wirkungsgrad, `ChargeLimits`.
- Faktor für den guten und den schlechten Fall.

Ausgabe je Tag und je Fall:

- ladbare kWh
- Energie bis Prioritäts-SOC, Rest fürs Fahrzeug
- Zeitpunkt voll für Plan-Ziel und für Max-SOC beziehungsweise 100 Prozent
- erreichbarer SOC und fehlende kWh, wenn der Tag nicht reicht
- Mindestleistung: `possible`, `brief` oder `never`
- Empfehlungstext: Überschuss ans Auto erst ab Prioritäts-SOC, Batteriestützung nur bis zur Puffergrenze

Die Füllung eines Slots ist `min(PV - Hauslast - Reserve, maximale Ladeleistung) * Wirkungsgrad`. Zuerst Batterie bis Prioritäts-SOC, dann Fahrzeug. Tests in `tests/test_preview.py`: Tag reicht, Tag reicht nicht, kein Slot über der Mindestleistung, Auto unverbunden mit Annahme-Flag, guter Fall liegt nicht nach dem schlechten.

`optimizer.py` bleibt für die Slotauswahl nach Preis. Die Vorschau ruft ihn nicht um. Der Plan benutzt `build_charge_plan`, nachdem die Batterie ihren Anteil aus den Slots abgezogen hat.

## Schritt 2: Backup als reines Modul

Neue Datei `backup.py`.

- `export_document(state) -> dict` mit `schema_version: 1`.
- `import_document(payload) -> ImportResult` mit migriertem Zustand, Warnungen und dem gespeicherten Schritt.
- Schema 1 enthält Optionen, Fahrzeugprofil, Plan, Entitätszuordnung, Lernfaktor und `step`.
- Eine neuere Schema-Nummer wirft `UnsupportedSchema`.
- Migration ist eine Funktion `migrate(document, target_version)`, auch wenn von 1 nach 1 nur die Identität ist.

Tests: rundes Speichern und Laden, fehlendes Feld bekommt den Default und eine Warnung, Schema 99 wird abgelehnt, Geheimnisfelder werden beim Export entfernt.

## Schritt 3: Speicher und Dienste

`storage.py` um einen `Store`-Helfer erweitern, Schlüssel `pv_charge_manager.{entry_id}`.

Gespeichert wird nur, was der Coordinator nicht aus den Entitäten neu lesen kann: Fahrzeugprofil, Plan, Lernzustand, Backup-Entwurf.

In `__init__.py`:

- Store laden, bevor der Coordinator startet.
- Dienste `export_backup` und `import_backup` registrieren. `import_backup` nimmt den JSON-Text, ruft `import_document` und speichert das Ergebnis.
- `recalculate` ruft `coordinator.async_request_refresh()`.
- `start_boost` bleibt ohne Wirkung und schreibt nur eine Warnung, bis Schritt 7 den Boost wirklich setzt.

Test mit gemocktem Store: Export nach Import ergibt denselben Zustand.

## Schritt 4: Konfiguration in Schritten

`config_flow.py` bleibt der Einstieg. `PVChargeManagerOptionsFlow` bekommt die Schritte `site`, `pv`, `battery`, `forecast`, `wallbox`, `vehicle`, `review`.

Jeder Schritt:

- speichert seinen Teil in `self._draft`
- bietet die bisherigen Werte als Default
- hat die Beschreibungen `save_json` und `load_json` als optionale Textfelder
- ruft nach Submit `probe_entities` auf

Neue Datei `probe.py`. Sie bekommt ein schmales Zustandsobjekt, nicht `hass`, damit sie ohne Home Assistant testbar ist. Ergebnis je Entität: `loaded`, `missing`, `stale`, `invalid` oder `optional_empty`, plus Rohwert und normalisierter Wert. Der Flow übersetzt `hass.states` in dieses Objekt. Der Schritt zeigt die Hinweise als Formularbeschreibung und blockiert nur fehlende Pflichtfelder.

JSON in jedem Schritt: `load_json` ersetzt den Entwurf über `import_document` und setzt `step` zurück. `save_json` ist ein nur lesbares Feld mit dem aktuellen `export_document`. Home Assistant kann in einem Options Flow keine Datei herunterladen. Der echte Download sitzt im Panel. Bis dahin ist der Text im Formular und der Dienst `export_backup` der gleiche Inhalt.

Nach dem letzten Schritt schreibt der Flow wie bisher `async_create_entry` mit den normalisierten Optionen. Fahrzeugprofil und Plan gehen in den Store, nicht in die Options, weil die Options kein freies JSON halten sollen.

Tests: Draft überlebt den Schritt, ungültige Phase blockiert, geladenes JSON mit unbekannter Entität setzt `missing` und verwirft die ID nicht.

## Schritt 5: Coordinator liest Prognose und Plan

In `coordinator.py` nach der bestehenden Überschussrechnung:

- Prognoseentitäten lesen. Erwartet wird eine kommaseparierte oder JSON-Liste von Leistungen, sonst eine einzelne Leistungszahl. Unlesbar ergibt `forecast_unavailable`, nicht einen erfundenen Slot.
- `ForecastCalibration` aus dem Store anwenden. Unter sieben Stichproben bleibt der Faktor 1 und das Attribut `forecast_trust` ist `low`.
- Slots für heute und morgen bauen. Hauslast ist der aktuelle Wert, solange keine Basislinie existiert.
- `preview.py` aufrufen.
- Wenn ein Plan im Store liegt, `required_vehicle_energy_kwh` und danach `build_charge_plan` auf dem Rest nach der Batteriepriorität.
- Ergebnis in `coordinator.data` legen. Der Wallbox-Sollwert bleibt der bisherige `recommended_current_a`.

Neue Sensoren in `sensor.py`, nur wenn der Schlüssel existiert. Fehlende Prognose macht diese Sensoren `unavailable`, nicht die vorhandenen Überschusssensoren.

Mindestens:

- `battery_full_at`, `battery_full_at_early`, `battery_full_at_late`
- `vehicle_full_at` mit Attribut `assumption`
- `chargeable_kwh_today`, `chargeable_kwh_tomorrow`
- `plan_status`: `feasible`, `needs_grid`, `infeasible`
- `minimum_power_today`
- `battery_recommendation`

`tests/test_coordinator_runtime.py` um einen Fall mit Prognoseliste und einen ohne Prognose erweitern.

## Schritt 6: Eingabeentitäten

Die Platzhalter befüllen, ohne neue Steuerung:

- `select.py`: Modus `off`, `smart`, `now`. Strategie `forecast`, `forecast_price`.
- `number.py`: Solaranteil, Ziel-SOC, Prioritäts-SOC, Puffer, Mindestreserve, Preisgrenze.
- `switch.py`: Immer laden. Steuerung-aktiv bleibt in den Optionen, damit er nicht versehentlich im Dashboard umgelegt wird.
- `button.py`: Plan neu rechnen, ruft denselben Dienst wie `recalculate`.

Werte landen im Store und lösen `async_request_refresh` aus. Tests prüfen nur die reine Zustandsklasse, nicht die Home-Assistant-Entity.

## Schritt 7: Panel

Erst wenn Schritt 4 bis 6 Sensoren und JSON liefern.

`frontend/pv-charge-manager.js` wird ein Panel: Energiefluss aus den vorhandenen Sensoren, zwei Tageskarten, Hinweise aus `probe`, JSON-Schaltflächen über die Dienste. `websocket.py` liefert dafür den Snapshot aus `coordinator.data` und dem Store. Keine zweite Rechnung im Browser.

Layout: eine Spalte unter 360 Pixel, Home-Assistant-Theme, keine eigene Farbwelt.

## Ausdrücklich später

Nicht in Schritt 1 bis 7:

- Schreiben von Entladesperre, Netzladung, Boost oder Puffer an den Wechselrichter.
- Änderung der Wallbox-Sollwertlogik.
- Heizstab, zweite Wallbox, CO2, Phasenwechsel.
- Mehrere Tarife je PV-Quelle. Das vorhandene eine Tariffeld bleibt, bis `allocation.py` je Quelle einen Tarif aus den Optionen bekommt.

## Abnahme je Schritt

- `ruff check .`
- `ruff format --check .`
- `pytest`
- Ein Schritt gilt erst als fertig, wenn die neuen Tests ohne laufendes Home Assistant grün sind und die bisherigen Wallbox-Tests unverändert durchlaufen.
