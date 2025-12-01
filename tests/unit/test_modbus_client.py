import pytest
from unittest.mock import MagicMock, patch
from app.core.modbus_client import (
    ModbusClientManager,
    DeviceConfig,
    RegisterType,
    ModbusClientError,
    ModbusGateway,
)
from pymodbus.exceptions import ModbusIOException


# Fixtures
@pytest.fixture
def mock_device_configs():
    return [
        DeviceConfig(
            device_id="test-device",
            host="localhost",
            port=502,
            slave_id=1,
            timeout=1,
            max_retries=3,
            retry_delay=0.01,
        )
    ]


@pytest.fixture
def modbus_manager(mock_device_configs):
    return ModbusClientManager(mock_device_configs)


# Helper to patch ModbusGateway with a mock client
def patch_gateway_client(mock_client_cls):
    class TestGateway(ModbusGateway):
        def __init__(self, *args, **kwargs):
            kwargs["client_cls"] = mock_client_cls
            super().__init__(*args, **kwargs)

    return patch("app.core.modbus_client.ModbusGateway", TestGateway)


# Tests
@pytest.mark.asyncio
async def test_read_registers_success(modbus_manager):
    """Test successful register reading."""

    MockClient = MagicMock()
    mock_instance = MockClient.return_value

    # Setup successful response
    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.registers = [10, 20, 30]
    mock_instance.read_holding_registers.return_value = mock_response
    mock_instance.connect.return_value = True
    mock_instance.is_socket_open.return_value = True

    # Patch ModbusGateway to use our MockClient
    with patch_gateway_client(MockClient):
        # Execute
        result = await modbus_manager.read_registers(
            device_id="test-device",
            register_type=RegisterType.HOLDING,
            address=0,
            count=3,
        )

        # Verify
        assert result == [10, 20, 30]
        mock_instance.read_holding_registers.assert_called_with(
            address=0, count=3, slave=1
        )


@pytest.mark.asyncio
async def test_read_registers_retry_success(modbus_manager):
    """Test retry logic: fail twice, then succeed."""

    MockClient = MagicMock()
    mock_instance = MockClient.return_value
    mock_instance.connect.return_value = True
    mock_instance.is_socket_open.return_value = True

    # Setup side_effect: Exception, Exception, Success
    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.registers = [99]

    mock_instance.read_holding_registers.side_effect = [
        ModbusIOException("Connection lost"),
        ModbusIOException("Timeout"),
        mock_response,
    ]

    with patch_gateway_client(MockClient):
        # Execute
        result = await modbus_manager.read_registers(
            device_id="test-device",
            register_type=RegisterType.HOLDING,
            address=10,
            count=1,
        )

        # Verify
        assert result == [99]
        # Should have been called 3 times
        assert mock_instance.read_holding_registers.call_count == 3


@pytest.mark.asyncio
async def test_read_registers_fail_max_retries(modbus_manager):
    """Test failure after max retries."""

    MockClient = MagicMock()
    mock_instance = MockClient.return_value
    mock_instance.connect.return_value = True
    mock_instance.is_socket_open.return_value = True

    # Always fail
    mock_instance.read_holding_registers.side_effect = ModbusIOException("Dead")

    with patch_gateway_client(MockClient):
        # Execute & Expect Error
        with pytest.raises(ModbusClientError) as excinfo:
            await modbus_manager.read_registers(
                device_id="test-device",
                register_type=RegisterType.HOLDING,
                address=10,
                count=1,
            )

        # The error could be "No response" or "Failed to connect" depending on flow
        err_msg = str(excinfo.value)
        assert (
            "No response" in err_msg
            or "Dead" in err_msg
            or "Failed to connect" in err_msg
        )


@pytest.mark.asyncio
async def test_write_register_success(modbus_manager):
    """Test successful register writing."""

    MockClient = MagicMock()
    mock_instance = MockClient.return_value
    mock_instance.connect.return_value = True
    mock_instance.is_socket_open.return_value = True

    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_instance.write_register.return_value = mock_response

    with patch_gateway_client(MockClient):
        # Execute
        await modbus_manager.write_register(
            device_id="test-device",
            register_type=RegisterType.HOLDING,
            address=5,
            value=123,
        )

        # Verify
        mock_instance.write_register.assert_called_with(address=5, value=123, slave=1)


@pytest.mark.asyncio
async def test_device_not_found(modbus_manager):
    """Test error when device ID is unknown."""

    with pytest.raises(ModbusClientError) as excinfo:
        await modbus_manager.read_registers(
            device_id="unknown-device",
            register_type=RegisterType.HOLDING,
            address=0,
            count=1,
        )

    assert "Unknown device_id" in str(excinfo.value)
