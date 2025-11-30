import pytest
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app

# Configure pytest-asyncio to treat all async tests as asyncio-driven
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient instance.
    """
    with TestClient(app) as c:
        yield c

# We need to mock the startup event to prevent real DB/MQTT connections during tests
# unless we are running a full integration test suite.
@pytest.fixture(autouse=True)
def mock_startup_shutdown():
    """Mock startup and shutdown events globally for all tests."""
    with patch("main.create_db_and_tables", new_callable=MagicMock) as mock_db, \
         patch("main.mqtt_manager.start", new_callable=MagicMock) as mock_mqtt, \
         patch("main.load_device_configs", return_value=[]) as mock_load:
        yield