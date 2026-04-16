"""Background polling loop for periodic register refresh."""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from typing import Dict, List, Any, Set, Tuple


from app.core.cache import RegisterCache
from app.core.logging_config import get_logger
from app.core.modbus_client import ModbusClientManager, ModbusClientError, RegisterType
from app.core.circuit_breaker import CircuitOpenError
from app.core.mqtt_client import MQTTClientManager
from app.database import crud
from app.database.connection import async_session_maker

logger = get_logger(__name__)

# Track pending MQTT publish tasks for graceful shutdown
_pending_mqtt_tasks: Set[asyncio.Task] = set()


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
            "mqtt_publish_failed",
            device_id=device_id,
            topic=topic_suffix,
            error=str(e),
            error_type=type(e).__name__,
            message="MQTT publish failed",
            exc_info=True,
        )


async def await_pending_mqtt_tasks(timeout: float = 5.0) -> int:
    """Wait for all pending MQTT publish tasks to complete.
    
    Args:
        timeout: Maximum time to wait for tasks to complete
        
    Returns:
        Number of tasks that were awaited
    """
    if not _pending_mqtt_tasks:
        return 0
    
    task_count = len(_pending_mqtt_tasks)
    logger.info(
        "mqtt_awaiting_pending_tasks",
        task_count=task_count,
        timeout=timeout,
        message=f"Awaiting {task_count} pending MQTT publish tasks",
    )
    
    # Wait for all pending tasks with timeout
    done, pending = await asyncio.wait(
        _pending_mqtt_tasks.copy(),
        timeout=timeout,
        return_when=asyncio.ALL_COMPLETED,
    )
    
    if pending:
        logger.warning(
            "mqtt_tasks_timeout",
            pending_count=len(pending),
            message=f"{len(pending)} MQTT tasks did not complete within timeout",
        )
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
    
    return len(done)

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
        logger.error(
            "polling_load_targets_failed",
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to load polling targets from database",
            exc_info=True,
        )
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
            "polling_target_success",
            device_id=device_id,
            register_type=register_type.value,
            address=address,
            count=count,
            values_count=len(data),
            message="Successfully polled target",
        )

        # Publish to MQTT (Fire & Forget with error handling and tracking)
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
            # Run in background with error handling and task tracking
            task = asyncio.create_task(
                _safe_mqtt_publish(mqtt_manager, topic_suffix, payload, device_id)
            )
            _pending_mqtt_tasks.add(task)
            task.add_done_callback(_pending_mqtt_tasks.discard)

        return (True, "")

    except (KeyError, ValueError) as exc:
        # Invalid configuration - log once and skip
        error_msg = f"Invalid poll target config {target}: {exc}"
        logger.error(
            "polling_target_invalid_config",
            target=target,
            error=str(exc),
            error_type=type(exc).__name__,
            device_id=target.get("device_id"),
            message="Invalid polling target configuration",
        )
        return (False, error_msg)

    except (ModbusClientError, ConnectionError, ConnectionResetError, OSError) as exc:
        # Connection error - log briefly and skip, will retry next cycle
        # Includes ConnectionResetError and OSError for Windows-specific socket errors
        error_msg = (
            f"✗ Poll failed: {target.get('device_id')} "
            f"{target.get('register_type')} addr={target.get('address')} - "
            f"will retry next cycle: {exc}"
        )
        logger.warning(
            "polling_target_failed",
            device_id=target.get("device_id"),
            register_type=target.get("register_type"),
            address=target.get("address"),
            error=str(exc),
            error_type=type(exc).__name__,
            message="Poll failed, will retry next cycle",
        )
        return (False, error_msg)

    except CircuitOpenError as exc:
        # Circuit breaker is open - skip silently, will retry after recovery timeout
        error_msg = f"⚡ Circuit OPEN: {exc.device_id} - skip for {exc.time_until_retry:.1f}s"
        logger.debug(
            "polling_target_circuit_open",
            device_id=exc.device_id,
            time_until_retry=round(exc.time_until_retry, 1),
            message="Device circuit breaker is open, skipping",
        )
        return (False, error_msg)

    except Exception as exc:
        # Unexpected error - log and skip
        error_msg = f"Unexpected error polling {target.get('device_id')}: {exc}"
        logger.error(
            "polling_target_unexpected_error",
            device_id=target.get("device_id"),
            target=target,
            error=str(exc),
            error_type=type(exc).__name__,
            message="Unexpected error polling target",
            exc_info=True,
        )
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
    - Gateway-serialized polling: Targets on same gateway (host:port) are polled sequentially
    - Parallel gateway polling: Different gateways can be polled in parallel
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
        "polling_service_started",
        database_mode=use_database,
        interval_seconds=interval_seconds,
        gateway_serial_polling=True,
        message="Polling service started",
    )

    try:
        while True:
            # FIX RACE CONDITION: Take snapshot of targets at start of cycle
            # This ensures we use consistent target list throughout the polling cycle
            # even if targets are modified in database during polling
            if use_database:
                targets = await load_polling_targets_from_db()
                if not targets and fallback_targets:
                    logger.debug(
                        "polling_using_fallback",
                        fallback_count=len(fallback_targets),
                        message="No targets in database, using fallback targets",
                    )
                    targets = deepcopy(
                        fallback_targets
                    )  # Deep copy to prevent mutation
            else:
                targets = deepcopy(fallback_targets)  # Deep copy to prevent mutation

            if not targets:
                logger.debug(
                    "polling_no_targets",
                    message="No polling targets configured, waiting",
                )
                await asyncio.sleep(interval_seconds)
                continue

            logger.debug(
                "polling_cycle_start",
                target_count=len(targets),
                message="Starting polling cycle",
            )
            cycle_start_time = time.time()

            # GROUP TARGETS BY GATEWAY (host:port)
            # This ensures targets on the same gateway are polled sequentially
            # to prevent response mix-up from shared connections
            gateway_groups: Dict[Tuple[str, int], List[dict]] = {}
            
            for target in targets:
                device_id = target.get("device_id")
                if not device_id:
                    continue
                    
                # Get device config to find gateway key
                config = manager.get_config(device_id)
                if not config:
                    logger.warning(
                        "polling_target_unknown_device",
                        device_id=device_id,
                        message="Skipping target with unknown device",
                    )
                    continue
                
                gateway_key = (config.host, config.port)
                if gateway_key not in gateway_groups:
                    gateway_groups[gateway_key] = []
                gateway_groups[gateway_key].append(target)

            # LOG gateway grouping for debugging
            for gw_key, gw_targets in gateway_groups.items():
                logger.debug(
                    "polling_gateway_group",
                    host=gw_key[0],
                    port=gw_key[1],
                    target_count=len(gw_targets),
                    device_ids=[t.get("device_id") for t in gw_targets],
                )

            # POLL EACH GATEWAY GROUP SEQUENTIALLY, BUT DIFFERENT GATEWAYS IN PARALLEL
            # This prevents response mix-up while maintaining some parallelism
            
            async def poll_gateway_group(
                gateway_key: Tuple[str, int], 
                group_targets: List[dict]
            ) -> Tuple[int, int]:
                """Poll all targets for one gateway sequentially.
                
                Returns (success_count, failure_count) for this gateway.
                """
                success_count = 0
                failure_count = 0
                
                for target in group_targets:
                    result = await _poll_single_target(target, manager, cache, mqtt_manager)
                    if isinstance(result, tuple):
                        success, _ = result
                        if success:
                            success_count += 1
                        else:
                            failure_count += 1
                    else:
                        failure_count += 1
                
                return success_count, failure_count

            # Create tasks for each gateway group (parallel across gateways)
            gateway_tasks = [
                poll_gateway_group(gw_key, gw_targets)
                for gw_key, gw_targets in gateway_groups.items()
            ]

            # Wait for all gateway groups to complete
            gateway_results = await asyncio.gather(*gateway_tasks, return_exceptions=True)

            # Process results
            success_count = 0
            failure_count = 0

            for i, result in enumerate(gateway_results):
                if isinstance(result, Exception):
                    gw_key = list(gateway_groups.keys())[i]
                    logger.error(
                        "polling_gateway_exception",
                        gateway_host=gw_key[0],
                        gateway_port=gw_key[1],
                        exception=str(result),
                        exception_type=type(result).__name__,
                        message="Gateway group raised exception",
                        exc_info=True,
                    )
                    # Count all targets in this group as failures
                    failure_count += len(gateway_groups[gw_key])
                elif isinstance(result, tuple):
                    s, f = result
                    success_count += s
                    failure_count += f
                else:
                    gw_key = list(gateway_groups.keys())[i]
                    failure_count += len(gateway_groups[gw_key])

            cycle_duration = time.time() - cycle_start_time
            cycle_duration_ms = cycle_duration * 1000
            
            # Record metrics
            from app.core.metrics import metrics_collector
            metrics_collector.polling.record_cycle(
                success_count, failure_count, cycle_duration_ms
            )
            
            logger.debug(
                "polling_cycle_completed",
                success_count=success_count,
                failure_count=failure_count,
                total_targets=len(targets),
                gateway_count=len(gateway_groups),
                duration_seconds=round(cycle_duration, 2),
                duration_ms=round(cycle_duration_ms, 2),
                message="Polling cycle completed",
            )

            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.info(
            "polling_service_cancelled",
            message="Polling service cancelled",
        )
        raise
