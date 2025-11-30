"""Device configuration - can load from database or use hardcoded defaults."""

from __future__ import annotations

from typing import List

from pymodbus.framer import FramerType
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.modbus_client import DeviceConfig

# Hard-coded demo devices as fallback
DEVICE_CONFIGS: List[DeviceConfig] = []

# Polling blueprint describing which registers to refresh periodically.
# Keep empty to disable polling.
DEFAULT_POLL_TARGETS = []

POLL_INTERVAL_SECONDS = settings.POLL_INTERVAL_SECONDS

# API request timeout in seconds
# If a Modbus request takes longer than this, it will timeout and reset the connection
API_REQUEST_TIMEOUT_SECONDS = 5


async def load_device_configs(
    session: AsyncSession | None = None,
) -> List[DeviceConfig]:
    """Load device configurations from database.

    If database is not available or session is None, returns hardcoded DEVICE_CONFIGS.
    """
    if session is None:
        return DEVICE_CONFIGS

    try:
        from app.database import crud

        devices = await crud.get_all_active_devices(session)

        if not devices:
            # No devices in database, use hardcoded configs
            return DEVICE_CONFIGS

        return [
            DeviceConfig(
                device_id=device.device_id,
                host=device.host,
                port=device.port,
                slave_id=device.slave_id,
                timeout=device.timeout,
                framer=FramerType[device.framer],
                max_retries=device.max_retries,
                retry_delay=device.retry_delay,
            )
            for device in devices
        ]
    except Exception as e:
        # If database error, fallback to hardcoded configs
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to load devices from database: {e}. Using hardcoded configs."
        )
        return DEVICE_CONFIGS
