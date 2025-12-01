"""Simple in-memory cache for register snapshots with TTL support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from app.core.config import settings
from app.core.modbus_client import RegisterType


@dataclass
class CachedEntry:
    device_id: str
    register_type: RegisterType
    address: int
    count: int
    data: list[int]
    timestamp: datetime
    ttl_seconds: int = 300  # Default TTL: 5 minutes
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age > self.ttl_seconds


class RegisterCache:
    """Stores the latest register values fetched per device/register interval.
    
    Features:
    - TTL (Time To Live) support for automatic expiration
    - Automatic cleanup of expired entries on get()
    - Thread-safe operations with asyncio.Lock
    """

    def __init__(self, default_ttl_seconds: int | None = None) -> None:
        self._store: Dict[str, CachedEntry] = {}
        self._lock = asyncio.Lock()
        self._default_ttl = default_ttl_seconds or settings.CACHE_TTL_SECONDS

    @staticmethod
    def _key(device_id: str, register_type: RegisterType, address: int, count: int) -> str:
        return f"{device_id}:{register_type.value}:{address}:{count}"

    async def set(
        self,
        device_id: str,
        register_type: RegisterType,
        address: int,
        count: int,
        data: list[int],
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a cache entry with optional TTL override.
        
        Args:
            device_id: Device identifier
            register_type: Type of register
            address: Register address
            count: Number of registers
            data: Register values
            ttl_seconds: Optional TTL override (uses default if None)
        """
        entry = CachedEntry(
            device_id=device_id,
            register_type=register_type,
            address=address,
            count=count,
            data=data,
            timestamp=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds or self._default_ttl,
        )
        async with self._lock:
            self._store[self._key(device_id, register_type, address, count)] = entry

    async def get(
        self,
        device_id: str,
        register_type: RegisterType,
        address: int,
        count: int,
    ) -> Optional[CachedEntry]:
        """Get a cache entry, automatically removing it if expired.
        
        Returns:
            CachedEntry if found and not expired, None otherwise
        """
        key = self._key(device_id, register_type, address, count)
        async with self._lock:
            entry = self._store.get(key)
            if entry and entry.is_expired():
                # Auto-cleanup expired entry
                del self._store[key]
                return None
            return entry

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._store.clear()
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._store.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._store[key]
            return len(expired_keys)
    
    async def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        async with self._lock:
            total = len(self._store)
            expired = sum(1 for entry in self._store.values() if entry.is_expired())
            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": total - expired,
            }
