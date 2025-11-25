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
