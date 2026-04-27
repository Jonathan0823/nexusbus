"""CRUD operations for Modbus devices."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging_config import get_logger
from app.database.models import (
    ModbusDevice,
    ModbusDeviceUpdate,
    PollingTarget,
    PollingTargetUpdate,
    DeviceHealth,
    DeviceState,
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

        device.updated_at = datetime.now()
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
        device.updated_at = datetime.now()
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
        device.updated_at = datetime.now()
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

        target.updated_at = datetime.now()
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
        target.updated_at = datetime.now()
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
        target.updated_at = datetime.now()
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


# =============================================================================
# Device Health CRUD
# =============================================================================

async def get_device_health(session: AsyncSession, device_id: str) -> Optional[DeviceHealth]:
    """Get device health for a specific device."""
    result = await session.execute(
        select(DeviceHealth).where(DeviceHealth.device_id == device_id)
    )
    return result.scalar_one_or_none()


async def get_all_device_health(session: AsyncSession) -> List[DeviceHealth]:
    """Get health for all devices."""
    result = await session.execute(select(DeviceHealth))
    return list(result.scalars().all())


async def get_active_device_health(session: AsyncSession) -> List[DeviceHealth]:
    """Get health for devices that have a health record."""
    result = await session.execute(
        select(DeviceHealth).where(DeviceHealth.state != DeviceState.OFFLINE)
    )
    return list(result.scalars().all())


async def upsert_device_health(
    session: AsyncSession,
    device_id: str,
    state: DeviceState = DeviceState.HEALTHY,
) -> DeviceHealth:
    """Create or update device health record."""
    health = await get_device_health(session, device_id)
    now = datetime.now()
    
    if health:
        health.state = state
        health.updated_at = now
    else:
        health = DeviceHealth(
            device_id=device_id,
            state=state,
            created_at=now,
            updated_at=now,
        )
        session.add(health)
    
    await session.commit()
    await session.refresh(health)
    return health


async def record_device_success(session: AsyncSession, device_id: str) -> Optional[DeviceHealth]:
    """Record a successful read for a device."""
    health = await get_device_health(session, device_id)
    now = datetime.now()
    
    if not health:
        health = DeviceHealth(
            device_id=device_id,
            state=DeviceState.HEALTHY,
            success_count=1,
            last_success=now,
            created_at=now,
            updated_at=now,
        )
        session.add(health)
    else:
        health.success_count += 1
        health.consecutive_failures = 0
        health.last_success = now
        health.quarantine_until = None  # Clear quarantine on success
        health.updated_at = now
        
        # Upgrade state if recovering
        if health.state == DeviceState.OFFLINE:
            health.state = DeviceState.DEGRADED
        elif health.state == DeviceState.DEGRADED:
            health.state = DeviceState.HEALTHY
    
    await session.commit()
    await session.refresh(health)
    return health


async def record_device_failure(session: AsyncSession, device_id: str) -> Optional[DeviceHealth]:
    """Record a failed read for a device.
    
    Sets quarantine_until with backoff:
    - 1st fail: 15s
    - 2nd: 30s
    - 3rd: 60s
    - cap at 300s (5 minutes)
    """
    health = await get_device_health(session, device_id)
    now = datetime.now()
    
    if not health:
        health = DeviceHealth(
            device_id=device_id,
            state=DeviceState.DEGRADED,
            failure_count=1,
            consecutive_failures=1,
            last_failure=now,
            quarantine_until=now,  # immediate quarantine on first failure
            created_at=now,
            updated_at=now,
        )
        session.add(health)
    else:
        health.failure_count += 1
        health.consecutive_failures += 1
        health.last_failure = now
        health.updated_at = now
        
        # Calculate quarantine backoff
        # 1st fail = 15s, 2nd = 30s, 3rd = 60s, cap at 300s
        consecutive = health.consecutive_failures
        backoff_seconds = min(15 * (2 ** (consecutive - 1)), 300)  # 15, 30, 60, 120, 240, 300...
        health.quarantine_until = datetime.fromtimestamp(now.timestamp() + backoff_seconds)
        
        logger.info(
            "device_quarantine_set",
            device_id=device_id,
            consecutive_failures=consecutive,
            quarantine_seconds=backoff_seconds,
            message=f"Device quarantined for {backoff_seconds}s after {consecutive} failures",
        )
        
        # Downgrade state based on consecutive failures
        if health.consecutive_failures >= 10:
            health.state = DeviceState.OFFLINE
        elif health.consecutive_failures >= 3:
            health.state = DeviceState.DEGRADED
    
    await session.commit()
    await session.refresh(health)
    return health


async def reset_device_health(session: AsyncSession, device_id: str) -> bool:
    """Reset device health to healthy state."""
    health = await get_device_health(session, device_id)
    if not health:
        return False
    
    health.state = DeviceState.HEALTHY
    health.consecutive_failures = 0
    health.quarantine_until = None
    health.updated_at = datetime.now()
    
    await session.commit()
    await session.refresh(health)
    return True


async def is_device_quarantined(session: AsyncSession, device_id: str) -> bool:
    """Check if a device is currently quarantined."""
    health = await get_device_health(session, device_id)
    if not health or not health.quarantine_until:
        return False
    return datetime.now() < health.quarantine_until


async def get_all_quarantined_devices(session: AsyncSession) -> List[str]:
    """Get list of device IDs that are currently quarantined."""
    from app.database.models import DeviceHealth
    result = await session.execute(
        select(DeviceHealth).where(
            DeviceHealth.quarantine_until != None,
            DeviceHealth.quarantine_until > datetime.now()
        )
    )
    return [h.device_id for h in result.scalars().all()]
