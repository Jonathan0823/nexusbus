"""CRUD operations for Modbus devices."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database.models import ModbusDevice, ModbusDeviceUpdate


async def get_all_active_devices(session: AsyncSession) -> List[ModbusDevice]:
    """Get all active Modbus devices from database."""
    result = await session.execute(select(ModbusDevice).where(ModbusDevice.is_active))
    return list(result.scalars().all())


async def get_all_devices(session: AsyncSession) -> List[ModbusDevice]:
    """Get all Modbus devices (including inactive) from database."""
    result = await session.execute(select(ModbusDevice))
    return list(result.scalars().all())


async def get_device(session: AsyncSession, device_id: str) -> Optional[ModbusDevice]:
    """Get a specific device by ID."""
    result = await session.execute(
        select(ModbusDevice).where(ModbusDevice.device_id == device_id)
    )
    return result.scalar_one_or_none()


async def create_device(session: AsyncSession, device: ModbusDevice) -> ModbusDevice:
    """Create a new Modbus device."""
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


async def update_device(
    session: AsyncSession,
    device_id: str,
    device_update: ModbusDeviceUpdate,
) -> Optional[ModbusDevice]:
    """Update an existing device configuration."""
    device = await get_device(session, device_id)
    if not device:
        return None

    # Update fields
    update_data = device_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    device.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(device)
    return device


async def delete_device(session: AsyncSession, device_id: str) -> bool:
    """Soft delete a device (set is_active to False)."""
    device = await get_device(session, device_id)
    if not device:
        return False

    device.is_active = False
    device.updated_at = datetime.utcnow()
    await session.commit()
    return True


async def activate_device(session: AsyncSession, device_id: str) -> bool:
    """Reactivate a device (set is_active to True)."""
    device = await get_device(session, device_id)
    if not device:
        return False

    device.is_active = True
    device.updated_at = datetime.utcnow()
    await session.commit()
    return True
