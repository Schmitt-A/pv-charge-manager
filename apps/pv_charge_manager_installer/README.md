# PV Charge Manager integration installer

This Home Assistant OS app installs the PV Charge Manager custom integration
into the Home Assistant configuration directory. It is a convenience installer
for this development repository; it is not a separate PV forecasting service
and it does not control the wallbox.

The app requires Home Assistant OS. HACS remains the path for Home Assistant
Container, Core, and supervised installations.

The app downloads the current `main` branch when it starts, copies the
integration, and then stops. It has no page of its own. Restart Home Assistant
and add PV Charge Manager under Settings, Devices & services. The sidebar entry
appears only after that integration exists.

`init: false` stays in `config.yaml`. The base image uses s6-overlay, which
must be process 1. The install script must halt s6 when it finishes. A normal
exit makes s6 start the container again.

