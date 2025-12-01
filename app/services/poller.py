"""Background polling loop for periodic register refresh."""

from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from typing import List, Dict, Any


from app.core.cache import RegisterCache
from app.core.modbus_client import ModbusClientManager, ModbusClientError, RegisterType
from app.core.mqtt_client import MQTTClientManager
from app.database import crud
from app.database.connection import async_session_maker

logger = logging.getLogger(__name__)


async def _safe_mqtt_publish(
    mqtt_manager: MQTTClientManager,
    topic_suffix: str,
    payload: Dict[str, Any],
    device_id: str,
) -> None:
    """Safely publish to MQTT with error handling.

    This function handles MQTT publish errors gracefully without
    affecting the polling loop.
    """
    try:
        await mqtt_manager.publish(topic_suffix, payload)
    except Exception as e:
        logger.error(
            f"MQTT publish failed for device '{device_id}' topic '{topic_suffix}': {e}",
            exc_info=True,
        )


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


async def _poll_single_target(
    target: Dict[str, Any],
    manager: ModbusClientManager,
    cache: RegisterCache,
    mqtt_manager: MQTTClientManager | None = None,
) -> tuple[bool, str]:
    """Poll a single target and return (success, error_message).

    Args:
        target: Polling target configuration dict
        manager: Modbus client manager
        cache: Register cache
        mqtt_manager: Optional MQTT manager

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        device_id = target["device_id"]
        register_type = target["register_type"]
        address = int(target["address"])
        count = int(target["count"])

        # Convert string to RegisterType enum
        if not isinstance(register_type, RegisterType):
            register_type = RegisterType(register_type)

        # Read from Modbus device (fail fast, no retry here)
        # Force retries=0 and timeout=1.0s to ensure fail-fast in polling loop
        data = await manager.read_registers(
            device_id=device_id,
            register_type=register_type,
            address=address,
            count=count,
            retries=0,  # Fail fast!
            timeout=1.0,  # Fast timeout for poller!
        )

        # Store in cache
        await cache.set(device_id, register_type, address, count, data)

        logger.info(
            f"✓ Polled {device_id} {register_type.value} "
            f"addr={address} count={count}"
        )

        # Publish to MQTT (Fire & Forget with error handling)
        if mqtt_manager:
            # Topic: {prefix}/{device_id}/{register_type}/{address}
            topic_suffix = f"{device_id}/{register_type.value}/{address}"
            payload = {
                "device_id": device_id,
                "register_type": register_type.value,
                "address": address,
                "count": count,
                "values": data,
                "timestamp": time.time(),  # Standard Unix timestamp
            }
            # Run in background with error handling
            asyncio.create_task(
                _safe_mqtt_publish(mqtt_manager, topic_suffix, payload, device_id)
            )

        return (True, "")

    except (KeyError, ValueError) as exc:
        # Invalid configuration - log once and skip
        error_msg = f"Invalid poll target config {target}: {exc}"
        logger.error(error_msg)
        return (False, error_msg)

    except (ModbusClientError, ConnectionError) as exc:
        # Modbus error - log briefly and skip, will retry next cycle
        error_msg = (
            f"✗ Poll failed: {target.get('device_id')} "
            f"{target.get('register_type')} addr={target.get('address')} - "
            f"will retry next cycle: {exc}"
        )
        logger.warning(error_msg)
        return (False, error_msg)

    except Exception as exc:
        # Unexpected error - log and skip
        error_msg = f"Unexpected error polling {target.get('device_id')}: {exc}"
        logger.error(error_msg, exc_info=True)
        return (False, error_msg)


async def poll_registers(
    manager: ModbusClientManager,
    cache: RegisterCache,
    interval_seconds: int,
    use_database: bool = True,
    fallback_targets: List[dict] | None = None,
    mqtt_manager: MQTTClientManager = None,  # Optional MQTT manager
) -> None:
    """Continuously poll configured registers and store them in cache.

    This function implements:
    - Race condition prevention: Takes snapshot of targets at start of each cycle
    - Parallel polling: Polls all targets concurrently using asyncio.gather
    - Hot-reload support: Reloads targets from database each cycle

    Args:
        manager: Modbus client manager
        cache: Register cache
        interval_seconds: Polling interval in seconds
        use_database: If True, load targets from database; if False, use fallback_targets
        fallback_targets: Hardcoded targets to use if use_database=False
        mqtt_manager: Optional MQTT manager for publishing data
    """

    if interval_seconds <= 0:
        interval_seconds = 1

    if fallback_targets is None:
        fallback_targets = []

    logger.info(
        f"Starting polling service (database mode: {use_database}, interval: {interval_seconds}s, parallel polling enabled)"
    )

    try:
        while True:
            # FIX RACE CONDITION: Take snapshot of targets at start of cycle
            # This ensures we use consistent target list throughout the polling cycle
            # even if targets are modified in database during polling
            if use_database:
                targets = await load_polling_targets_from_db()
                if not targets and fallback_targets:
                    logger.debug("No targets in database, using fallback targets")
                    targets = deepcopy(
                        fallback_targets
                    )  # Deep copy to prevent mutation
            else:
                targets = deepcopy(fallback_targets)  # Deep copy to prevent mutation

            if not targets:
                logger.debug("No polling targets configured, waiting...")
                await asyncio.sleep(interval_seconds)
                continue

            logger.debug(f"Polling {len(targets)} target(s) in parallel...")
            cycle_start_time = time.time()

            # PARALLEL POLLING: Poll all targets concurrently
            # This significantly improves performance when polling multiple devices
            polling_tasks = [
                _poll_single_target(target, manager, cache, mqtt_manager)
                for target in targets
            ]

            # Wait for all polling tasks to complete (with return_exceptions=True
            # to prevent one failure from stopping others)
            results = await asyncio.gather(*polling_tasks, return_exceptions=True)

            # Process results
            success_count = 0
            failure_count = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Polling task {i} raised exception: {result}", exc_info=True
                    )
                    failure_count += 1
                elif isinstance(result, tuple):
                    success, error_msg = result
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                else:
                    failure_count += 1

            cycle_duration = time.time() - cycle_start_time
            cycle_duration_ms = cycle_duration * 1000
            
            # Record metrics
            from app.core.metrics import metrics_collector
            metrics_collector.polling.record_cycle(
                success_count, failure_count, cycle_duration_ms
            )
            
            logger.debug(
                f"Polling cycle completed: {success_count} success, {failure_count} failures, "
                f"duration: {cycle_duration:.2f}s"
            )

            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.info("Polling task cancelled")
        raise
