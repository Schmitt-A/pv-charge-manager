/* Panel view. Numbers come from the snapshot. This file does not calculate a plan. */

const FLOW = [
  ["pv_w", "PV", "#E09F3E", "pv"],
  ["home_w", "Haus", "#8B909A", "home"],
  ["battery_w", "Batterie", "#1AAE9F", "battery"],
  ["car_w", "Auto", "#7A5AF8", "car"],
];

const SELECTS = [
  ["mode", "Modus", [["off", "Aus"], ["smart", "Intelligent"], ["now", "Sofort"]]],
  ["strategy", "Strategie", [["forecast", "Nur Prognose"], ["forecast_price", "Prognose und Preis"]]],
];

const DAYS = [
  ["mo", "Montag"],
  ["di", "Dienstag"],
  ["mi", "Mittwoch"],
  ["do", "Donnerstag"],
  ["fr", "Freitag"],
  ["sa", "Samstag"],
  ["so", "Sonntag"],
];

const NUMBERS = [
  ["target_soc", "Ziel des Autos", "Prozent", 1],
  ["priority_soc", "Priorität der Batterie", "Prozent", 1],
  ["buffer_soc", "Puffer", "Prozent", 1],
  ["reserve_soc", "Mindestreserve", "Prozent", 1],
  ["solar_share", "Solaranteil", "Prozent", 1],
  ["price_limit_eur", "Preisgrenze", "Euro je kWh", 0.01],
];

class PVChargeManagerPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._snapshot = null;
    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;
    if (!this._snapshot) {
      this._refresh();
    }
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="wrap"></div>`;
    this._root = this.shadowRoot.querySelector(".wrap");
    this._root.textContent = "Die Übersicht wird geladen.";
  }

  async _refresh() {
    if (!this._hass) return;
    try {
      this._snapshot = await this._hass.callWS({ type: "pv_charge_manager/snapshot" });
      this._draw();
    } catch (_err) {
      if (this._root) this._root.textContent = "Die Übersicht ist nicht erreichbar.";
    }
  }

  async _set(key, value) {
    if (!this._hass) return;
    const payload = { type: "pv_charge_manager/set_control", key, value };
    if (this._snapshot && this._snapshot.entry_id) payload.entry_id = this._snapshot.entry_id;
    try {
      this._snapshot = await this._hass.callWS(payload);
      this._draw();
    } catch (_err) {
      this._note("Der Wert wurde nicht übernommen.");
    }
  }

  _draw() {
    const snap = this._snapshot;
    if (!this._root || !snap) return;
    this._root.replaceChildren();
    this._root.append(heading(snap.sentence, "sentence"), heading(snap.detail, "detail"));
    if (snap.assumption) this._root.append(heading("Auto-Wert ist eine Annahme.", "detail"));
    this._root.append(facts(snap), flow(snap.flow), days(snap), controls(snap, (key, value) => this._set(key, value)));
    if (snap.recommendation) this._root.append(heading(snap.recommendation, "detail"));
    if (snap.balancing) this._root.append(heading(snap.balancing, "detail"));
    if (snap.night_reserve) this._root.append(heading(snap.night_reserve, "detail"));
    this._root.append(probe(snap.probe), backup(snap, this._hass, () => this._refresh()));
    if (snap.step) this._root.append(heading(`Gespeicherter Schritt: ${snap.step}`, "detail"));
  }

  _note(text) {
    if (!this._root) return;
    this._root.append(heading(text, "detail"));
  }
}

function heading(text, className) {
  const node = document.createElement("p");
  node.className = className;
  node.textContent = text || "";
  return node;
}

function facts(snap) {
  const grid = document.createElement("section");
  grid.className = "grid facts";
  grid.append(
    fact("Ladestand", percent(snap.flow.battery_soc)),
    fact("Heute ladbar", kwh(snap.days[0].chargeable_kwh)),
    fact("Morgen ladbar", kwh(snap.days[1].chargeable_kwh)),
    fact("Batterie voll", snap.battery_band),
    fact("Auto am Ziel", snap.vehicle_band),
  );
  return grid;
}

function fact(label, value) {
  const card = document.createElement("article");
  card.className = "card";
  const name = document.createElement("div");
  name.className = "muted";
  name.textContent = label;
  const number = document.createElement("div");
  number.className = "value";
  number.textContent = value;
  card.append(name, number);
  return card;
}

function flow(values) {
  const grid = document.createElement("section");
  grid.className = "grid flow";
  for (const [key, label, color, kind] of FLOW) {
    grid.append(strand(label, color, flowText(kind, values[key])));
  }
  grid.append(strand("Netzbezug", "#3D6BF5", watts(values.grid_import_w)));
  grid.append(strand("Einspeisung", "#3D6BF5", watts(values.grid_export_w)));
  return grid;
}

function strand(label, color, text) {
  const card = document.createElement("article");
  card.className = "card";
  const bar = document.createElement("div");
  bar.className = "bar";
  bar.style.background = color;
  const name = document.createElement("div");
  name.className = "muted";
  name.textContent = label;
  const number = document.createElement("div");
  number.className = "value";
  number.textContent = text;
  card.append(bar, name, number);
  return card;
}

function flowText(kind, value) {
  if (value == null) return "kein Wert";
  if (kind === "battery") return value > 0 ? `lädt ${watts(value)}` : "hält";
  if (kind === "car") return value > 0 ? watts(value) : "aus";
  return watts(value);
}

function days(snap) {
  const grid = document.createElement("section");
  grid.className = "grid days";
  for (const day of snap.days) {
    const card = document.createElement("article");
    card.className = "card";
    const title = document.createElement("div");
    title.className = "muted";
    title.textContent = day.title;
    const number = document.createElement("div");
    number.className = "value";
    number.textContent = kwh(day.chargeable_kwh);
    card.append(title, number);
    if (day.hint) card.append(heading(day.hint, "detail"));
    grid.append(card);
  }
  return grid;
}

function controls(snap, setControl) {
  const section = document.createElement("section");
  section.className = "grid";
  const values = snap.controls || {};
  for (const [key, label, options] of SELECTS) {
    const field = document.createElement("label");
    field.className = "card";
    field.append(heading(label, "muted"));
    const select = document.createElement("select");
    for (const [value, name] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = name;
      option.selected = values[key] === value;
      select.append(option);
    }
    select.addEventListener("change", () => setControl(key, select.value));
    field.append(select);
    section.append(field);
  }
  for (const [key, label, unit, step] of NUMBERS) {
    section.append(stepper(label, unit, values[key], step, (value) => setControl(key, value)));
  }
  section.append(stepper("Abfahrt", "Uhrzeit", values.departure || "", null, (value) => setControl("departure", value), true));
  section.append(stepper("Spätes Netzfenster", "Stunden vor Abfahrt, 0 löscht", values.late_hours || 0, 1, (value) => setControl("late_hours", value)));
  section.append(heading("Wochenplan. Ohne Eintrag ist jeder Tag offen. Ist ein Tag eingetragen, bleiben die anderen zu.", "detail"));
  const week = values.week || {};
  for (const [day, label] of DAYS) {
    const entry = week[day] || {};
    section.append(stepper(`${label} von`, "Uhrzeit", entry.start || "", null, (value) => setControl(`week_${day}_start`, value), true));
    section.append(stepper(`${label} bis`, "Uhrzeit", entry.end || "", null, (value) => setControl(`week_${day}_end`, value), true));
  }
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "card switch";
  toggle.setAttribute("aria-pressed", values.always_charge ? "true" : "false");
  toggle.textContent = values.always_charge ? "Immer laden: an" : "Immer laden: aus";
  toggle.addEventListener("click", () => setControl("always_charge", !values.always_charge));
  section.append(toggle);
  return section;
}

function stepper(label, unit, current, step, onCommit, text) {
  const field = document.createElement("label");
  field.className = "card stepper";
  field.append(heading(`${label}`, "muted"));
  const row = document.createElement("div");
  row.className = "row";
  const input = document.createElement("input");
  input.value = current == null ? "" : String(current);
  if (!text) input.inputMode = "decimal";
  const commit = () => onCommit(text ? input.value : Number(input.value));
  if (!text) {
    const down = document.createElement("button");
    down.type = "button";
    down.textContent = "−";
    down.addEventListener("click", () => onCommit(round(Number(current) - step, step)));
    const up = document.createElement("button");
    up.type = "button";
    up.textContent = "+";
    up.addEventListener("click", () => onCommit(round(Number(current) + step, step)));
    row.append(down, input, up);
  } else {
    row.append(input);
  }
  input.addEventListener("change", commit);
  const unitNode = document.createElement("span");
  unitNode.className = "muted";
  unitNode.textContent = unit;
  field.append(row, unitNode);
  return field;
}

function probe(rows) {
  const section = document.createElement("section");
  section.className = "card";
  section.append(heading("Verbindung", "muted"));
  if (!rows || !rows.length) {
    section.append(heading("Keine zugeordneten Entitäten.", "detail"));
    return section;
  }
  for (const row of rows) {
    const line = document.createElement("div");
    line.className = "detail";
    line.textContent = `${row.entity_id}: ${row.label} | ${row.raw} -> ${row.normalized}`;
    section.append(line);
  }
  return section;
}

function backup(snap, hass, refresh) {
  const section = document.createElement("section");
  section.className = "card";
  section.append(heading("Sicherung", "muted"));
  const area = document.createElement("textarea");
  area.rows = 6;
  area.value = snap.backup ? JSON.stringify(snap.backup, null, 2) : "";
  const row = document.createElement("div");
  row.className = "row";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "JSON speichern";
  save.addEventListener("click", async () => {
    const result = await callService(hass, "export_backup", { entry_id: snap.entry_id });
    const body = result && result.response ? result.response : result;
    if (body && body.schema_version) area.value = JSON.stringify(body, null, 2);
  });
  const load = document.createElement("button");
  load.type = "button";
  load.textContent = "JSON laden";
  load.addEventListener("click", async () => {
    await callService(hass, "import_backup", { entry_id: snap.entry_id, json: area.value });
    await refresh();
  });
  row.append(save, load);
  section.append(area, row);
  return section;
}

async function callService(hass, service, data) {
  const payload = {};
  for (const [key, value] of Object.entries(data)) {
    if (value != null && value !== "") payload[key] = value;
  }
  return hass.callService("pv_charge_manager", service, payload, undefined, true, true);
}

function watts(value) {
  if (value == null) return "kein Wert";
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} kW`;
  }
  return `${Math.round(value).toLocaleString("de-DE")} W`;
}

function kwh(value) {
  if (value == null) return "kein Wert";
  return `${Number(value).toLocaleString("de-DE", { maximumFractionDigits: 1 })} kWh`;
}

function percent(value) {
  if (value == null) return "kein Wert";
  return `${Math.round(value).toLocaleString("de-DE")} Prozent`;
}

function round(value, step) {
  const places = step < 1 ? 2 : 0;
  return Number(value.toFixed(places));
}

const CSS = `
:host { display: block; background: var(--primary-background-color, Canvas); color: var(--primary-text-color, CanvasText); }
.wrap { box-sizing: border-box; max-width: 960px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.sentence { margin: 0; font-size: 1.35rem; line-height: 1.35; }
.detail, .muted { margin: 0; color: var(--secondary-text-color, GrayText); font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
.card { background: var(--card-background-color, Canvas); border: 1px solid var(--divider-color, GrayText); border-radius: 12px; padding: 12px; }
.bar { height: 6px; border-radius: 99px; margin-bottom: 8px; }
.value { font-size: 1.15rem; font-variant-numeric: tabular-nums; }
.row { display: flex; gap: 8px; align-items: center; }
button, select, input, textarea { font: inherit; color: inherit; background: transparent; border: 1px solid var(--divider-color, GrayText); border-radius: 8px; padding: 8px; }
button { min-height: 44px; min-width: 44px; }
textarea { width: 100%; box-sizing: border-box; }
.switch[aria-pressed="true"] { border-color: var(--primary-color, currentColor); }
@media (min-width: 720px) {
  .flow { grid-template-columns: repeat(4, 1fr); }
  .days, .facts { grid-template-columns: 1fr 1fr; }
}
`;

customElements.define("pv-charge-manager-panel", PVChargeManagerPanel);
