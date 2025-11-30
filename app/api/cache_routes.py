"""Admin API routes for cache inspection."""

from __future__ import annotations

from typing import List, Dict, Any

from fastapi import APIRouter, Depends

from app.dependencies import get_cache
from app.core.cache import RegisterCache

router = APIRouter(prefix="/admin/cache", tags=["admin", "cache"])


@router.get("", response_model=List[Dict[str, Any]])
async def inspect_cache(
    cache: RegisterCache = Depends(get_cache),
) -> List[Dict[str, Any]]:
    """Inspect all cached register values.
    
    Returns a list of all cached entries with their metadata.
    Useful for debugging and monitoring polling status.
    """
    cache_entries = []
    
    # Access internal cache storage
    async with cache._lock:
        for key, entry in cache._store.items():
            cache_entries.append({
                "key": key,
                "device_id": entry.device_id,
                "register_type": entry.register_type.value,
                "address": entry.address,
                "count": entry.count,
                "values": entry.data,
                "cached_at": entry.timestamp.isoformat(),
                "age_seconds": (
                    # Calculate age
                    # Using datetime.now(timezone.utc) - entry.timestamp
                    (entry.timestamp.now(entry.timestamp.tzinfo) - entry.timestamp).total_seconds()
                ),
            })
    
    return cache_entries


@router.get("/stats")
async def cache_stats(
    cache: RegisterCache = Depends(get_cache),
) -> Dict[str, Any]:
    """Get cache statistics.
    
    Returns:
        - total_entries: Number of cached entries
        - devices: List of devices with cached data
        - oldest_entry: Timestamp of oldest cached data
        - newest_entry: Timestamp of newest cached data
    """
    from datetime import datetime, timezone
    
    async with cache._lock:
        entries = list(cache._store.values())
    
    if not entries:
        return {
            "total_entries": 0,
            "devices": [],
            "oldest_entry": None,
            "newest_entry": None,
        }
    
    devices = list(set(entry.device_id for entry in entries))
    timestamps = [entry.timestamp for entry in entries]
    
    return {
        "total_entries": len(entries),
        "devices": devices,
        "oldest_entry": min(timestamps).isoformat(),
        "newest_entry": max(timestamps).isoformat(),
        "cache_keys": list(cache._store.keys()),
    }


@router.delete("")
async def clear_cache(
    cache: RegisterCache = Depends(get_cache),
) -> Dict[str, str]:
    """Clear all cached data.
    
    Useful for testing or forcing fresh polling.
    """
    async with cache._lock:
        count = len(cache._store)
        cache._store.clear()
    
    return {
        "status": "ok",
        "message": f"Cleared {count} cache entries",
    }


@router.get("/device/{device_id}")
async def inspect_device_cache(
    device_id: str,
    cache: RegisterCache = Depends(get_cache),
) -> List[Dict[str, Any]]:
    """Inspect cached data for a specific device."""
    device_entries = []
    
    async with cache._lock:
        for key, entry in cache._store.items():
            if entry.device_id == device_id:
                device_entries.append({
                    "key": key,
                    "register_type": entry.register_type.value,
                    "address": entry.address,
                    "count": entry.count,
                    "values": entry.data,
                    "cached_at": entry.timestamp.isoformat(),
                })
    
    return device_entries
