"""CRUD operations for Modbus devices."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging_config import get_logger
from app.database.models import (
    ModbusDevice,
    ModbusDeviceUpdate,
    PollingTarget,
    PollingTargetUpdate,
)

logger = get_logger(__name__)


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
    try:
        session.add(device)
        await session.commit()
        await session.refresh(device)
        logger.info(
            "device_created",
            device_id=device.device_id,
            host=device.host,
            port=device.port,
            message="Device created successfully",
        )
        return device
    except Exception as e:
        await session.rollback()
        logger.error(
            "device_create_failed",
            device_id=device.device_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to create device",
        )
        raise


async def update_device(
    session: AsyncSession,
    device_id: str,
    device_update: ModbusDeviceUpdate,
) -> Optional[ModbusDevice]:
    """Update an existing device configuration."""
    try:
        device = await get_device(session, device_id)
        if not device:
            return None

        # Update fields
        update_data = device_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(device, key, value)

        device.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(device)
        logger.info(
            "device_updated",
            device_id=device_id,
            updated_fields=list(update_data.keys()),
            message="Device updated successfully",
        )
        return device
    except Exception as e:
        await session.rollback()
        logger.error(
            "device_update_failed",
            device_id=device_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to update device",
        )
        raise


async def delete_device(session: AsyncSession, device_id: str) -> bool:
    """Soft delete a device (set is_active to False)."""
    try:
        device = await get_device(session, device_id)
        if not device:
            return False

        device.is_active = False
        device.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "device_deleted",
            device_id=device_id,
            message="Device soft-deleted successfully",
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.error(
            "device_delete_failed",
            device_id=device_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to delete device",
        )
        raise


async def activate_device(session: AsyncSession, device_id: str) -> bool:
    """Reactivate a device (set is_active to True)."""
    try:
        device = await get_device(session, device_id)
        if not device:
            return False

        device.is_active = True
        device.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "device_activated",
            device_id=device_id,
            message="Device activated successfully",
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.error(
            "device_activate_failed",
            device_id=device_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to activate device",
        )
        raise


# ============================================================
# CRUD operations for polling targets
# ============================================================


async def get_all_active_polling_targets(
    session: AsyncSession,
) -> List[PollingTarget]:
    """Get all active polling targets from database."""
    from app.database.models import PollingTarget

    result = await session.execute(select(PollingTarget).where(PollingTarget.is_active))
    return list(result.scalars().all())


async def get_all_polling_targets(session: AsyncSession) -> List[PollingTarget]:
    """Get all polling targets (including inactive) from database."""
    from app.database.models import PollingTarget

    result = await session.execute(select(PollingTarget))
    return list(result.scalars().all())


async def get_polling_target(
    session: AsyncSession, target_id: int
) -> Optional["PollingTarget"]:
    """Get a specific polling target by ID."""
    from app.database.models import PollingTarget

    result = await session.execute(
        select(PollingTarget).where(PollingTarget.id == target_id)
    )
    return result.scalar_one_or_none()


async def get_polling_targets_by_device(
    session: AsyncSession, device_id: str
) -> List["PollingTarget"]:
    """Get all active polling targets for a specific device."""
    from app.database.models import PollingTarget

    result = await session.execute(
        select(PollingTarget).where(
            PollingTarget.device_id == device_id, PollingTarget.is_active
        )
    )
    return list(result.scalars().all())


async def create_polling_target(
    session: AsyncSession, target: "PollingTarget"
) -> "PollingTarget":
    """Create a new polling target."""
    try:
        session.add(target)
        await session.commit()
        await session.refresh(target)
        logger.info(
            "polling_target_created",
            target_id=target.id,
            device_id=target.device_id,
            message="Polling target created successfully",
        )
        return target
    except Exception as e:
        await session.rollback()
        logger.error(
            "polling_target_create_failed",
            device_id=target.device_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to create polling target",
        )
        raise


async def update_polling_target(
    session: AsyncSession,
    target_id: int,
    target_update: PollingTargetUpdate,
) -> Optional[PollingTarget]:
    """Update an existing polling target configuration."""
    try:
        target = await get_polling_target(session, target_id)
        if not target:
            return None

        # Update fields
        update_data = target_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(target, key, value)

        target.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(target)
        logger.info(
            "polling_target_updated",
            target_id=target_id,
            updated_fields=list(update_data.keys()),
            message="Polling target updated successfully",
        )
        return target
    except Exception as e:
        await session.rollback()
        logger.error(
            "polling_target_update_failed",
            target_id=target_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to update polling target",
        )
        raise


async def delete_polling_target(session: AsyncSession, target_id: int) -> bool:
    """Soft delete a polling target (set is_active to False)."""
    try:
        target = await get_polling_target(session, target_id)
        if not target:
            return False

        target.is_active = False
        target.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "polling_target_deleted",
            target_id=target_id,
            message="Polling target soft-deleted successfully",
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.error(
            "polling_target_delete_failed",
            target_id=target_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to delete polling target",
        )
        raise


async def activate_polling_target(session: AsyncSession, target_id: int) -> bool:
    """Reactivate a polling target (set is_active to True)."""
    try:
        target = await get_polling_target(session, target_id)
        if not target:
            return False

        target.is_active = True
        target.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "polling_target_activated",
            target_id=target_id,
            message="Polling target activated successfully",
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.error(
            "polling_target_activate_failed",
            target_id=target_id,
            error=str(e),
            error_type=type(e).__name__,
            message="Failed to activate polling target",
        )
        raise
