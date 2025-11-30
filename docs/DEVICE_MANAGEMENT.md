# Device Management API

> **Comprehensive guide for managing Modbus devices via REST API**

**[← Main README](../README.md)** | **[Setup Guide](../DATABASE_SETUP.md)** | **[Polling Config →](./POLLING_CONFIGURATION.md)** | **[Migrations](../migrations/README.md)**

---

## 📚 Quick Navigation

- [Overview](#overview)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Usage Examples](#usage-examples)
- [Workflows](#workflow)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Device Management API allows you to dynamically configure Modbus devices without modifying code or restarting the application. All device configurations are stored in the PostgreSQL database.

## Features

✅ **CRUD Operations**: Create, Read, Update, Delete devices
✅ **Hot-Reload**: Changes take effect immediately via `/reload` endpoint
✅ **Soft Delete**: Deactivate devices without losing configuration
✅ **Validation**: Automatic validation of device parameters
✅ **Audit Trail**: Track creation and update timestamps
✅ **Database-Driven**: No hardcoded configurations needed

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Admin API                             │
│                                                          │
│  POST   /api/admin/devices         (Create)             │
│  GET    /api/admin/devices         (List All)           │
│  GET    /api/admin/devices/active  (List Active)        │
│  GET    /api/admin/devices/{id}    (Get Detail)         │
│  PUT    /api/admin/devices/{id}    (Update)             │
│  DELETE /api/admin/devices/{id}    (Soft Delete)        │
│  POST   /api/admin/devices/{id}/activate (Reactivate)   │
│  POST   /api/admin/devices/reload  (Hot-Reload)         │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│              PostgreSQL Database                         │
│  ┌────────────────────────────────────────┐              │
│  │  modbus_devices                        │              │
│  │  ┌──────────────────────────────────┐  │              │
│  │  │ device_id: "office-eng"          │  │              │
│  │  │ host: "10.19.20.148"             │  │              │
│  │  │ port: 8899                       │  │              │
│  │  │ slave_id: 1                      │  │              │
│  │  │ timeout: 10                      │  │              │
│  │  │ framer: "RTU"                    │  │              │
│  │  │ max_retries: 5                   │  │              │
│  │  │ retry_delay: 0.1                 │  │              │
│  │  │ is_active: true                  │  │              │
│  │  │ created_at: timestamp            │  │              │
│  │  │ updated_at: timestamp            │  │              │
│  │  └──────────────────────────────────┘  │              │
│  └────────────────────────────────────────┘              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓ (POST /reload)
┌──────────────────────────────────────────────────────────┐
│         ModbusClientManager (In-Memory)                  │
│  - Loaded device configurations                          │
│  - Active Modbus connections                             │
│  - Request routing to correct slave_id                   │
└──────────────────────────────────────────────────────────┘
```

## Database Schema

```sql
CREATE TABLE modbus_devices (
    device_id VARCHAR(50) PRIMARY KEY,
    host VARCHAR(100) NOT NULL,
    port INTEGER NOT NULL,
    slave_id INTEGER NOT NULL,
    timeout INTEGER DEFAULT 10,
    framer VARCHAR(20) DEFAULT 'RTU',
    max_retries INTEGER DEFAULT 5,
    retry_delay FLOAT DEFAULT 0.1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | ✅ | Unique identifier for the device |
| `host` | string | ✅ | IP address or hostname of Modbus gateway |
| `port` | integer | ✅ | TCP port number (e.g., 502, 8899) |
| `slave_id` | integer | ✅ | Modbus slave ID (1-247) |
| `timeout` | integer | ❌ | Connection timeout in seconds (default: 10) |
| `framer` | string | ❌ | Modbus framer type: RTU, SOCKET, ASCII (default: RTU) |
| `max_retries` | integer | ❌ | Max retry attempts for failed operations (default: 5) |
| `retry_delay` | float | ❌ | Delay between retries in seconds (default: 0.1) |
| `is_active` | boolean | ❌ | Active status (default: true) |

### Valid Framer Types

- `RTU` - RTU over TCP (Modbus RTU framing)
- `SOCKET` - Modbus TCP (standard)
- `ASCII` - ASCII over TCP

## API Endpoints

### 1. List All Devices

```http
GET /api/admin/devices
```

**Response**: 200 OK
```json
[
  {
    "device_id": "office-eng",
    "host": "10.19.20.148",
    "port": 8899,
    "slave_id": 1,
    "timeout": 10,
    "framer": "RTU",
    "max_retries": 5,
    "retry_delay": 0.1,
    "is_active": true,
    "created_at": "2025-11-28T09:00:00.000000",
    "updated_at": "2025-11-28T09:00:00.000000"
  }
]
```

### 2. List Active Devices Only

```http
GET /api/admin/devices/active
```

Returns only devices where `is_active = true`.

### 3. Get Device Detail

```http
GET /api/admin/devices/{device_id}
```

**Example**:
```bash
curl http://localhost:8000/api/admin/devices/office-eng
```

**Response**: 200 OK
```json
{
  "device_id": "office-eng",
  "host": "10.19.20.148",
  "port": 8899,
  "slave_id": 1,
  "timeout": 10,
  "framer": "RTU",
  "max_retries": 5,
  "retry_delay": 0.1,
  "is_active": true,
  "created_at": "2025-11-28T09:00:00.000000",
  "updated_at": "2025-11-28T09:00:00.000000"
}
```

**Error**: 404 Not Found
```json
{
  "detail": "Device 'office-eng' not found"
}
```

### 4. Create New Device

```http
POST /api/admin/devices
Content-Type: application/json
```

**Request Body**:
```json
{
  "device_id": "warehouse-1",
  "host": "192.168.1.100",
  "port": 502,
  "slave_id": 3,
  "timeout": 10,
  "framer": "SOCKET",
  "max_retries": 3,
  "retry_delay": 0.2
}
```

**Response**: 201 Created
```json
{
  "device_id": "warehouse-1",
  "host": "192.168.1.100",
  "port": 502,
  "slave_id": 3,
  "timeout": 10,
  "framer": "SOCKET",
  "max_retries": 3,
  "retry_delay": 0.2,
  "is_active": true,
  "created_at": "2025-11-28T10:30:00.000000",
  "updated_at": "2025-11-28T10:30:00.000000"
}
```

**Error**: 409 Conflict
```json
{
  "detail": "Device 'warehouse-1' already exists"
}
```

### 5. Update Device

```http
PUT /api/admin/devices/{device_id}
Content-Type: application/json
```

**Request Body** (partial update allowed):
```json
{
  "host": "192.168.1.101",
  "timeout": 15,
  "max_retries": 10
}
```

**Response**: 200 OK
```json
{
  "device_id": "warehouse-1",
  "host": "192.168.1.101",
  "port": 502,
  "slave_id": 3,
  "timeout": 15,
  "framer": "SOCKET",
  "max_retries": 10,
  "retry_delay": 0.2,
  "is_active": true,
  "created_at": "2025-11-28T10:30:00.000000",
  "updated_at": "2025-11-28T11:00:00.000000"
}
```

### 6. Delete Device (Soft Delete)

```http
DELETE /api/admin/devices/{device_id}
```

Sets `is_active = false` without removing the record.

**Response**: 204 No Content

**Error**: 404 Not Found
```json
{
  "detail": "Device 'warehouse-1' not found"
}
```

### 7. Reactivate Device

```http
POST /api/admin/devices/{device_id}/activate
```

Sets `is_active = true` for a previously deactivated device.

**Response**: 200 OK
```json
{
  "device_id": "warehouse-1",
  "is_active": true,
  ...
}
```

### 8. Reload Device Configurations

```http
POST /api/admin/devices/reload
```

**IMPORTANT**: After creating/updating/deleting devices, you **must** call this endpoint to reload the `ModbusClientManager` with the latest configurations.

**Response**: 200 OK
```json
{
  "status": "ok",
  "message": "Reloaded 3 device(s)",
  "devices": ["office-eng", "formation", "warehouse-1"]
}
```

## Usage Examples

### Using cURL

#### Create a Device
```bash
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "production-line-1",
    "host": "10.0.1.50",
    "port": 502,
    "slave_id": 1,
    "framer": "SOCKET"
  }'
```

#### List All Devices
```bash
curl http://localhost:8000/api/admin/devices
```

#### Update a Device
```bash
curl -X PUT http://localhost:8000/api/admin/devices/production-line-1 \
  -H "Content-Type: application/json" \
  -d '{
    "timeout": 20,
    "max_retries": 10
  }'
```

#### Reload Configurations
```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

#### Delete a Device
```bash
curl -X DELETE http://localhost:8000/api/admin/devices/production-line-1
```

### Using Python

```python
import requests

BASE_URL = "http://localhost:8000/api/admin/devices"

# Create device
response = requests.post(BASE_URL, json={
    "device_id": "sensor-array-1",
    "host": "192.168.1.200",
    "port": 8899,
    "slave_id": 5,
    "framer": "RTU",
})
print(response.json())

# Reload configurations
reload_response = requests.post(f"{BASE_URL}/reload")
print(reload_response.json())

# List all devices
devices = requests.get(BASE_URL).json()
print(f"Total devices: {len(devices)}")

# Update device
update_response = requests.put(
    f"{BASE_URL}/sensor-array-1",
    json={"timeout": 15}
)
print(update_response.json())

# Reload again after update
requests.post(f"{BASE_URL}/reload")
```

### Using JavaScript/Fetch

```javascript
// Create device
const createDevice = async () => {
  const response = await fetch('http://localhost:8000/api/admin/devices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: 'hvac-controller',
      host: '10.5.5.100',
      port: 502,
      slave_id: 2,
      framer: 'SOCKET'
    })
  });
  
  const device = await response.json();
  console.log('Created:', device);
  
  // Reload configurations
  await fetch('http://localhost:8000/api/admin/devices/reload', {
    method: 'POST'
  });
};

// List devices
const listDevices = async () => {
  const response = await fetch('http://localhost:8000/api/admin/devices');
  const devices = await response.json();
  console.log('Devices:', devices);
};
```

## Workflow

### Adding a New Device

1. **Create the device** via API
2. **Reload configurations** to activate it
3. **Test connection** via device API

```bash
# Step 1: Create
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test-device",
    "host": "192.168.1.50",
    "port": 502,
    "slave_id": 1
  }'

# Step 2: Reload
curl -X POST http://localhost:8000/api/admin/devices/reload

# Step 3: Test
curl "http://localhost:8000/api/devices/test-device/registers?address=0&count=10&source=live"
```

### Updating Device Configuration

1. **Update the device** via API
2. **Reload configurations** to apply changes
3. **Old connections are closed**, new ones created

```bash
# Step 1: Update
curl -X PUT http://localhost:8000/api/admin/devices/test-device \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.51"}'

# Step 2: Reload
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Removing a Device

1. **Soft delete** the device
2. **Reload configurations**
3. **Connection is closed** and device removed from manager

```bash
# Step 1: Delete
curl -X DELETE http://localhost:8000/api/admin/devices/test-device

# Step 2: Reload
curl -X POST http://localhost:8000/api/admin/devices/reload
```

## Best Practices

### 1. Always Reload After Changes

```bash
# ❌ Wrong - changes not applied
curl -X POST http://localhost:8000/api/admin/devices -d '{...}'

# ✅ Correct - reload to apply
curl -X POST http://localhost:8000/api/admin/devices -d '{...}'
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### 2. Use Unique Device IDs

```json
{
  "device_id": "descriptive-name-location-number"
}
```

Good examples:
- `production-line-1-plc`
- `warehouse-sensor-array-2`
- `office-eng-hvac-controller`

### 3. Test Before Production

Always test new devices with `source=live` first:

```bash
curl "http://localhost:8000/api/devices/new-device/registers?address=0&count=1&source=live"
```

### 4. Monitor Connections

Check gateway status:

```bash
curl http://localhost:8000/api/devices/gateways
```

Response shows active connections:
```json
[
  {
    "host": "10.19.20.148",
    "port": 8899,
    "connected": true
  }
]
```

## Troubleshooting

### Device Not Found After Creation

**Problem**: Created device but getting 404 errors

**Solution**: You forgot to reload! Call `/reload` endpoint:
```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Connection Timeout

**Problem**: Device exists but connection times out

**Checklist**:
1. ✅ Is device IP reachable? `ping {host}`
2. ✅ Is port correct and open?
3. ✅ Is slave_id correct?
4. ✅ Is framer type correct (RTU vs SOCKET)?

**Increase timeout**:
```bash
curl -X PUT http://localhost:8000/api/admin/devices/{id} \
  -H "Content-Type: application/json" \
  -d '{"timeout": 30, "max_retries": 10}'

curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Duplicate Device Error

**Problem**: Getting 409 Conflict error

**Solution**: Device already exists. Either:
1. Use a different `device_id`
2. Update the existing device with PUT
3. Delete the old device first

## Migration

To set up devices table and seed initial data:

```bash
python migrate.py --migration 001
```

Or run all migrations:

```bash
python migrate.py
```

See [migrations/README.md](../migrations/README.md) for more details.

## Related Documentation

- [Polling Configuration](./POLLING_CONFIGURATION.md) - Configure automatic polling
- [API Reference](./API_REFERENCE.md) - Complete API documentation
- [Migrations](../migrations/README.md) - Database migrations

## Support

For issues or questions:
1. Check application logs
2. Verify database connection
3. Test with Swagger UI: `http://localhost:8000/docs`
