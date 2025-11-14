"""Simple in-memory cache for register snapshots."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.modbus_client import RegisterType


@dataclass
class CachedEntry:
    device_id: str
    register_type: RegisterType
    address: int
    count: int
    data: list[int]
    timestamp: datetime


class RegisterCache:
    """Stores the latest register values fetched per device/register interval."""

    def __init__(self) -> None:
        self._store: Dict[str, CachedEntry] = {}
        self._lock = asyncio.Lock()

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
    ) -> None:
        entry = CachedEntry(
            device_id=device_id,
            register_type=register_type,
            address=address,
            count=count,
            data=data,
            timestamp=datetime.now(timezone.utc),
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
        async with self._lock:
            return self._store.get(self._key(device_id, register_type, address, count))

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
