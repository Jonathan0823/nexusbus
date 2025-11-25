"""Static device configuration for development/demo purposes."""

from __future__ import annotations

from typing import List

from pymodbus.framer import FramerType

from app.core.modbus_client import DeviceConfig

# Hard-coded demo devices. Extend or load from external config/db as needed.
DEVICE_CONFIGS: List[DeviceConfig] = [
    DeviceConfig(
        device_id="rgv-lithium",
        host="10.19.20.147",
        port=8899,
        slave_id=1,
        timeout=10,
        framer=FramerType.RTU,
    ),
    # The following two devices share the same IP:Port (Gateway).
    # The ModbusClientManager will automatically share a single TCP connection
    # and serialize requests to prevent slave ID mismatches.
    DeviceConfig(
        device_id="office-eng",
        host="10.19.20.148",
        port=8899,
        slave_id=1,
        timeout=10,
        framer=FramerType.RTU,
    ),
    DeviceConfig(
        device_id="formation",
        host="10.19.20.148",
        port=8899,
        slave_id=2,
        timeout=10,
        framer=FramerType.RTU,
    ),
]

# Polling blueprint describing which registers to refresh periodically.
# Keep empty to disable polling.
DEFAULT_POLL_TARGETS = []

POLL_INTERVAL_SECONDS = 5

# API request timeout in seconds
# If a Modbus request takes longer than this, it will timeout and reset the connection
API_REQUEST_TIMEOUT_SECONDS = 5
