# Test instructions

## Test strategy

Tests in this directory should validate the pure Python behavior first:

- PV surplus calculations
- feed-in tariff allocation
- vehicle energy demand
- forecast correction
- charge window planning

Do not require a running Home Assistant instance for these tests. Add Home
Assistant integration tests later under a separate marker once the runtime setup
is mature.

The runtime coordinator has an additional local smoke check when Home Assistant
dependencies are installed. Keep the default test suite independent from those
large optional dependencies.

## Commands

```bash
pytest
ruff check tests custom_components/pv_charge_manager
```
