"""Modbus client session and manager abstractions."""

from __future__ import annotations

import asyncio
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.framer import FramerType
from pymodbus.pdu import ExceptionResponse

from app.core.logging_config import get_logger
from app.core.circuit_breaker import (
    CircuitBreakerRegistry,
    CircuitBreakerConfig,
    CircuitOpenError,
)
from app.core.config import settings

logger = get_logger(__name__)


class RegisterType(str, Enum):
    """Supported Modbus register/coil types."""

    HOLDING = "holding"
    INPUT = "input"
    COIL = "coil"
    DISCRETE = "discrete"


@dataclass(frozen=True)
class DeviceConfig:
    """Configuration needed to connect to a Modbus device."""

    device_id: str
    host: str
    port: int
    slave_id: int
    timeout: int = 3
    framer: FramerType = FramerType.SOCKET
    max_retries: int = 5
    retry_delay: float = 0.1


class AsyncModbusGateway:
    """
    Encapsulates a shared async Modbus TCP connection to a gateway/host.
    Serves multiple slave_ids behind the same IP:Port.
    
    Uses AsyncModbusTcpClient for true async/await non-blocking operations.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: int = 3,
        framer: FramerType = FramerType.SOCKET,
        max_retries: int = 5,
        retry_delay: float = 0.1,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.framer = framer
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[AsyncModbusTcpClient] = None
        self._create_client()

    def _create_client(self) -> None:
        """Create the async Modbus TCP client."""
        self._client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
            framer=self.framer,
            retries=0,  # We handle retries ourselves for full control
        )

    async def connect(self) -> bool:
        """Connect to the Modbus gateway."""
        if self._client is None:
            self._create_client()
        return await self._client.connect()

    async def ensure_connection(self) -> None:
        """Ensure we have an active connection."""
        if not self.is_connected():
            connected = await self.connect()
            if not connected:
                raise ConnectionError(
                    f"Unable to connect to Modbus gateway {self.host}:{self.port}"
                )

    def _is_valid_response(self, response, operation: str, slave_id: int) -> bool:
        """Check if response is valid (not error and correct slave_id)."""
        # Check for None response (timeout or connection issue)
        if response is None:
            logger.warning(
                "modbus_no_response",
                operation=operation,
                slave_id=slave_id,
                message="No response (None) received",
            )
            return False

        # Check if response is ExceptionResponse (includes CRC errors)
        if isinstance(response, ExceptionResponse):
            logger.warning(
                "modbus_exception_response",
                operation=operation,
                slave_id=slave_id,
                exception_code=response.exception_code,
                message="Exception response received",
            )
            return False

        # Check if response is error
        # Use getattr to safely check isError, defaulting to False if not present
        if getattr(response, "isError", lambda: False)():
            error_msg = str(response)
            logger.warning(
                "modbus_error_response",
                operation=operation,
                slave_id=slave_id,
                error=error_msg,
                message="Error response received",
            )
            return False

        # Additional check for slave_id if available
        if hasattr(response, "slave_id") and response.slave_id != slave_id:
            logger.warning(
                "modbus_slave_id_mismatch",
                operation=operation,
                requested_slave_id=slave_id,
                received_slave_id=response.slave_id,
                message="Slave ID mismatch, will retry",
            )
            return False
        return True

    async def _read_registers(
        self,
        slave_id: int,
        address: int,
        count: int,
        operation: str,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Generic async method for reading registers/coils/discrete inputs.
        
        Args:
            slave_id: Modbus slave ID
            address: Start address
            count: Number of registers/coils to read
            operation: One of 'holding', 'input', 'coil', 'discrete'
            retries: Optional retry count override
            timeout: Optional timeout override
            
        Returns:
            Modbus response object or None on failure
        """
        await self.ensure_connection()
        last_response = None
        last_exception = None

        # Map operation to client method
        method_map = {
            "holding": self._client.read_holding_registers,
            "input": self._client.read_input_registers,
            "coil": self._client.read_coils,
            "discrete": self._client.read_discrete_inputs,
        }

        if operation not in method_map:
            raise ValueError(
                f"Invalid operation: {operation}. Must be one of {list(method_map.keys())}"
            )

        # Compute operation name once for logging
        op_name = (
            f"read_{operation}_registers"
            if operation in ("holding", "input")
            else f"read_{operation}s"
        )

        read_method = method_map[operation]

        # Apply temporary timeout override if provided
        original_timeout = None
        if timeout is not None and self._client:
            original_timeout = getattr(self._client, "timeout", self.timeout)
            self._client.timeout = timeout

        try:
            num_attempts = retries if retries is not None else self.max_retries
            if num_attempts < 1:
                num_attempts = 1

            for attempt in range(num_attempts):
                try:
                    response = await read_method(
                        address=address, count=count, device_id=slave_id
                    )
                    # Only assign last_response after validation succeeds
                    if self._is_valid_response(response, op_name, slave_id):
                        last_response = response
                        if attempt > 0:
                            logger.info(
                                "modbus_read_success_after_retry",
                                operation=op_name,
                                slave_id=slave_id,
                                attempts=attempt + 1,
                                message="Read succeeded after retries",
                            )
                        return response
                    else:
                        # Invalid response (slave_id mismatch, error response, etc.)
                        # Close connection to flush buffer and prevent stale responses
                        logger.debug(
                            "modbus_invalid_response_flush",
                            operation=op_name,
                            slave_id=slave_id,
                            attempt=attempt + 1,
                            message="Invalid response detected, flushing connection",
                        )
                        self._client.close()
                        if attempt < num_attempts - 1:
                            # Brief delay to allow device to stabilize
                            await asyncio.sleep(0.05)
                            await self.ensure_connection()
                            # Re-apply timeout after reconnect
                            if timeout is not None and self._client:
                                self._client.timeout = timeout
                except (ModbusException, ModbusIOException, OSError) as exc:
                    last_exception = exc
                    logger.debug(
                        "modbus_read_exception",
                        operation=op_name,
                        slave_id=slave_id,
                        exception_type=type(exc).__name__,
                        exception=str(exc),
                        attempt=attempt + 1,
                        max_attempts=num_attempts,
                        message="Modbus exception, retrying",
                    )
                    if self._client:
                        self._client.close()
                    if attempt < num_attempts - 1:
                        await self.ensure_connection()
                        # Re-apply timeout after reconnect
                        if timeout is not None and self._client:
                            self._client.timeout = timeout
                except Exception as exc:
                    last_exception = exc
                    logger.error(
                        "modbus_read_unexpected_error",
                        operation=op_name,
                        slave_id=slave_id,
                        exception_type=type(exc).__name__,
                        exception=str(exc),
                        attempt=attempt + 1,
                        max_attempts=num_attempts,
                        message="Unexpected error, retrying",
                        exc_info=True,
                    )
                    if self._client:
                        self._client.close()
                    if attempt < num_attempts - 1:
                        await self.ensure_connection()
                        # Re-apply timeout after reconnect
                        if timeout is not None and self._client:
                            self._client.timeout = timeout

                if attempt < num_attempts - 1:
                    # Log at INFO for holding/input, DEBUG for coil/discrete
                    log_fn = logger.info if operation in ("holding", "input") else logger.debug
                    log_fn(
                        "modbus_read_retry",
                        operation=op_name,
                        slave_id=slave_id,
                        attempt=attempt + 1,
                        max_attempts=num_attempts,
                    )
                    await asyncio.sleep(self.retry_delay)

            logger.debug(
                "modbus_read_failed",
                operation=op_name,
                slave_id=slave_id,
                attempts=num_attempts,
                last_exception=str(last_exception) if last_exception else None,
                message="Read failed after all retries",
            )

            # Flush connection to clear any stale data in buffer
            # This prevents response mix-up when multiple slave IDs share a connection
            if self._client:
                self._client.close()

            # Return None - do not return potentially invalid last_response
            return None
        finally:
            # Restore original timeout
            if original_timeout is not None and self._client:
                self._client.timeout = original_timeout

    async def read_holding_registers(
        self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ):
        """Read holding registers."""
        return await self._read_registers(slave_id, address, count, "holding", retries, timeout)

    async def read_input_registers(
        self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ):
        """Read input registers."""
        return await self._read_registers(slave_id, address, count, "input", retries, timeout)

    async def read_coils(
        self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ):
        """Read coils."""
        return await self._read_registers(slave_id, address, count, "coil", retries, timeout)

    async def read_discrete_inputs(
        self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ):
        """Read discrete inputs."""
        return await self._read_registers(slave_id, address, count, "discrete", retries, timeout)

    async def write_holding_register(self, slave_id: int, address: int, value: int):
        """Write a single holding register."""
        await self.ensure_connection()
        last_response = None
        for attempt in range(self.max_retries):
            try:
                response = await self._client.write_register(
                    address=address, value=value, device_id=slave_id
                )
                # Only assign last_response after validation succeeds
                if self._is_valid_response(response, "write_holding_register", slave_id):
                    last_response = response
                    return response
                else:
                    # Invalid response - clear last_response
                    last_response = None
            except (ModbusException, OSError) as exc:
                logger.warning(
                    "modbus_write_exception",
                    operation="write_holding_register",
                    slave_id=slave_id,
                    address=address,
                    value=value,
                    exception=str(exc),
                    attempt=attempt + 1,
                    max_attempts=self.max_retries,
                    message="Write exception, retrying",
                )
                if self._client:
                    self._client.close()
                if attempt < self.max_retries - 1:
                    await self.ensure_connection()

            if attempt < self.max_retries - 1:
                logger.debug(
                    "modbus_write_retry",
                    operation="write_holding_register",
                    slave_id=slave_id,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries,
                )
                await asyncio.sleep(self.retry_delay)

        # Return None - do not return potentially invalid last_response
        return None

    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return bool(self._client and self._client.connected)

    def close(self) -> None:
        """Close the Modbus connection."""
        if self._client:
            self._client.close()
            self._client = None


# Keep old class name as alias for backwards compatibility during transition
ModbusGateway = AsyncModbusGateway


class ModbusClientError(Exception):
    """Base exception for Modbus client issues."""


class DeviceNotFoundError(ModbusClientError):
    pass


class ModbusClientManager:
    """
    Manages Modbus gateways and exposes device-centric helpers.
    Ensures only one connection exists per (Host, Port).
    
    Now uses fully async AsyncModbusTcpClient - no more to_thread wrapping!
    """

    def __init__(self, device_configs: Iterable[DeviceConfig], db_session_factory) -> None:
        self._configs: Dict[str, DeviceConfig] = {
            cfg.device_id: cfg for cfg in device_configs
        }
        # Database session factory for device health tracking
        self._db_session_factory = db_session_factory
        # Map (host, port) -> AsyncModbusGateway
        # IMPORTANT: One gateway per host:port, NOT per slave_id
        # All devices sharing the same host:port share ONE connection
        self._gateways: Dict[Tuple[str, int], AsyncModbusGateway] = {}
        # Map (host, port) -> Lock - ensures serialized access per gateway
        self._locks: Dict[Tuple[str, int], asyncio.Lock] = {}
        self._manager_lock = asyncio.Lock()
        
        # Gateway cooldown: (host, port) -> cooldown_until timestamp
        # After a failure, this gateway is paused to let RTU buffer settle
        self._gateway_cooldowns: Dict[Tuple[str, int], float] = {}
        self._gateway_cooldown_seconds = 1.0  # How long to wait after failure

        # Circuit breaker registry (per device)
        self._circuit_breakers = CircuitBreakerRegistry(
            default_config=CircuitBreakerConfig(
                failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=float(settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT),
            )
        )

        # Validate for problematic configurations
        self._validate_gateway_config()

    def _create_gateway(self, config: DeviceConfig) -> AsyncModbusGateway:
        """Create a gateway for a device.

        Note: Gateway is shared across all devices on the same host:port,
        regardless of slave_id. Access is serialized via locks.
        """
        return AsyncModbusGateway(
            host=config.host,
            port=config.port,
            timeout=config.timeout,
            framer=config.framer,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
        )

    def _validate_gateway_config(self) -> None:
        """Check for problematic configurations across all devices.

        Validates:
        - Multiple devices on same host:port with different slave_ids (allowed but warned)
        - Duplicate (host, port, slave_id) combinations (error)
        """
        # Track (host, port, slave_id) -> list of device_ids
        endpoint_map: Dict[Tuple[str, int, int], List[str]] = {}
        # Track (host, port) -> list of device_ids for warnings
        gateway_map: Dict[Tuple[str, int], List[str]] = {}

        for device_id, config in self._configs.items():
            endpoint_key = (config.host, config.port, config.slave_id)
            gateway_key = (config.host, config.port)

            if endpoint_key not in endpoint_map:
                endpoint_map[endpoint_key] = []
            endpoint_map[endpoint_key].append(device_id)

            if gateway_key not in gateway_map:
                gateway_map[gateway_key] = []
            gateway_map[gateway_key].append(device_id)

        # Check for duplicate endpoints (exact same host:port:slave_id)
        duplicates = {key: devs for key, devs in endpoint_map.items() if len(devs) > 1}
        if duplicates:
            for (host, port, slave_id), device_ids in duplicates.items():
                logger.error(
                    "modbus_duplicate_endpoint_error",
                    host=host,
                    port=port,
                    slave_id=slave_id,
                    device_ids=device_ids,
                    message=(
                        f"CRITICAL: Multiple devices with identical endpoint: "
                        f"{host}:{port} slave_id={slave_id} -> devices: {device_ids}"
                    ),
                )

        # Warn about shared gateways (multiple devices on same host:port)
        shared_gateways = {key: devs for key, devs in gateway_map.items() if len(devs) > 1}
        if shared_gateways:
            for (host, port), device_ids in shared_gateways.items():
                slave_ids = [self._configs[did].slave_id for did in device_ids]
                logger.warning(
                    "modbus_shared_gateway",
                    host=host,
                    port=port,
                    device_ids=device_ids,
                    slave_ids=slave_ids,
                    message=(
                        f"Multiple devices share gateway {host}:{port} - "
                        f"polling will be serialized to prevent response mix-up. "
                        f"Devices: {device_ids} (slave_ids: {slave_ids})"
                    ),
                )

    async def _get_gateway_and_lock(
        self, device_id: str
    ) -> Tuple[AsyncModbusGateway, asyncio.Lock]:
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        # Key is (host, port) only - all devices on same gateway share connection
        gateway_key = (config.host, config.port)

        # Check if gateway is in cooldown (paused after failure)
        # This prevents stale RTU buffer from poisoning next device
        cooldown_until = self._gateway_cooldowns.get(gateway_key, 0)
        if cooldown_until > 0:
            now = time.time()
            if now < cooldown_until:
                wait_time = cooldown_until - now
                logger.warning(
                    "modbus_gateway_cooldown_wait",
                    host=config.host,
                    port=config.port,
                    wait_seconds=round(wait_time, 2),
                    message="Waiting for gateway cooldown before request",
                )
                await asyncio.sleep(wait_time)
            # Clear cooldown after waiting
            self._gateway_cooldowns.pop(gateway_key, None)

        async with self._manager_lock:
            if gateway_key not in self._gateways:
                self._gateways[gateway_key] = self._create_gateway(config)
                self._locks[gateway_key] = asyncio.Lock()
            return self._gateways[gateway_key], self._locks[gateway_key]

    async def _run_with_gateway(
        self, device_id: str, func_name: str, *args, **kwargs
    ):
        """Execute a gateway method directly - now truly async!

        Circuit breaker is applied in the higher-level methods like read_registers.
        No more asyncio.to_thread() wrapper - we await directly!
        """
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        gateway, lock = await self._get_gateway_and_lock(device_id)
        slave_id = config.slave_id

        async with lock:
            method = getattr(gateway, func_name)
            try:
                # Direct await - no to_thread wrapper!
                return await method(slave_id, *args, **kwargs)
            except ModbusException as exc:
                raise ModbusClientError(str(exc)) from exc
            except ConnectionError:
                # retry once after reconnecting
                gateway.close()
                await gateway.connect()
                if not gateway.is_connected():
                    raise ModbusClientError(
                        f"Failed to connect to gateway '{config.host}:{config.port}'"
                    ) from None
                method = getattr(gateway, func_name)
                # Direct await after reconnect
                return await method(slave_id, *args, **kwargs)

    async def read_registers(
        self,
        device_id: str,
        register_type: RegisterType,
        address: int,
        count: int,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[int]:
        from app.core.metrics import metrics_collector
        from app.database.crud import record_device_failure, record_device_success

        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        # Get circuit breaker for this device
        circuit = await self._circuit_breakers.get_or_create(device_id)

        start_time = time.time()
        success = False
        failure_reason: Optional[str] = None

        async def _execute_read():
            """Execute read and validate response - all inside circuit breaker."""
            response = await self._run_read_internal(
                device_id, register_type, address, count, retries=retries, timeout=timeout
            )

            # Validate response - failures here count toward circuit breaker
            if response is None:
                raise ModbusClientError(f"No response from device '{device_id}'")

            if getattr(response, "isError", lambda: False)():
                raise ModbusClientError(str(response))

            if hasattr(response, "registers"):
                registers = list(response.registers)
                return registers[:count]
            elif hasattr(response, "bits"):
                bits = [int(bit) for bit in response.bits]
                return bits[:count]
            else:
                raise ModbusClientError("Unexpected Modbus response format")

        try:
            result = await circuit.call(_execute_read)
            success = True
            # Record success to device health
            try:
                async with self._db_session_factory() as session:
                    await record_device_success(session, device_id)
            except Exception as e:
                logger.warning(
                    "device_health_record_success_failed",
                    device_id=device_id,
                    error=str(e),
                    message="Failed to record device success",
                )
            return result
        except CircuitOpenError:
            # Circuit breaker is intentionally open; do not treat as a device failure
            # and do not reset the gateway. The poller will skip until recovery.
            logger.debug(
                "device_circuit_open",
                device_id=device_id,
                host=config.host,
                port=config.port,
                message="Circuit breaker open, skipping gateway reset",
            )
            raise
        except Exception as e:
            failure_reason = str(e)
            # Record failure to device health
            try:
                async with self._db_session_factory() as session:
                    await record_device_failure(session, device_id)
            except Exception as health_err:
                logger.warning(
                    "device_health_record_failure_failed",
                    device_id=device_id,
                    error=str(health_err),
                    message="Failed to record device failure",
                )
            
            # CRITICAL: Reset gateway on failure to clear stale buffer
            # This prevents one bad device from poisoning other devices on shared gateway
            if "No response from device" in failure_reason or "ModbusIOException" in failure_reason:
                logger.debug(
                    "device_failure_gateway_reset",
                    device_id=device_id,
                    failure_reason=failure_reason,
                    host=config.host,
                    port=config.port,
                    message="Resetting gateway after device failure to prevent buffer poisoning",
                )
            await self.reset_gateway(device_id)
            raise
        finally:
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            metrics_collector.modbus.record_request(register_type, success, latency_ms)

    async def write_register(
        self, device_id: str, register_type: RegisterType, address: int, value: int
    ) -> None:
        if register_type is not RegisterType.HOLDING:
            raise ModbusClientError("Writing is only supported for holding registers")

        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        # Get circuit breaker for this device
        circuit = await self._circuit_breakers.get_or_create(device_id)

        async def _execute_write():
            """Execute write and validate response - all inside circuit breaker."""
            response = await self._run_with_gateway(
                device_id, "write_holding_register", address, value
            )

            if response is None:
                raise ModbusClientError(f"No response from device '{device_id}'")

            if getattr(response, "isError", lambda: False)():
                raise ModbusClientError(str(response))

        await circuit.call(_execute_write)

    async def _run_read_internal(
        self,
        device_id: str,
        register_type: RegisterType,
        address: int,
        count: int,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Internal read method - does not apply circuit breaker."""
        method_name = {
            RegisterType.HOLDING: "read_holding_registers",
            RegisterType.INPUT: "read_input_registers",
            RegisterType.COIL: "read_coils",
            RegisterType.DISCRETE: "read_discrete_inputs",
        }[register_type]
        return await self._run_with_gateway(
            device_id, method_name, address, count, retries=retries, timeout=timeout
        )

    async def reset_gateway(self, device_id: str) -> None:
        """Reset (close and remove) the gateway for a specific device.

        This is useful when a connection becomes unresponsive.
        The next request will create a fresh connection.

        Note: Resets the entire gateway (host:port), not just one device.
        """
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        # Key is (host, port) - resets the shared gateway
        gateway_key = (config.host, config.port)

        async with self._manager_lock:
            if gateway_key in self._gateways:
                gateway = self._gateways[gateway_key]
                gateway.close()  # AsyncModbusTcpClient.close() is sync
                del self._gateways[gateway_key]
                del self._locks[gateway_key]
                logger.info(
                    "modbus_gateway_reset",
                    device_id=device_id,
                    host=config.host,
                    port=config.port,
                    message="Gateway reset",
                )
            
            # Set cooldown for this gateway to let RTU buffer settle
            # Prevents stale frames from poisoning the next device on same gateway
            self._gateway_cooldowns[gateway_key] = time.time() + self._gateway_cooldown_seconds
            logger.debug(
                "modbus_gateway_cooldown_set",
                host=config.host,
                port=config.port,
                cooldown_seconds=self._gateway_cooldown_seconds,
                message="Gateway cooldown started after failure",
            )

    async def reload_configs(self, new_configs: Iterable[DeviceConfig]) -> None:
        """Reload device configurations dynamically.

        This closes connections for removed devices and updates the config map.
        Also handles devices that moved to different host/port (stale gateway cleanup).
        """
        old_device_ids = set(self._configs.keys())
        new_device_ids = {cfg.device_id for cfg in new_configs}
        removed = old_device_ids - new_device_ids

        # Close gateways for removed devices
        for device_id in removed:
            try:
                await self.reset_gateway(device_id)
            except DeviceNotFoundError:
                pass  # Already removed

        # Check for devices that changed host/port (moved endpoints)
        moved_devices: List[str] = []
        for new_cfg in new_configs:
            if new_cfg.device_id in self._configs:
                old_cfg = self._configs[new_cfg.device_id]
                old_endpoint = (old_cfg.host, old_cfg.port)
                new_endpoint = (new_cfg.host, new_cfg.port)
                if old_endpoint != new_endpoint:
                    # Device moved to different endpoint - close old gateway
                    old_gateway_key = old_endpoint
                    if old_gateway_key in self._gateways:
                        try:
                            await self.reset_gateway(new_cfg.device_id)
                            moved_devices.append(new_cfg.device_id)
                        except DeviceNotFoundError:
                            pass

        # Update configs
        self._configs = {cfg.device_id: cfg for cfg in new_configs}

        # Re-validate gateway config after reload
        self._validate_gateway_config()

        logger.info(
            "modbus_configs_reloaded",
            device_count=len(new_configs),
            device_ids=[cfg.device_id for cfg in new_configs],
            message="Device configurations reloaded",
        )

    async def close_all(self) -> None:
        """Close all Modbus connections."""
        for gateway in self._gateways.values():
            gateway.close()  # close() is sync for AsyncModbusTcpClient
        self._gateways.clear()
        self._locks.clear()

    def list_devices(self) -> Tuple[str, ...]:
        return tuple(self._configs.keys())

    def get_config(self, device_id: str) -> Optional[DeviceConfig]:
        return self._configs.get(device_id)

    def get_gateways_status(self) -> List[dict]:
        """Return status of all active gateways."""
        status_list = []
        for (host, port), gateway in self._gateways.items():
            # Get all devices using this gateway
            device_ids = [
                dev_id for dev_id, cfg in self._configs.items()
                if cfg.host == host and cfg.port == port
            ]
            slave_ids = [self._configs[dev_id].slave_id for dev_id in device_ids]
            status_list.append({
                "host": host,
                "port": port,
                "device_ids": device_ids,
                "slave_ids": slave_ids,
                "connected": gateway.is_connected(),
            })
        return status_list

    def get_circuit_status(self) -> Dict[str, dict]:
        """Return status of all circuit breakers."""
        return self._circuit_breakers.get_all_status()

    async def reset_circuit(self, device_id: str) -> bool:
        """Reset circuit breaker for a device.

        Returns True if reset was successful, False if device not found.
        """
        return await self._circuit_breakers.reset(device_id)
