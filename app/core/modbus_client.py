"""Modbus client session and manager abstractions."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple, Type

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.framer import FramerType
from pymodbus.pdu import ExceptionResponse

logger = logging.getLogger(__name__)


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
            logger.warning(f"{operation}: No response (None) from slave_id={slave_id}")
            return False
        
        # Check if response is ExceptionResponse (includes CRC errors)
        if isinstance(response, ExceptionResponse):
            logger.warning(
                f"{operation}: Exception response from slave_id={slave_id} "
                f"(code={response.exception_code})"
            )
            return False
        
        # Check if response is error
        # Use getattr to safely check isError, defaulting to False if not present
        if getattr(response, 'isError', lambda: False)():
            error_msg = str(response)
            logger.warning(
                f"{operation}: Error response from slave_id={slave_id}: {error_msg}"
            )
            return False
        
        # Additional check for slave_id if available
        if hasattr(response, 'slave_id') and response.slave_id != slave_id:
            logger.warning(
                f"{operation}: request for slave_id={slave_id} but got slave_id={response.slave_id}. Retrying..."
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

    def read_holding_registers(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        self.ensure_connection()
        last_response = None
        last_exception = None
        
        # Apply temporary timeout override
        orig_timeout = self._apply_temp_timeout(timeout)
        
        try:
            num_attempts = (retries if retries is not None else self.max_retries)
            if num_attempts < 1:
                num_attempts = 1
                
            for attempt in range(num_attempts):
                try:
                    response = self._client.read_holding_registers(
                        address=address, count=count, slave=slave_id
                    )
                    last_response = response
                    if self._is_valid_response(response, "read_holding_registers", slave_id):
                        if attempt > 0:
                            logger.info(f"read_holding_registers succeeded after {attempt + 1} attempts for slave_id={slave_id}")
                        return response
                except (ModbusException, ModbusIOException) as exc:
                    last_exception = exc
                    exc_type = type(exc).__name__
                    logger.warning(f"read_holding_registers {exc_type} for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        # Re-apply timeout after reconnect
                        self._apply_temp_timeout(timeout)
                except Exception as exc:
                    last_exception = exc
                    logger.error(f"read_holding_registers unexpected error for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        # Re-apply timeout after reconnect
                        self._apply_temp_timeout(timeout)
                
                if attempt < num_attempts - 1:
                    logger.info(f"read_holding_registers retry {attempt + 1}/{num_attempts} for slave_id={slave_id}")
                    time.sleep(self.retry_delay)
            
            logger.error(f"read_holding_registers failed after {num_attempts} attempts for slave_id={slave_id}. Last exception: {last_exception}")
            return last_response
        finally:
            self._restore_timeout(orig_timeout)

    def read_input_registers(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        self.ensure_connection()
        last_response = None
        last_exception = None
        
        orig_timeout = self._apply_temp_timeout(timeout)
        
        try:
            num_attempts = (retries if retries is not None else self.max_retries)
            if num_attempts < 1:
                num_attempts = 1
                
            for attempt in range(num_attempts):
                try:
                    response = self._client.read_input_registers(
                        address=address, count=count, slave=slave_id
                    )
                    last_response = response
                    if self._is_valid_response(response, "read_input_registers", slave_id):
                        if attempt > 0:
                            logger.info(f"read_input_registers succeeded after {attempt + 1} attempts for slave_id={slave_id}")
                        return response
                except (ModbusException, ModbusIOException) as exc:
                    last_exception = exc
                    exc_type = type(exc).__name__
                    logger.warning(f"read_input_registers {exc_type} for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        self._apply_temp_timeout(timeout)
                except Exception as exc:
                    last_exception = exc
                    logger.error(f"read_input_registers unexpected error for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        self._apply_temp_timeout(timeout)

                if attempt < num_attempts - 1:
                    logger.info(f"read_input_registers retry {attempt + 1}/{num_attempts} for slave_id={slave_id}")
                    time.sleep(self.retry_delay)
            logger.error(f"read_input_registers failed after {num_attempts} attempts for slave_id={slave_id}. Last exception: {last_exception}")
            return last_response
        finally:
            self._restore_timeout(orig_timeout)

    def read_coils(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        self.ensure_connection()
        last_response = None
        
        orig_timeout = self._apply_temp_timeout(timeout)
        
        try:
            num_attempts = (retries if retries is not None else self.max_retries)
            if num_attempts < 1:
                num_attempts = 1
                
            for attempt in range(num_attempts):
                try:
                    response = self._client.read_coils(
                        address=address, count=count, slave=slave_id
                    )
                    last_response = response
                    if self._is_valid_response(response, "read_coils", slave_id):
                        return response
                except ModbusException as exc:
                    logger.warning(f"read_coils exception for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        self._apply_temp_timeout(timeout)

                if attempt < num_attempts - 1:
                    logger.debug(f"Retry {attempt + 1}/{num_attempts} for slave_id={slave_id}")
                    time.sleep(self.retry_delay)
            return last_response
        finally:
            self._restore_timeout(orig_timeout)

    def read_discrete_inputs(self, slave_id: int, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None):
        self.ensure_connection()
        last_response = None
        
        orig_timeout = self._apply_temp_timeout(timeout)
        
        try:
            num_attempts = (retries if retries is not None else self.max_retries)
            if num_attempts < 1:
                num_attempts = 1
                
            for attempt in range(num_attempts):
                try:
                    response = self._client.read_discrete_inputs(
                        address=address, count=count, slave=slave_id
                    )
                    last_response = response
                    if self._is_valid_response(response, "read_discrete_inputs", slave_id):
                        return response
                except ModbusException as exc:
                    logger.warning(f"read_discrete_inputs exception for slave_id={slave_id}: {exc}. Retrying...")
                    self.close()
                    if attempt < num_attempts - 1:
                        self.ensure_connection()
                        self._apply_temp_timeout(timeout)

                if attempt < num_attempts - 1:
                    logger.debug(f"Retry {attempt + 1}/{num_attempts} for slave_id={slave_id}")
                    time.sleep(self.retry_delay)
            return last_response
        finally:
            self._restore_timeout(orig_timeout)

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
            except ModbusException as exc:
                logger.warning(f"write_holding_register exception for slave_id={slave_id}: {exc}. Retrying...")
                self.close()
                if attempt < self.max_retries - 1:
                    self.ensure_connection()

            if attempt < self.max_retries - 1:
                logger.debug(f"Retry {attempt + 1}/{self.max_retries} for slave_id={slave_id}")
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

        gateway, lock = await self._get_gateway_and_lock(device_id)
        
        # Inject slave_id as the first argument to the gateway method
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

    async def read_registers(
        self, device_id: str, register_type: RegisterType, address: int, count: int, retries: Optional[int] = None, timeout: Optional[float] = None
    ) -> List[int]:
        response = await self._run_read(device_id, register_type, address, count, retries=retries, timeout=timeout)
        
        if response is None:
            raise ModbusClientError(f"No response from device '{device_id}'")
            
        if getattr(response, 'isError', lambda: False)():
            raise ModbusClientError(str(response))
            
        if hasattr(response, "registers"):
            registers = list(response.registers)
            return registers[:count]
        if hasattr(response, "bits"):
            bits = [int(bit) for bit in response.bits]
            return bits[:count]
        raise ModbusClientError("Unexpected Modbus response format")

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
                logger.info(f"Reset gateway {config.host}:{config.port} for device '{device_id}'")

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
        logger.info(f"Reloaded {len(new_configs)} device config(s)")

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

