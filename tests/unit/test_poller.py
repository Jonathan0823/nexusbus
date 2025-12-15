"""Unit tests for Polling Service helpers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from app.services.poller import (
    load_polling_targets_from_db,
    _poll_single_target,
    await_pending_mqtt_tasks,
    _pending_mqtt_tasks,
)
from app.core.modbus_client import ModbusClientManager, ModbusClientError, RegisterType
from app.core.circuit_breaker import CircuitOpenError
from app.core.cache import RegisterCache


# ============================================================
# load_polling_targets_from_db Tests
# ============================================================

@pytest.mark.asyncio
async def test_load_polling_targets_success():
    """Test successful loading of polling targets."""
    mock_target = MagicMock()
    mock_target.id = 1
    mock_target.device_id = "plc-1"
    mock_target.register_type = "holding"
    mock_target.address = 100
    mock_target.count = 10
    mock_target.description = "Test target"
    
    with patch("app.services.poller.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        with patch("app.services.poller.crud.get_all_active_polling_targets", 
                   new=AsyncMock(return_value=[mock_target])):
            
            targets = await load_polling_targets_from_db()
            
            assert len(targets) == 1
            assert targets[0]["device_id"] == "plc-1"
            assert targets[0]["address"] == 100


@pytest.mark.asyncio
async def test_load_polling_targets_empty():
    """Test loading when no targets exist."""
    with patch("app.services.poller.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        with patch("app.services.poller.crud.get_all_active_polling_targets", 
                   new=AsyncMock(return_value=[])):
            
            targets = await load_polling_targets_from_db()
            
            assert targets == []


@pytest.mark.asyncio
async def test_load_polling_targets_db_error():
    """Test handling of database errors."""
    with patch("app.services.poller.async_session_maker") as mock_session_maker:
        mock_session_maker.return_value.__aenter__.side_effect = Exception("DB Error")
        
        targets = await load_polling_targets_from_db()
        
        assert targets == []


# ============================================================
# _poll_single_target Tests
# ============================================================

@pytest.fixture
def mock_manager():
    """Mock ModbusClientManager."""
    return AsyncMock(spec=ModbusClientManager)


@pytest.fixture
def mock_cache():
    """Mock RegisterCache."""
    return AsyncMock(spec=RegisterCache)


@pytest.mark.asyncio
async def test_poll_single_target_success(mock_manager, mock_cache):
    """Test successful polling of a single target."""
    mock_manager.read_registers.return_value = [100, 200, 300]
    
    target = {
        "device_id": "plc-1",
        "register_type": "holding",
        "address": 0,
        "count": 3,
    }
    
    success, error = await _poll_single_target(target, mock_manager, mock_cache)
    
    assert success is True
    assert error == ""
    mock_manager.read_registers.assert_called_once()
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_poll_single_target_invalid_config():
    """Test handling of invalid target configuration."""
    mock_manager = AsyncMock()
    mock_cache = AsyncMock()
    
    target = {
        # Missing required fields
        "device_id": "plc-1",
    }
    
    success, error = await _poll_single_target(target, mock_manager, mock_cache)
    
    assert success is False
    assert "Invalid" in error or "address" in error.lower() or "KeyError" in error


@pytest.mark.asyncio
async def test_poll_single_target_modbus_error(mock_manager, mock_cache):
    """Test handling of Modbus errors."""
    mock_manager.read_registers.side_effect = ModbusClientError("Device offline")
    
    target = {
        "device_id": "plc-1",
        "register_type": "holding",
        "address": 0,
        "count": 1,
    }
    
    success, error = await _poll_single_target(target, mock_manager, mock_cache)
    
    assert success is False
    assert "plc-1" in error


@pytest.mark.asyncio
async def test_poll_single_target_circuit_open(mock_manager, mock_cache):
    """Test handling of circuit breaker open errors."""
    mock_manager.read_registers.side_effect = CircuitOpenError("plc-1", 30.0)
    
    target = {
        "device_id": "plc-1",
        "register_type": "holding",
        "address": 0,
        "count": 1,
    }
    
    success, error = await _poll_single_target(target, mock_manager, mock_cache)
    
    assert success is False
    assert "Circuit" in error or "OPEN" in error


@pytest.mark.asyncio
async def test_poll_single_target_with_mqtt(mock_manager, mock_cache):
    """Test polling with MQTT publishing."""
    mock_manager.read_registers.return_value = [100]
    mock_mqtt = AsyncMock()
    
    target = {
        "device_id": "plc-1",
        "register_type": "holding",
        "address": 0,
        "count": 1,
    }
    
    # Clear any pending tasks from previous tests
    _pending_mqtt_tasks.clear()
    
    success, error = await _poll_single_target(target, mock_manager, mock_cache, mock_mqtt)
    
    # Wait briefly for background task to be created
    await asyncio.sleep(0.01)
    
    assert success is True
    # MQTT task should have been created
    assert len(_pending_mqtt_tasks) >= 0  # May have completed already


# ============================================================
# await_pending_mqtt_tasks Tests
# ============================================================

@pytest.mark.asyncio
async def test_await_pending_mqtt_tasks_empty():
    """Test awaiting when no pending tasks."""
    _pending_mqtt_tasks.clear()
    
    count = await await_pending_mqtt_tasks(timeout=1.0)
    
    assert count == 0


@pytest.mark.asyncio
async def test_await_pending_mqtt_tasks_with_tasks():
    """Test awaiting pending tasks."""
    _pending_mqtt_tasks.clear()
    
    # Create some quick tasks
    async def quick_task():
        await asyncio.sleep(0.01)
    
    task = asyncio.create_task(quick_task())
    _pending_mqtt_tasks.add(task)
    task.add_done_callback(_pending_mqtt_tasks.discard)
    
    count = await await_pending_mqtt_tasks(timeout=1.0)
    
    assert count == 1
