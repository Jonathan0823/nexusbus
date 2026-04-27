import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.modbus_client import (
    ModbusClientManager,
    AsyncModbusGateway,
    DeviceConfig,
    RegisterType,
    ModbusClientError,
)
from pymodbus.exceptions import ModbusIOException
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.framer import FramerType


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
def mock_db_session_factory():
    """Mock database session factory for testing."""
    async def mock_session():
        yield MagicMock()
    return mock_session


@pytest.fixture
def modbus_manager(mock_device_configs, mock_db_session_factory):
    return ModbusClientManager(mock_device_configs, mock_db_session_factory)


def create_mock_gateway(mock_client, host="localhost", port=502):
    """Create a fully configured AsyncModbusGateway with mocked client."""
    gateway = AsyncModbusGateway(
        host=host,
        port=port,
        timeout=1,
        framer=FramerType.SOCKET,
        max_retries=3,
        retry_delay=0.01,
    )
    # Replace the client with mock
    gateway._client = mock_client
    return gateway


# Tests
@pytest.mark.asyncio
async def test_read_registers_success(modbus_manager):
    """Test successful register reading with async client."""

    # Create mock async client
    mock_client = AsyncMock(spec=AsyncModbusTcpClient)
    
    # Setup successful response
    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.registers = [10, 20, 30]
    mock_response.slave_id = 1  # Must match requested slave_id
    mock_client.read_holding_registers = AsyncMock(return_value=mock_response)
    mock_client.connect = AsyncMock(return_value=True)
    mock_client.connected = True  # Property, not method

    # Create mock gateway
    gateway = create_mock_gateway(mock_client)
    
    # Patch the manager's gateway creation
    with patch.object(modbus_manager, '_create_gateway', return_value=gateway):
        # Execute
        result = await modbus_manager.read_registers(
            device_id="test-device",
            register_type=RegisterType.HOLDING,
            address=0,
            count=3,
        )

        # Verify
        assert result == [10, 20, 30]


@pytest.mark.asyncio
async def test_read_registers_retry_success(modbus_manager):
    """Test retry logic with async client: fail twice, then succeed."""

    # Create mock async client
    mock_client = AsyncMock(spec=AsyncModbusTcpClient)
    mock_client.connect = AsyncMock(return_value=True)
    mock_client.connected = True

    # Setup side_effect: Exception, Exception, Success
    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.registers = [99]
    mock_response.slave_id = 1

    mock_client.read_holding_registers = AsyncMock(side_effect=[
        ModbusIOException("Connection lost"),
        ModbusIOException("Timeout"),
        mock_response,
    ])

    # Create mock gateway
    gateway = create_mock_gateway(mock_client)
    
    with patch.object(modbus_manager, '_create_gateway', return_value=gateway):
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
        assert mock_client.read_holding_registers.call_count == 3


@pytest.mark.asyncio
async def test_read_registers_fail_max_retries(modbus_manager):
    """Test failure after max retries with async client."""

    # Create mock async client that always fails
    mock_client = AsyncMock(spec=AsyncModbusTcpClient)
    mock_client.connect = AsyncMock(return_value=True)
    mock_client.connected = True
    mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("Dead"))

    # Create mock gateway with max_retries=1 for faster test
    gateway = create_mock_gateway(mock_client)
    gateway.max_retries = 1  # Override for test
    
    with patch.object(modbus_manager, '_create_gateway', return_value=gateway):
        # Execute & Expect Error
        with pytest.raises(ModbusClientError) as excinfo:
            await modbus_manager.read_registers(
                device_id="test-device",
                register_type=RegisterType.HOLDING,
                address=10,
                count=1,
            )

        # The error could be "No response" or exception from mock
        err_msg = str(excinfo.value)
        assert (
            "No response" in err_msg
            or "Dead" in err_msg
            or "Failed to connect" in err_msg
        )


@pytest.mark.asyncio
async def test_write_register_success(modbus_manager):
    """Test successful register writing with async client."""

    # Create mock async client
    mock_client = AsyncMock(spec=AsyncModbusTcpClient)
    mock_client.connect = AsyncMock(return_value=True)
    mock_client.connected = True

    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.slave_id = 1
    mock_client.write_register = AsyncMock(return_value=mock_response)

    # Create mock gateway
    gateway = create_mock_gateway(mock_client)
    
    with patch.object(modbus_manager, '_create_gateway', return_value=gateway):
        # Execute
        await modbus_manager.write_register(
            device_id="test-device",
            register_type=RegisterType.HOLDING,
            address=5,
            value=123,
        )

        # Verify write was called
        mock_client.write_register.assert_called_once()


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