"""Modbus client session and manager abstractions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple, Type

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType


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


class ModbusSession:
    """Encapsulates Modbus client lifecycle and basic operations."""

    def __init__(
        self,
        host: str,
        port: int,
        slave_id: int,
        timeout: int = 3,
        framer: FramerType = FramerType.SOCKET,
        client_cls: Type[ModbusTcpClient] = ModbusTcpClient,
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self._client = client_cls(
            host,
            port=port,
            timeout=timeout,
            framer=framer,
        )

    def connect(self) -> bool:
        return self._client.connect()

    def ensure_connection(self) -> None:
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError(
                    f"Unable to connect to Modbus device {self.host}:{self.port}"
                )

    def read_holding_registers(self, address: int, count: int):
        self.ensure_connection()
        return self._client.read_holding_registers(
            address=address, count=count, slave=self.slave_id
        )

    def read_input_registers(self, address: int, count: int):
        self.ensure_connection()
        return self._client.read_input_registers(
            address=address, count=count, slave=self.slave_id
        )

    def read_coils(self, address: int, count: int):
        self.ensure_connection()
        return self._client.read_coils(address=address, count=count, slave=self.slave_id)

    def read_discrete_inputs(self, address: int, count: int):
        self.ensure_connection()
        return self._client.read_discrete_inputs(
            address=address, count=count, slave=self.slave_id
        )

    def write_holding_register(self, address: int, value: int):
        self.ensure_connection()
        return self._client.write_register(
            address=address, value=value, slave=self.slave_id
        )

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
    """Manages Modbus sessions per device and exposes async-friendly helpers."""

    def __init__(self, device_configs: Iterable[DeviceConfig]) -> None:
        self._configs: Dict[str, DeviceConfig] = {cfg.device_id: cfg for cfg in device_configs}
        self._sessions: Dict[str, ModbusSession] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._manager_lock = asyncio.Lock()

    def _create_session(self, device_id: str) -> ModbusSession:
        config = self._configs.get(device_id)
        if not config:
            raise DeviceNotFoundError(f"Unknown device_id '{device_id}'")
        return ModbusSession(
            host=config.host,
            port=config.port,
            slave_id=config.slave_id,
            timeout=config.timeout,
            framer=config.framer,
        )

    async def _get_session(self, device_id: str) -> ModbusSession:
        async with self._manager_lock:
            if device_id not in self._sessions:
                self._sessions[device_id] = self._create_session(device_id)
                self._locks[device_id] = asyncio.Lock()
            return self._sessions[device_id]

    async def _run_with_session(self, device_id: str, func_name: str, *args, **kwargs):
        session = await self._get_session(device_id)
        lock = self._locks[device_id]
        async with lock:
            method = getattr(session, func_name)
            try:
                return await asyncio.to_thread(method, *args, **kwargs)
            except ModbusException as exc:
                raise ModbusClientError(str(exc)) from exc
            except ConnectionError:
                # retry once after reconnecting
                session.close()
                if not session.connect():
                    raise ModbusClientError(
                        f"Failed to connect to device '{device_id}'"
                    ) from None
                method = getattr(session, func_name)
                return await asyncio.to_thread(method, *args, **kwargs)

    async def read_registers(
        self, device_id: str, register_type: RegisterType, address: int, count: int
    ) -> List[int]:
        response = await self._run_read(device_id, register_type, address, count)
        if response.isError():  # type: ignore[attr-defined]
            raise ModbusClientError(str(response))
        if hasattr(response, "registers"):
            return list(response.registers)
        if hasattr(response, "bits"):
            return [int(bit) for bit in response.bits]
        raise ModbusClientError("Unexpected Modbus response format")

    async def write_register(
        self, device_id: str, register_type: RegisterType, address: int, value: int
    ) -> None:
        if register_type is not RegisterType.HOLDING:
            raise ModbusClientError("Writing is only supported for holding registers")
        response = await self._run_with_session(
            device_id, "write_holding_register", address, value
        )
        if response.isError():  # type: ignore[attr-defined]
            raise ModbusClientError(str(response))

    async def _run_read(
        self, device_id: str, register_type: RegisterType, address: int, count: int
    ):
        method_name = {
            RegisterType.HOLDING: "read_holding_registers",
            RegisterType.INPUT: "read_input_registers",
            RegisterType.COIL: "read_coils",
            RegisterType.DISCRETE: "read_discrete_inputs",
        }[register_type]
        return await self._run_with_session(device_id, method_name, address, count)

    async def close_all(self) -> None:
        for session in self._sessions.values():
            await asyncio.to_thread(session.close)
        self._sessions.clear()
        self._locks.clear()

    def list_devices(self) -> Tuple[str, ...]:
        return tuple(self._configs.keys())

    def get_config(self, device_id: str) -> Optional[DeviceConfig]:
        return self._configs.get(device_id)
