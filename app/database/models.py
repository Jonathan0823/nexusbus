"""SQLModel models for database tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


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
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Pydantic schemas for API
class ModbusDeviceCreate(SQLModel):
    """Schema for creating a new device."""
    
    device_id: str
    host: str
    port: int
    slave_id: int
    timeout: int = 10
    framer: str = "RTU"
    max_retries: int = 5
    retry_delay: float = 0.1


class ModbusDeviceUpdate(SQLModel):
    """Schema for updating device configuration."""
    
    host: Optional[str] = None
    port: Optional[int] = None
    slave_id: Optional[int] = None
    timeout: Optional[int] = None
    framer: Optional[str] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[float] = None


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
    device_id: str = Field(max_length=50, index=True)
    register_type: str = Field(max_length=20)  # holding, input, coil, discrete
    address: int
    count: int = Field(default=1, ge=1, le=125)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Pydantic schemas for Polling API
class PollingTargetCreate(SQLModel):
    """Schema for creating a new polling target."""
    
    device_id: str
    register_type: str  # holding, input, coil, discrete
    address: int
    count: int = 1
    description: Optional[str] = None


class PollingTargetUpdate(SQLModel):
    """Schema for updating polling target configuration."""
    
    device_id: Optional[str] = None
    register_type: Optional[str] = None
    address: Optional[int] = None
    count: Optional[int] = None
    description: Optional[str] = None


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
