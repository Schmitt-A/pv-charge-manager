# PV Charge Manager integration installer

This Home Assistant OS app installs the PV Charge Manager custom integration
into the Home Assistant configuration directory. It is a convenience installer
for this development repository; it is not a separate PV forecasting service
and it does not control the wallbox.

The app downloads the current `main` branch when it starts. After installing or
updating the app, restart Home Assistant before configuring the integration.

The app requires Home Assistant OS because Home Assistant apps are only
available with that installation method. HACS remains the preferred path for
Home Assistant Container, Core, and supervised installations.

`init: false` stays in `config.yaml`. The base image uses s6-overlay, which
must be process 1. With the default Docker init the app stops immediately and
logs `s6-overlay-suexec: fatal: can only run as pid 1`.

