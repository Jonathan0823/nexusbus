import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.core.modbus_client import RegisterType

def test_get_devices_empty(client: TestClient):
    """Test getting devices when none are configured (mocked empty)."""
    # Since the endpoint reads directly from the imported DEVICE_CONFIGS,
    # we must patch it where it is used (app.api.routes).
    with patch("app.api.routes.DEVICE_CONFIGS", []):
        response = client.get("/api/devices")
        assert response.status_code == 200
        assert response.json() == []

@patch("app.core.modbus_client.ModbusClientManager.read_registers")
def test_read_registers_success(mock_read, client: TestClient):
    """
    Test reading registers from a device.
    We mock the ModbusClientManager.read_registers to return a fixed value.
    """
    # Setup Mock
    mock_read.return_value = [123, 456]
    
    # We need to ensure the device exists in the manager for the check logic
    from main import app
    # Inject a fake client into the manager's list so it passes the "is device valid" check
    app.state.modbus_manager.clients = {"test-device": MagicMock()}
    
    # Execute Request
    response = client.get("/api/devices/test-device/registers?address=10&count=2")
    
    # Verify Response
    assert response.status_code == 200
    data = response.json()
    
    # The key is 'values', not 'data'
    assert data["values"] == [123, 456]
    assert data["device_id"] == "test-device"
    assert data["source"] == "live" # default is live if not cached

def test_read_registers_device_not_found(client: TestClient):
    """Test reading from a non-existent device."""
    response = client.get("/api/devices/non-existent/registers?address=10&count=1")
    
    # Should return 404 Not Found
    assert response.status_code == 404
    # Error message from ModbusClientManager is "Unknown device_id ..."
    assert "unknown device_id" in response.json()["detail"].lower()

def test_gateway_status(client: TestClient):
    """Test the gateway status endpoint."""
    response = client.get("/api/devices/gateways")
    assert response.status_code == 200
    # Should return a list of gateway status dicts
    assert isinstance(response.json(), list)
