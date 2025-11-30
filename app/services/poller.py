"""Background polling loop for periodic register refresh."""

from __future__ import annotations

import asyncio
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RegisterCache
from app.core.modbus_client import ModbusClientManager, ModbusClientError, RegisterType
from app.database import crud
from app.database.connection import async_session_maker

logger = logging.getLogger(__name__)


async def load_polling_targets_from_db() -> List[dict]:
    """Load active polling targets from database."""
    try:
        async with async_session_maker() as session:
            targets = await crud.get_all_active_polling_targets(session)
            
            # Convert to dict format expected by polling loop
            return [
                {
                    "id": target.id,
                    "device_id": target.device_id,
                    "register_type": target.register_type,
                    "address": target.address,
                    "count": target.count,
                    "description": target.description,
                }
                for target in targets
            ]
    except Exception as e:
        logger.error(f"Failed to load polling targets from database: {e}")
        return []


async def poll_registers(
    manager: ModbusClientManager,
    cache: RegisterCache,
    interval_seconds: int,
    use_database: bool = True,
    fallback_targets: List[dict] | None = None,
) -> None:
    """Continuously poll configured registers and store them in cache.
    
    Args:
        manager: Modbus client manager
        cache: Register cache
        interval_seconds: Polling interval in seconds
        use_database: If True, load targets from database; if False, use fallback_targets
        fallback_targets: Hardcoded targets to use if use_database=False
    """

    if interval_seconds <= 0:
        interval_seconds = 1
    
    if fallback_targets is None:
        fallback_targets = []

    logger.info(
        f"Starting polling service (database mode: {use_database}, interval: {interval_seconds}s)"
    )

    try:
        while True:
            # Load targets from database on each iteration (hot-reload support)
            if use_database:
                targets = await load_polling_targets_from_db()
                if not targets and fallback_targets:
                    logger.debug("No targets in database, using fallback targets")
                    targets = fallback_targets
            else:
                targets = fallback_targets
            
            if not targets:
                logger.debug("No polling targets configured, waiting...")
                await asyncio.sleep(interval_seconds)
                continue
            
            logger.debug(f"Polling {len(targets)} target(s)...")
            
            for target in targets:
                try:
                    device_id = target["device_id"]
                    register_type = target["register_type"]
                    address = int(target["address"])
                    count = int(target["count"])
                    
                    # Convert string to RegisterType enum
                    if not isinstance(register_type, RegisterType):
                        register_type = RegisterType(register_type)
                    
                    # Read from Modbus device
                    data = await manager.read_registers(
                        device_id=device_id,
                        register_type=register_type,
                        address=address,
                        count=count,
                    )
                    
                    # Store in cache
                    await cache.set(device_id, register_type, address, count, data)
                    
                    logger.debug(
                        f"Polled {device_id} {register_type.value} "
                        f"addr={address} count={count} → {data}"
                    )
                    
                except (KeyError, ValueError) as exc:
                    logger.error(f"Invalid poll target {target}: {exc}")
                except (ModbusClientError, ConnectionError) as exc:
                    logger.warning(
                        f"Polling failed for {target.get('device_id')} "
                        f"(register={target.get('register_type')} "
                        f"addr={target.get('address')} "
                        f"count={target.get('count')}): {exc}"
                    )
            
            await asyncio.sleep(interval_seconds)
            
    except asyncio.CancelledError:
        logger.info("Polling task cancelled")
        raise

