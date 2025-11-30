import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app

# We need to mock the startup event to prevent real DB/MQTT connections during tests
# unless we are running a full integration test suite.
@pytest.fixture(autouse=True)
def mock_startup_shutdown():
    """Mock startup and shutdown events."""
    with patch("main.create_db_and_tables", new_callable=MagicMock) as mock_db, \
         patch("main.mqtt_manager.start", new_callable=MagicMock) as mock_mqtt, \
         patch("main.load_device_configs", return_value=[]) as mock_load:
        yield

def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_read_root_docs(client: TestClient):
    """Test that the documentation endpoint is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200

# --- Unit Tests for Utilities (No DB/Network needed) ---

from app.core.cache import RegisterCache
from app.core.modbus_client import RegisterType


@pytest.mark.asyncio
async def test_cache_operations():
    """Test basic cache set/get operations."""
    cache = RegisterCache()
    
    # Test Set & Get
    await cache.set("device1", RegisterType.HOLDING, 100, 3, [1, 2, 3])
    
    # Get Returns CachedEntry object, not just value
    entry = await cache.get("device1", RegisterType.HOLDING, 100, 3)
    assert entry is not None
    assert entry.data == [1, 2, 3]
    assert entry.device_id == "device1"
    
    # Test Miss (Different address or count)
    entry_none = await cache.get("device1", RegisterType.HOLDING, 999, 1)
    assert entry_none is None
    
    # Test Clear
    await cache.clear()
    entry_cleared = await cache.get("device1", RegisterType.HOLDING, 100, 3)
    assert entry_cleared is None
