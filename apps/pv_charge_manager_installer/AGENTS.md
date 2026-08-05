# Home Assistant app instructions

This folder contains the Home Assistant OS app that installs the custom
integration into `/config/custom_components/pv_charge_manager/`.

The app is intentionally an installer and does not control a wallbox. It fetches
the integration from the repository's `main` branch, so users must restart the
app and then Home Assistant after an update.

Keep the write scope limited to the mapped Home Assistant configuration. Do not
add Supervisor, Docker, host-network, hardware, or wallbox privileges.
