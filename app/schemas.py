"""Shared Pydantic models and enums for API layer."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.core.modbus_client import RegisterType


class CacheSource(str, Enum):
    LIVE = "live"
    CACHE = "cache"


class WriteRegisterRequest(BaseModel):
    register_type: RegisterType = Field(
        default=RegisterType.HOLDING,
        description="Only holding registers are writable.",
    )
    address: int = Field(..., ge=0, description="Start address of the register")
    value: int = Field(..., description="Value to write to the register")
