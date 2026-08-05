class PVChargeManagerPanel extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <ha-card header="PV Charge Manager">
        <div style="padding: 16px">
          <p>Development preview. Runtime controls will be added after the backend entity mapping is complete.</p>
        </div>
      </ha-card>
    `;
  }
}

customElements.define("pv-charge-manager-panel", PVChargeManagerPanel);
