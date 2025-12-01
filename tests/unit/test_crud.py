import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import crud
from app.database.models import ModbusDevice, ModbusDeviceUpdate

@pytest.mark.asyncio
async def test_create_device():
    """Test creating a new device."""
    # Mock Session
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Input data
    new_device = ModbusDevice(
        device_id="test-plc",
        host="192.168.1.10",
        port=502,
        slave_id=1
    )

    # Execute
    result = await crud.create_device(mock_session, new_device)

    # Verify
    assert result.device_id == "test-plc"
    mock_session.add.assert_called_once_with(new_device)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(new_device)

@pytest.mark.asyncio
async def test_get_device_found():
    """Test getting an existing device."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Mock result
    mock_device = ModbusDevice(device_id="test-plc", host="localhost", port=502, slave_id=1)
    
    # Mock execute().scalar_one_or_none()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_device
    mock_session.execute.return_value = mock_result

    # Execute
    result = await crud.get_device(mock_session, "test-plc")

    # Verify
    assert result is not None
    assert result.device_id == "test-plc"
    mock_session.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_device_not_found():
    """Test getting a non-existent device."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await crud.get_device(mock_session, "unknown")
    assert result is None

@pytest.mark.asyncio
async def test_update_device():
    """Test updating a device."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Existing device
    existing_device = ModbusDevice(
        device_id="test-plc", 
        host="old-host", 
        port=502, 
        slave_id=1
    )
    
    # Mock get_device to return existing_device
    # We need to patch crud.get_device because it's called internally
    with patch("app.database.crud.get_device", new=AsyncMock(return_value=existing_device)):
        
        update_data = ModbusDeviceUpdate(host="new-host")
        
        # Execute
        result = await crud.update_device(mock_session, "test-plc", update_data)

        # Verify
        assert result.host == "new-host"
        assert result.port == 502 # Unchanged
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(existing_device)

@pytest.mark.asyncio
async def test_delete_device():
    """Test soft deleting a device."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    existing_device = ModbusDevice(device_id="test-plc", is_active=True, host="x", port=1, slave_id=1)
    
    with patch("app.database.crud.get_device", new=AsyncMock(return_value=existing_device)):
        
        # Execute
        success = await crud.delete_device(mock_session, "test-plc")

        # Verify
        assert success is True
        assert existing_device.is_active is False
        mock_session.commit.assert_awaited_once()
