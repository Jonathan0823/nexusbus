"""Static device configuration for development/demo purposes."""

from __future__ import annotations

from typing import List

from app.core.modbus_client import DeviceConfig, RegisterType

# Hard-coded demo devices. Extend or load from external config/db as needed.
DEVICE_CONFIGS: List[DeviceConfig] = [
    DeviceConfig(
        device_id="device-1",
        host="127.0.0.1",
        port=502,
        slave_id=1,
        timeout=3,
    ),
]

# Polling blueprint describing which registers to refresh periodically.
DEFAULT_POLL_TARGETS = [
    {
        "device_id": "device-1",
        "register_type": RegisterType.HOLDING,
        "address": 0,
        "count": 4,
    }
]

POLL_INTERVAL_SECONDS = 5
