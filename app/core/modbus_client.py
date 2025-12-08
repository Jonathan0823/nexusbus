"""Modbus client session and manager abstractions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple, Type

from pymodbus.client import ModbusTcpClient
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


class ModbusGateway:
    """
    Encapsulates a shared Modbus TCP connection to a gateway/host.
    Serves multiple slave_ids behind the same IP:Port.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: int = 3,
        framer: FramerType = FramerType.SOCKET,
        max_retries: int = 5,
        retry_delay: float = 0.1,
        client_cls: Type[ModbusTcpClient] = ModbusTcpClient,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = client_cls(
            host,
            port=port,
            timeout=timeout,
            framer=framer,
            retries=0,  # Disable internal pymodbus retries!
        )

    def connect(self) -> bool:
        return self._client.connect()

    def ensure_connection(self) -> None:
        if not self.is_connected():
            if not self.connect():
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
        if getattr(response, 'isError', lambda: False)():
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
        if hasattr(response, 'slave_id') and response.slave_id != slave_id:
            logger.warning(
                "modbus_slave_id_mismatch",
                operation=operation,
                requested_slave_id=slave_id,
                received_slave_id=response.slave_id,
                message="Slave ID mismatch, will retry",
            )
            return False
        return True

    def _apply_temp_timeout(self, timeout: Optional[float]):
        """Apply temporary timeout to client and socket."""
        if timeout is None:
            return None
            
        # Save original timeout
        # Pymodbus structure might vary, try to get from common places
        original_timeout = getattr(self._client, "timeout", self.timeout)
        
        # Set new timeout on client object
        if hasattr(self._client, "timeout"):
            self._client.timeout = timeout
        if hasattr(self._client, "comm_params") and hasattr(self._client.comm_params, "timeout"):
            self._client.comm_params.timeout = timeout
            
        # Set new timeout on actual socket if connected
        if self._client.socket:
            self._client.socket.settimeout(timeout)
            
        return original_timeout

    def _restore_timeout(self, original_timeout: Optional[float]):
        """Restore original timeout."""
        if original_timeout is None:
            return
            
        # Restore on client object
        if hasattr(self._client, "timeout"):
            self._client.timeout = original_timeout
        if hasattr(self._client, "comm_params") and hasattr(self._client.comm_params, "timeout"):
            self._client.comm_params.timeout = original_timeout
            
        # Restore on socket
        if self._client.socket:
            self._client.socket.settimeout(original_timeout)

    def _read_registers(
        self,
        slave_id: int,
        address: int,
        count: int,
        operation: str,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Generic method for reading registers/coils/discrete inputs.
        
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
        self.ensure_connection()
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
            raise ValueError(f"Invalid operation: {operation}. Must be one of {list(method_map.keys())}")
        
        read_method = method_map[operation]
        
        # Apply temporary timeout override
        orig_timeout = self._apply_temp_timeout(timeout)
        
        try:
            num_attempts = (retries if retries is not None else self.max_retries)
            if num_attempts < 1:
                num_attempts = 1
                
            for attempt in range(num_attempts):
                try:
                    response = read_method(
                        address=address, count=count, slave=slave_id
                    )
                    last_response = response
                    # Use appropriate operation name for logging
                    op_name = f"read_{operation}_registers" if operation in ("holding", "input") else f"read_{operation}s"
                    if self._is_valid_response(response, op_name, slave_id):
                        if attempt > 0:
                            logger.info(
                                "modbus_read_success_after_retry",
                                operation=op_name,
                                slave_id=slave_id,
                                attempts=attempt + 1,
                                message="Read succeeded after retries",
                            )
                        return response
                except (ModbusException, ModbusIOException, OSError) as exc:
                    last_exception = exc
                    exc_type = type(exc).__name__
                    op_name = f"read_{operation}_registers" if operation in ("holding", "input") else f"read_{operation}s"
                    logger.warning(
                        "modbus_read_exception",
                        operation=op_name,
                        slave_id=slave_id,
                        exception_type=exc_type,
                        exception=str(exc),
                        attempt=attempt + 1,
                        max_attempts=num_attempts,
                        message="Modbus exception, retrying",
                    )
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        # Re-apply timeout after reconnect
                        self._apply_temp_timeout(timeout)
                except Exception as exc:
                    last_exception = exc
                    op_name = f"read_{operation}_registers" if operation in ("holding", "input") else f"read_{operation}s"
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
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        # Re-apply timeout after reconnect
                        self._apply_temp_timeout(timeout)
                
                if attempt < num_attempts - 1:
                    op_name = f"read_{operation}_registers" if operation in ("holding", "input") else f"read_{operation}s"
                    if operation in ("holding", "input"):
                        logger.info(
                            "modbus_read_retry",
                            operation=op_name,
                            slave_id=slave_id,
                            attempt=attempt + 1,
                            max_attempts=num_attempts,
                        )
                    else:
                        logger.debug(
                            "modbus_read_retry",
                            operation=op_name,
                            slave_id=slave_id,
                            attempt=attempt + 1,
                            max_attempts=num_attempts,
                        )
                    time.sleep(self.retry_delay)
            
            op_name = f"read_{operation}_registers" if operation in ("holding", "input") else f"read_{operation}s"
            logger.error(
                "modbus_read_failed",
                operation=op_name,
                slave_id=slave_id,
                attempts=num_attempts,
                last_exception=str(last_exception) if last_exception else None,
                message="Read failed after all retries",
            )
            return last_response
        finally:
            self._restore_timeout(orig_timeout)

    def read_holding_registers(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        """Read holding registers."""
        return self._read_registers(slave_id, address, count, "holding", retries, timeout)

    def read_input_registers(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        """Read input registers."""
        return self._read_registers(slave_id, address, count, "input", retries, timeout)

    def read_coils(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        """Read coils."""
        return self._read_registers(slave_id, address, count, "coil", retries, timeout)

    def read_discrete_inputs(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        """Read discrete inputs."""
        return self._read_registers(slave_id, address, count, "discrete", retries, timeout)

    def write_holding_register(self, slave_id: int, address: int, value: int):
        self.ensure_connection()
        last_response = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.write_register(
                    address=address, value=value, slave=slave_id
                )
                last_response = response
                if self._is_valid_response(response, "write_holding_register", slave_id):
                    return response
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
                self.close()
                if attempt < self.max_retries - 1:
                    self.ensure_connection()

            if attempt < self.max_retries - 1:
                logger.debug(
                    "modbus_write_retry",
                    operation="write_holding_register",
                    slave_id=slave_id,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries,
                )
                time.sleep(self.retry_delay)
        return last_response

    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_socket_open())

    def close(self) -> None:
        if self.is_connected():
            self._client.close()


class ModbusClientError(Exception):
    """Base exception for Modbus client issues."""


class DeviceNotFoundError(ModbusClientError):
    pass


class ModbusClientManager:
    """
    Manages Modbus gateways and exposes device-centric helpers.
    Ensures only one connection exists per (Host, Port).
    """

    def __init__(self, device_configs: Iterable[DeviceConfig]) -> None:
        self._configs: Dict[str, DeviceConfig] = {
            cfg.device_id: cfg for cfg in device_configs
        }
        # Map (host, port) -> ModbusGateway
        self._gateways: Dict[Tuple[str, int], ModbusGateway] = {}
        # Map (host, port) -> Lock
        self._locks: Dict[Tuple[str, int], asyncio.Lock] = {}
        self._manager_lock = asyncio.Lock()
        
        # Circuit breaker registry (per device)
        self._circuit_breakers = CircuitBreakerRegistry(
            default_config=CircuitBreakerConfig(
                failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=float(settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT),
            )
        )

    def _create_gateway(self, config: DeviceConfig) -> ModbusGateway:
        return ModbusGateway(
            host=config.host,
            port=config.port,
            timeout=config.timeout,
            framer=config.framer,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
        )

    async def _get_gateway_and_lock(self, device_id: str) -> Tuple[ModbusGateway, asyncio.Lock]:
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")
        
        key = (config.host, config.port)
        
        async with self._manager_lock:
            if key not in self._gateways:
                self._gateways[key] = self._create_gateway(config)
                self._locks[key] = asyncio.Lock()
            return self._gateways[key], self._locks[key]

    async def _run_with_gateway(self, device_id: str, func_name: str, *args, **kwargs):
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")

        # Get circuit breaker for this device
        circuit = await self._circuit_breakers.get_or_create(device_id)
        
        async def _execute():
            gateway, lock = await self._get_gateway_and_lock(device_id)
            slave_id = config.slave_id
            
            async with lock:
                method = getattr(gateway, func_name)
                try:
                    return await asyncio.to_thread(method, slave_id, *args, **kwargs)
                except ModbusException as exc:
                    raise ModbusClientError(str(exc)) from exc
                except ConnectionError:
                    # retry once after reconnecting
                    gateway.close()
                    if not gateway.connect():
                        raise ModbusClientError(
                            f"Failed to connect to gateway '{config.host}:{config.port}'"
                        ) from None
                    method = getattr(gateway, func_name)
                    return await asyncio.to_thread(method, slave_id, *args, **kwargs)
        
        # Execute through circuit breaker
        return await circuit.call(_execute)

    async def read_registers(
        self, device_id: str, register_type: RegisterType, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ) -> List[int]:
        import time
        from app.core.metrics import metrics_collector
        
        start_time = time.time()
        success = False
        
        try:
            response = await self._run_read(device_id, register_type, address, count, retries=retries, timeout=timeout)
            
            if response is None:
                raise ModbusClientError(f"No response from device '{device_id}'")
                
            if getattr(response, 'isError', lambda: False)():
                raise ModbusClientError(str(response))
                
            if hasattr(response, "registers"):
                registers = list(response.registers)
                result = registers[:count]
            elif hasattr(response, "bits"):
                bits = [int(bit) for bit in response.bits]
                result = bits[:count]
            else:
                raise ModbusClientError("Unexpected Modbus response format")
            
            success = True
            return result
        finally:
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            metrics_collector.modbus.record_request(register_type, success, latency_ms)

    async def write_register(
        self, device_id: str, register_type: RegisterType, address: int, value: int
    ) -> None:
        if register_type is not RegisterType.HOLDING:
            raise ModbusClientError("Writing is only supported for holding registers")
        response = await self._run_with_gateway(
            device_id, "write_holding_register", address, value
        )
        
        if response is None:
            raise ModbusClientError(f"No response from device '{device_id}'")
            
        if getattr(response, 'isError', lambda: False)():
            raise ModbusClientError(str(response))

    async def _run_read(
        self, device_id: str, register_type: RegisterType, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ):
        method_name = {
            RegisterType.HOLDING: "read_holding_registers",
            RegisterType.INPUT: "read_input_registers",
            RegisterType.COIL: "read_coils",
            RegisterType.DISCRETE: "read_discrete_inputs",
        }[register_type]
        return await self._run_with_gateway(device_id, method_name, address, count, retries=retries, timeout=timeout)

    async def reset_gateway(self, device_id: str) -> None:
        """Reset (close and remove) the gateway for a specific device.
        
        This is useful when a connection becomes unresponsive.
        The next request will create a fresh connection.
        """
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")
        
        key = (config.host, config.port)
        
        async with self._manager_lock:
            if key in self._gateways:
                gateway = self._gateways[key]
                await asyncio.to_thread(gateway.close)
                del self._gateways[key]
                del self._locks[key]
                logger.info(
                    "modbus_gateway_reset",
                    device_id=device_id,
                    host=config.host,
                    port=config.port,
                    message="Gateway reset",
                )

    async def reload_configs(self, new_configs: Iterable[DeviceConfig]) -> None:
        """Reload device configurations dynamically.
        
        This closes connections for removed devices and updates the config map.
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
        
        # Update configs
        self._configs = {cfg.device_id: cfg for cfg in new_configs}
        logger.info(
            "modbus_configs_reloaded",
            device_count=len(new_configs),
            device_ids=[cfg.device_id for cfg in new_configs],
            message="Device configurations reloaded",
        )

    async def close_all(self) -> None:
        for gateway in self._gateways.values():
            await asyncio.to_thread(gateway.close)
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
            status_list.append({
                "host": host,
                "port": port,
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

