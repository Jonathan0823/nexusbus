"""Admin API routes for managing Modbus devices."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.connection import get_session
from app.database.models import (
    ModbusDevice,
    ModbusDeviceCreate,
    ModbusDeviceResponse,
    ModbusDeviceUpdate,
)
from app.dependencies import get_modbus_manager
from app.core.modbus_client import ModbusClientManager

router = APIRouter(prefix="/admin/devices", tags=["admin"])


@router.get("", response_model=List[ModbusDeviceResponse])
async def list_all_devices(
    session: AsyncSession = Depends(get_session),
) -> List[ModbusDevice]:
    """List all Modbus devices (including inactive)."""
    return await crud.get_all_devices(session)


@router.get("/active", response_model=List[ModbusDeviceResponse])
async def list_active_devices(
    session: AsyncSession = Depends(get_session),
) -> List[ModbusDevice]:
    """List only active Modbus devices."""
    return await crud.get_all_active_devices(session)


@router.get("/{device_id}", response_model=ModbusDeviceResponse)
async def get_device_detail(
    device_id: str,
    session: AsyncSession = Depends(get_session),
) -> ModbusDevice:
    """Get details of a specific device."""
    device = await crud.get_device(session, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return device


@router.post("", response_model=ModbusDeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_new_device(
    device_create: ModbusDeviceCreate,
    session: AsyncSession = Depends(get_session),
) -> ModbusDevice:
    """Create a new Modbus device configuration."""
    # Check if device already exists
    existing = await crud.get_device(session, device_create.device_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device '{device_create.device_id}' already exists"
        )
    
    # Create new device
    db_device = ModbusDevice(**device_create.model_dump())
    return await crud.create_device(session, db_device)


@router.put("/{device_id}", response_model=ModbusDeviceResponse)
async def update_device_config(
    device_id: str,
    device_update: ModbusDeviceUpdate,
    session: AsyncSession = Depends(get_session),
) -> ModbusDevice:
    """Update device configuration."""
    updated = await crud.update_device(session, device_id, device_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    return updated


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a device (set is_active to False)."""
    success = await crud.delete_device(session, device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )


@router.post("/{device_id}/activate", response_model=ModbusDeviceResponse)
async def activate_device(
    device_id: str,
    session: AsyncSession = Depends(get_session),
) -> ModbusDevice:
    """Reactivate a device."""
    success = await crud.activate_device(session, device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found"
        )
    device = await crud.get_device(session, device_id)
    return device


@router.post("/reload", status_code=status.HTTP_200_OK)
async def reload_devices(
    manager: ModbusClientManager = Depends(get_modbus_manager),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reload device configurations from database into ModbusClientManager."""
    from app.config.devices import load_device_configs
    
    # Load fresh configs from database
    new_configs = await load_device_configs(session)
    
    # Reload the manager
    await manager.reload_configs(new_configs)
    
    return {
        "status": "ok",
        "message": f"Reloaded {len(new_configs)} device(s)",
        "devices": [cfg.device_id for cfg in new_configs]
    }
