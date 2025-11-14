"""FastAPI dependency helpers for shared services."""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.cache import RegisterCache
from app.core.modbus_client import ModbusClientManager


def get_modbus_manager(request: Request) -> ModbusClientManager:
    manager = getattr(request.app.state, "modbus_manager", None)
    if manager is None:
        raise RuntimeError("Modbus manager is not initialized")
    return manager


def get_cache(
    request: Request, _manager: ModbusClientManager = Depends(get_modbus_manager)
) -> RegisterCache:
    cache = getattr(request.app.state, "register_cache", None)
    if cache is None:
        raise RuntimeError("Register cache is not initialized")
    return cache
