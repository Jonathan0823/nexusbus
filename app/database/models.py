"""SQLModel models for database tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from pydantic import field_validator
from sqlmodel import Field, SQLModel


# =============================================================================
# Reusable Validators (DRY principle)
# =============================================================================

VALID_FRAMERS: Tuple[str, ...] = ("RTU", "SOCKET", "ASCII")
VALID_REGISTER_TYPES: Tuple[str, ...] = ("holding", "input", "coil", "discrete")


def validate_framer_value(v: str | None, allow_none: bool = False) -> str | None:
    """Validate framer value and normalize to uppercase.
    
    Args:
        v: Framer value to validate
        allow_none: If True, None values are passed through
        
    Returns:
        Normalized uppercase framer value
        
    Raises:
        ValueError: If framer value is invalid
    """
    if v is None:
        if allow_none:
            return None
        raise ValueError("framer cannot be None")
    v_upper = v.upper()
    if v_upper not in VALID_FRAMERS:
        raise ValueError(f"framer must be one of {VALID_FRAMERS}, got '{v}'")
    return v_upper


def validate_register_type_value(v: str | None, allow_none: bool = False) -> str | None:
    """Validate register type value and normalize to lowercase.
    
    Args:
        v: Register type value to validate
        allow_none: If True, None values are passed through
        
    Returns:
        Normalized lowercase register type value
        
    Raises:
        ValueError: If register type value is invalid
    """
    if v is None:
        if allow_none:
            return None
        raise ValueError("register_type cannot be None")
    v_lower = v.lower()
    if v_lower not in VALID_REGISTER_TYPES:
        raise ValueError(f"register_type must be one of {VALID_REGISTER_TYPES}, got '{v}'")
    return v_lower


# =============================================================================
# Database Models
# =============================================================================

class ModbusDevice(SQLModel, table=True):
    """Modbus device configuration stored in database."""
    
    __tablename__ = "modbus_devices"
    
    device_id: str = Field(primary_key=True, max_length=50)
    host: str = Field(max_length=100)
    port: int
    slave_id: int
    timeout: int = Field(default=10)
    framer: str = Field(default="RTU", max_length=20)
    max_retries: int = Field(default=5)
    retry_delay: float = Field(default=0.1)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Pydantic schemas for API
class ModbusDeviceCreate(SQLModel):
    """Schema for creating a new device."""
    
    device_id: str = Field(..., max_length=50)
    host: str = Field(..., max_length=100)
    port: int = Field(..., ge=1, le=65535)
    slave_id: int = Field(..., ge=1, le=247)  # Modbus slave ID range: 1-247
    timeout: int = Field(default=10, ge=1, le=300)
    framer: str = Field(default="RTU", max_length=20)
    max_retries: int = Field(default=5, ge=0, le=10)
    retry_delay: float = Field(default=0.1, ge=0.0, le=10.0)
    
    @field_validator('framer')
    @classmethod
    def validate_framer(cls, v: str) -> str:
        """Validate framer value."""
        return validate_framer_value(v, allow_none=False)


class ModbusDeviceUpdate(SQLModel):
    """Schema for updating device configuration."""
    
    host: Optional[str] = Field(None, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    slave_id: Optional[int] = Field(None, ge=1, le=247)
    timeout: Optional[int] = Field(None, ge=1, le=300)
    framer: Optional[str] = Field(None, max_length=20)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay: Optional[float] = Field(None, ge=0.0, le=10.0)
    
    @field_validator('framer')
    @classmethod
    def validate_framer(cls, v: str | None) -> str | None:
        """Validate framer value."""
        return validate_framer_value(v, allow_none=True)


class ModbusDeviceResponse(SQLModel):
    """Schema for device API responses."""
    
    device_id: str
    host: str
    port: int
    slave_id: int
    timeout: int
    framer: str
    max_retries: int
    retry_delay: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PollingTarget(SQLModel, table=True):
    """Polling target configuration - defines which registers to poll automatically."""
    
    __tablename__ = "polling_targets"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(max_length=50, index=True, foreign_key="modbus_devices.device_id")
    register_type: str = Field(max_length=20)  # holding, input, coil, discrete
    address: int
    count: int = Field(default=1, ge=1, le=125)
    is_active: bool = Field(default=True, index=True)
    description: Optional[str] = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Pydantic schemas for Polling API
class PollingTargetCreate(SQLModel):
    """Schema for creating a new polling target."""
    
    device_id: str = Field(..., max_length=50)
    register_type: str = Field(..., max_length=20)
    address: int = Field(..., ge=0, le=65535)  # Modbus address range
    count: int = Field(default=1, ge=1, le=125)  # Modbus max read count
    description: Optional[str] = Field(None, max_length=200)
    
    @field_validator('register_type')
    @classmethod
    def validate_register_type(cls, v: str) -> str:
        """Validate register type."""
        return validate_register_type_value(v, allow_none=False)


class PollingTargetUpdate(SQLModel):
    """Schema for updating polling target configuration."""
    
    device_id: Optional[str] = Field(None, max_length=50)
    register_type: Optional[str] = Field(None, max_length=20)
    address: Optional[int] = Field(None, ge=0, le=65535)
    count: Optional[int] = Field(None, ge=1, le=125)
    description: Optional[str] = Field(None, max_length=200)
    
    @field_validator('register_type')
    @classmethod
    def validate_register_type(cls, v: str | None) -> str | None:
        """Validate register type."""
        return validate_register_type_value(v, allow_none=True)


class PollingTargetResponse(SQLModel):
    """Schema for polling target API responses."""
    
    id: int
    device_id: str
    register_type: str
    address: int
    count: int
    is_active: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
