"""Unit tests for Model Validators."""

import pytest
from pydantic import ValidationError

from app.database.models import (
    validate_framer_value,
    validate_register_type_value,
    VALID_FRAMERS,
    VALID_REGISTER_TYPES,
    ModbusDeviceCreate,
    ModbusDeviceUpdate,
    PollingTargetCreate,
    PollingTargetUpdate,
)


# ============================================================
# Standalone Validator Function Tests
# ============================================================

class TestFramerValidator:
    """Tests for validate_framer_value function."""

    def test_valid_framers(self):
        """All valid framers should pass."""
        for framer in VALID_FRAMERS:
            result = validate_framer_value(framer)
            assert result == framer
    
    def test_case_insensitive(self):
        """Framers should be case-insensitive."""
        assert validate_framer_value("rtu") == "RTU"
        assert validate_framer_value("Rtu") == "RTU"
        assert validate_framer_value("socket") == "SOCKET"
    
    def test_invalid_framer(self):
        """Invalid framer should raise ValueError."""
        with pytest.raises(ValueError, match="framer must be one of"):
            validate_framer_value("INVALID")
    
    def test_none_not_allowed(self):
        """None should raise ValueError when allow_none=False."""
        with pytest.raises(ValueError, match="framer cannot be None"):
            validate_framer_value(None, allow_none=False)
    
    def test_none_allowed(self):
        """None should pass through when allow_none=True."""
        result = validate_framer_value(None, allow_none=True)
        assert result is None


class TestRegisterTypeValidator:
    """Tests for validate_register_type_value function."""

    def test_valid_register_types(self):
        """All valid register types should pass."""
        for reg_type in VALID_REGISTER_TYPES:
            result = validate_register_type_value(reg_type)
            assert result == reg_type
    
    def test_case_insensitive(self):
        """Register types should be case-insensitive."""
        assert validate_register_type_value("HOLDING") == "holding"
        assert validate_register_type_value("Holding") == "holding"
        assert validate_register_type_value("COIL") == "coil"
    
    def test_invalid_register_type(self):
        """Invalid register type should raise ValueError."""
        with pytest.raises(ValueError, match="register_type must be one of"):
            validate_register_type_value("INVALID")
    
    def test_none_not_allowed(self):
        """None should raise ValueError when allow_none=False."""
        with pytest.raises(ValueError, match="register_type cannot be None"):
            validate_register_type_value(None, allow_none=False)
    
    def test_none_allowed(self):
        """None should pass through when allow_none=True."""
        result = validate_register_type_value(None, allow_none=True)
        assert result is None


# ============================================================
# Schema Validation Tests
# ============================================================

class TestModbusDeviceCreate:
    """Tests for ModbusDeviceCreate schema validation."""

    def test_valid_device(self):
        """Valid device data should pass."""
        device = ModbusDeviceCreate(
            device_id="plc-1",
            host="192.168.1.10",
            port=502,
            slave_id=1,
        )
        assert device.device_id == "plc-1"
        assert device.framer == "RTU"  # Default

    def test_framer_normalized(self):
        """Framer should be normalized to uppercase."""
        device = ModbusDeviceCreate(
            device_id="plc-1",
            host="192.168.1.10",
            port=502,
            slave_id=1,
            framer="socket",
        )
        assert device.framer == "SOCKET"

    def test_invalid_port(self):
        """Invalid port should raise validation error."""
        with pytest.raises(ValidationError):
            ModbusDeviceCreate(
                device_id="plc-1",
                host="192.168.1.10",
                port=99999,  # Invalid
                slave_id=1,
            )

    def test_invalid_slave_id(self):
        """Invalid slave_id should raise validation error."""
        with pytest.raises(ValidationError):
            ModbusDeviceCreate(
                device_id="plc-1",
                host="192.168.1.10",
                port=502,
                slave_id=300,  # Invalid (max 247)
            )


class TestModbusDeviceUpdate:
    """Tests for ModbusDeviceUpdate schema validation."""

    def test_partial_update(self):
        """Only provided fields should be set."""
        update = ModbusDeviceUpdate(host="new-host")
        assert update.host == "new-host"
        assert update.port is None
        assert update.framer is None

    def test_framer_normalized(self):
        """Framer should be normalized when provided."""
        update = ModbusDeviceUpdate(framer="ascii")
        assert update.framer == "ASCII"

    def test_none_framer_allowed(self):
        """None framer should be allowed for updates."""
        update = ModbusDeviceUpdate(host="new-host")
        assert update.framer is None


class TestPollingTargetCreate:
    """Tests for PollingTargetCreate schema validation."""

    def test_valid_target(self):
        """Valid target data should pass."""
        target = PollingTargetCreate(
            device_id="plc-1",
            register_type="holding",
            address=100,
        )
        assert target.register_type == "holding"
        assert target.count == 1  # Default

    def test_register_type_normalized(self):
        """Register type should be normalized to lowercase."""
        target = PollingTargetCreate(
            device_id="plc-1",
            register_type="HOLDING",
            address=100,
        )
        assert target.register_type == "holding"

    def test_invalid_register_type(self):
        """Invalid register type should raise error."""
        with pytest.raises(ValidationError):
            PollingTargetCreate(
                device_id="plc-1",
                register_type="invalid",
                address=100,
            )

    def test_invalid_count(self):
        """Count > 125 should raise error."""
        with pytest.raises(ValidationError):
            PollingTargetCreate(
                device_id="plc-1",
                register_type="holding",
                address=100,
                count=200,  # Invalid (max 125)
            )


class TestPollingTargetUpdate:
    """Tests for PollingTargetUpdate schema validation."""

    def test_partial_update(self):
        """Only provided fields should be set."""
        update = PollingTargetUpdate(count=50)
        assert update.count == 50
        assert update.register_type is None

    def test_register_type_normalized(self):
        """Register type should be normalized when provided."""
        update = PollingTargetUpdate(register_type="INPUT")
        assert update.register_type == "input"
