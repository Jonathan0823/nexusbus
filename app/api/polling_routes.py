"""Admin API routes for managing polling targets."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.connection import get_session
from app.database.models import (
    PollingTarget,
    PollingTargetCreate,
    PollingTargetResponse,
    PollingTargetUpdate,
)

router = APIRouter(prefix="/admin/polling", tags=["admin", "polling"])


@router.get("", response_model=List[PollingTargetResponse])
async def list_all_polling_targets(
    session: AsyncSession = Depends(get_session),
) -> List[PollingTarget]:
    """List all polling targets (including inactive)."""
    return await crud.get_all_polling_targets(session)


@router.get("/active", response_model=List[PollingTargetResponse])
async def list_active_polling_targets(
    session: AsyncSession = Depends(get_session),
) -> List[PollingTarget]:
    """List only active polling targets."""
    return await crud.get_all_active_polling_targets(session)


@router.get("/device/{device_id}", response_model=List[PollingTargetResponse])
async def list_polling_targets_by_device(
    device_id: str,
    session: AsyncSession = Depends(get_session),
) -> List[PollingTarget]:
    """List all active polling targets for a specific device."""
    return await crud.get_polling_targets_by_device(session, device_id)


@router.get("/{target_id}", response_model=PollingTargetResponse)
async def get_polling_target_detail(
    target_id: int,
    session: AsyncSession = Depends(get_session),
) -> PollingTarget:
    """Get details of a specific polling target."""
    target = await crud.get_polling_target(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polling target with ID {target_id} not found"
        )
    return target


@router.post("", response_model=PollingTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_new_polling_target(
    target_create: PollingTargetCreate,
    session: AsyncSession = Depends(get_session),
) -> PollingTarget:
    """Create a new polling target configuration."""
    # Validate register_type
    valid_types = ["holding", "input", "coil", "discrete"]
    if target_create.register_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid register_type. Must be one of: {valid_types}"
        )
    
    # Check if device exists
    device = await crud.get_device(session, target_create.device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{target_create.device_id}' not found"
        )
    
    # Create new polling target
    db_target = PollingTarget(**target_create.model_dump())
    return await crud.create_polling_target(session, db_target)


@router.put("/{target_id}", response_model=PollingTargetResponse)
async def update_polling_target_config(
    target_id: int,
    target_update: PollingTargetUpdate,
    session: AsyncSession = Depends(get_session),
) -> PollingTarget:
    """Update polling target configuration."""
    # Validate register_type if provided
    if target_update.register_type:
        valid_types = ["holding", "input", "coil", "discrete"]
        if target_update.register_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid register_type. Must be one of: {valid_types}"
            )
    
    updated = await crud.update_polling_target(session, target_id, target_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polling target with ID {target_id} not found"
        )
    return updated


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polling_target(
    target_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a polling target (set is_active to False)."""
    success = await crud.delete_polling_target(session, target_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polling target with ID {target_id} not found"
        )


@router.post("/{target_id}/activate", response_model=PollingTargetResponse)
async def activate_polling_target(
    target_id: int,
    session: AsyncSession = Depends(get_session),
) -> PollingTarget:
    """Reactivate a polling target."""
    success = await crud.activate_polling_target(session, target_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Polling target with ID {target_id} not found"
        )
    target = await crud.get_polling_target(session, target_id)
    return target


@router.post("/reload", status_code=status.HTTP_200_OK)
async def reload_polling_targets() -> dict:
    """Trigger reload of polling targets from database.
    
    Note: This endpoint signals the polling service to reload its configuration.
    The actual reload happens asynchronously in the background polling task.
    """
    # This will be handled by the polling service watching for config changes
    # For now, we just return success - the polling loop will pick up changes
    # on its next iteration
    return {
        "status": "ok",
        "message": "Polling targets will be reloaded on next polling cycle"
    }
