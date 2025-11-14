"""Static device configuration for development/demo purposes."""

from __future__ import annotations

from typing import List

from pymodbus.framer import FramerType

from app.core.modbus_client import DeviceConfig, RegisterType

# Hard-coded demo devices. Extend or load from external config/db as needed.
DEVICE_CONFIGS: List[DeviceConfig] = [
    DeviceConfig(
        device_id="rgv-lithium",
        host="10.19.20.147",
        port=8899,
        slave_id=1,
        timeout=3,
        framer=FramerType.RTU,
    ),
]

# Polling blueprint describing which registers to refresh periodically.
DEFAULT_POLL_TARGETS = [
    {
        "device_id": "rgv-lithium",
        "register_type": RegisterType.HOLDING,
        "address": 0,
        "count": 4,
    }
]

POLL_INTERVAL_SECONDS = 5
