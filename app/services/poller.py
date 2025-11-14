"""Background polling loop for periodic register refresh."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Mapping

from app.core.cache import RegisterCache
from app.core.modbus_client import ModbusClientManager, ModbusClientError, RegisterType

logger = logging.getLogger(__name__)


async def poll_registers(
    manager: ModbusClientManager,
    cache: RegisterCache,
    targets: Iterable[Mapping[str, object]],
    interval_seconds: int,
) -> None:
    """Continuously poll configured registers and store them in cache."""

    if interval_seconds <= 0:
        interval_seconds = 1

    try:
        while True:
            for target in targets:
                try:
                    device_id = target["device_id"]  # type: ignore[index]
                    register_type = target["register_type"]  # type: ignore[index]
                    address = int(target["address"])  # type: ignore[index]
                    count = int(target["count"])  # type: ignore[index]
                    if not isinstance(register_type, RegisterType):
                        register_type = RegisterType(register_type)
                    data = await manager.read_registers(
                        device_id=device_id,
                        register_type=register_type,
                        address=address,
                        count=count,
                    )
                    await cache.set(device_id, register_type, address, count, data)
                except (KeyError, ValueError) as exc:
                    logger.error("Invalid poll target %s: %s", target, exc)
                except (ModbusClientError, ConnectionError) as exc:
                    logger.warning(
                        "Polling failed for %s (register=%s addr=%s count=%s): %s",
                        target.get("device_id"),
                        target.get("register_type"),
                        target.get("address"),
                        target.get("count"),
                        exc,
                    )
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Polling task cancelled")
        raise
