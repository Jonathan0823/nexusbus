"""REST API endpoints for Modbus middleware."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config.devices import API_REQUEST_TIMEOUT_SECONDS, DEVICE_CONFIGS
from app.core.cache import RegisterCache
from app.core.modbus_client import (
    DeviceNotFoundError,
    ModbusClientError,
    ModbusClientManager,
    RegisterType,
)
from app.dependencies import get_cache, get_modbus_manager
from app.schemas import CacheSource, WriteRegisterRequest

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=List[dict])
async def list_devices() -> List[dict]:
    return [
        {
            "device_id": cfg.device_id,
            "host": cfg.host,
            "port": cfg.port,
            "slave_id": cfg.slave_id,
            "timeout": cfg.timeout,
            "gateway": f"{cfg.host}:{cfg.port}",
        }
        for cfg in DEVICE_CONFIGS
    ]


@router.get("/gateways", tags=["system"])
async def list_gateways(
    manager: ModbusClientManager = Depends(get_modbus_manager),
) -> List[dict]:
    """List all active Modbus gateways and their connection status."""
    return manager.get_gateways_status()


@router.get("/{device_id}/registers")
async def read_registers(
    device_id: str,
    address: int = Query(..., ge=0),
    count: int = Query(1, ge=1, le=125),
    register_type: RegisterType = Query(RegisterType.HOLDING),
    source: CacheSource = Query(CacheSource.LIVE),
    manager: ModbusClientManager = Depends(get_modbus_manager),
    cache: RegisterCache = Depends(get_cache),
) -> dict:
    try:
        used_source = source
        cached_entry = None
        if source is CacheSource.CACHE:
            cached_entry = await cache.get(device_id, register_type, address, count)
            if cached_entry:
                return _serialize_read_response(
                    device_id,
                    register_type,
                    address,
                    count,
                    cached_entry.data,
                    used_source,
                    cached_entry.timestamp,
                )
            used_source = CacheSource.LIVE

        # Wrap Modbus operation with timeout
        try:
            data = await asyncio.wait_for(
                manager.read_registers(device_id, register_type, address, count),
                timeout=API_REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # Reset the gateway connection on timeout
            await manager.reset_gateway(device_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timeout after {API_REQUEST_TIMEOUT_SECONDS} seconds. Connection reset."
            )
        
        await cache.set(device_id, register_type, address, count, data)
        return _serialize_read_response(
            device_id,
            register_type,
            address,
            count,
            data,
            used_source,
            None,
        )
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ModbusClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/{device_id}/registers/write")
async def write_register(
    device_id: str,
    payload: WriteRegisterRequest,
    manager: ModbusClientManager = Depends(get_modbus_manager),
    cache: RegisterCache = Depends(get_cache),
) -> dict:
    try:
        # Wrap Modbus operations with timeout
        try:
            await asyncio.wait_for(
                manager.write_register(
                    device_id,
                    payload.register_type,
                    payload.address,
                    payload.value,
                ),
                timeout=API_REQUEST_TIMEOUT_SECONDS
            )
            # refresh cache for that register if available
            data = await asyncio.wait_for(
                manager.read_registers(
                    device_id,
                    payload.register_type,
                    payload.address,
                    1,
                ),
                timeout=API_REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # Reset the gateway connection on timeout
            await manager.reset_gateway(device_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timeout after {API_REQUEST_TIMEOUT_SECONDS} seconds. Connection reset."
            )
        
        await cache.set(
            device_id,
            payload.register_type,
            payload.address,
            1,
            data,
        )
        return {
            "device_id": device_id,
            "status": "ok",
            "address": payload.address,
            "value": payload.value,
            "register_type": payload.register_type,
        }
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ModbusClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _serialize_read_response(
    device_id: str,
    register_type: RegisterType,
    address: int,
    count: int,
    data: List[int],
    source: CacheSource,
    cached_at: Optional[datetime],
) -> dict:
    body = {
        "device_id": device_id,
        "register_type": register_type,
        "address": address,
        "count": count,
        "values": data,
        "source": source,
    }
    if cached_at:
        body["cached_at"] = cached_at.isoformat()
    return body
