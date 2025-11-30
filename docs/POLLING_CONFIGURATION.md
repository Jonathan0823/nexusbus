# Database-Driven Polling Configuration

> **Configure automatic register polling from database with hot-reload**

**[← Main README](../README.md)** | **[Setup Guide](../DATABASE_SETUP.md)** | **[Device API](./DEVICE_MANAGEMENT.md)** | **[Quick Start →](./POLLING_QUICK_START.md)** | **[Migrations](../migrations/README.md)**

---

## 📚 Quick Navigation

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Usage Examples](#usage-examples)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

---

Polling targets can now be configured dynamically from the database instead of being hardcoded in `devices.py`. The polling service automatically reloads targets from the database on each polling cycle, providing **hot-reload** capability.

## Features

✅ **Database Configuration**: Store polling targets in PostgreSQL database
✅ **CRUD API**: Full REST API for managing polling targets
✅ **Hot-Reload**: Changes take effect on next polling cycle (no restart needed)
✅ **Validation**: Automatic validation of device_id and register_type
✅ **Soft Delete**: Targets can be deactivated without deletion
✅ **Per-Device Queries**: Filter polling targets by device

## Architecture

```
┌─────────────────────────────────────────┐
│   Database (PostgreSQL)                 │
│   ┌───────────────────────────────┐     │
│   │  polling_targets table        │     │
│   │  - id (PK)                    │     │
│   │  - device_id                  │     │
│   │  - register_type              │     │
│   │  - address                    │     │
│   │  - count                      │     │
│   │  - is_active                  │     │
│   │  - description                │     │
│   └───────────────────────────────┘     │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   Polling Service                       │
│   - Loads targets from DB every cycle   │
│   - Polls Modbus devices                │
│   - Stores results in cache             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   Cache (In-Memory)                     │
│   - Stores latest register values       │
│   - Accessed by GET API                 │
└─────────────────────────────────────────┘
```

## API Endpoints

### List All Polling Targets
```http
GET /api/admin/polling
```

Response:
```json
[
  {
    "id": 1,
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "is_active": true,
    "description": "Poll first 10 holding registers",
    "created_at": "2025-11-28T09:00:00Z",
    "updated_at": "2025-11-28T09:00:00Z"
  }
]
```

### List Active Polling Targets Only
```http
GET /api/admin/polling/active
```

### Get Polling Targets for Specific Device
```http
GET /api/admin/polling/device/{device_id}
```

Example:
```bash
GET /api/admin/polling/device/office-eng
```

### Create New Polling Target
```http
POST /api/admin/polling
Content-Type: application/json

{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 100,
  "count": 5,
  "description": "Temperature sensors"
}
```

### Update Polling Target
```http
PUT /api/admin/polling/{id}
Content-Type: application/json

{
  "count": 10,
  "description": "Updated description"
}
```

### Delete Polling Target (Soft Delete)
```http
DELETE /api/admin/polling/{id}
```

### Reactivate Polling Target
```http
POST /api/admin/polling/{id}/activate
```

## Database Schema

```sql
CREATE TABLE polling_targets (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    register_type VARCHAR(20) NOT NULL,
    address INTEGER NOT NULL,
    count INTEGER DEFAULT 1 CHECK (count >= 1 AND count <= 125),
    is_active BOOLEAN DEFAULT TRUE,
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_polling_targets_device_id ON polling_targets(device_id);
```

## Valid Register Types

- `holding` - Holding Registers (read/write)
- `input` - Input Registers (read-only)
- `coil` - Coils (read/write bits)
- `discrete` - Discrete Inputs (read-only bits)

## Usage Examples

### Using cURL

**Create a polling target:**
```bash
curl -X POST http://localhost:8000/api/admin/polling \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "description": "Main control registers"
  }'
```

**List all active targets:**
```bash
curl http://localhost:8000/api/admin/polling/active
```

**Update a target:**
```bash
curl -X PUT http://localhost:8000/api/admin/polling/1 \
  -H "Content-Type: application/json" \
  -d '{
    "count": 20
  }'
```

**Delete (deactivate) a target:**
```bash
curl -X DELETE http://localhost:8000/api/admin/polling/1
```

### Using Python

```python
import requests

BASE_URL = "http://localhost:8000/api/admin/polling"

# Create polling target
response = requests.post(BASE_URL, json={
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "description": "Temperature sensors"
})
print(response.json())

# List all targets
response = requests.get(BASE_URL)
targets = response.json()
print(f"Found {len(targets)} polling targets")

# Get targets for specific device
response = requests.get(f"{BASE_URL}/device/office-eng")
print(response.json())
```

## How It Works

1. **Startup**: Application starts polling service with `use_database=True`
2. **Polling Cycle**: Every 5 seconds (configurable), the service:
   - Loads active polling targets from database
   - For each target:
     - Reads register values from Modbus device
     - Stores results in cache
3. **Hot-Reload**: Any changes to polling targets take effect on next cycle
4. **API Access**: GET endpoints can access cached values with `source=cache`

## Configuration

In `app/config/devices.py`:

```python
# Polling interval in seconds
POLL_INTERVAL_SECONDS = 5

# Fallback targets if database is empty (optional)
DEFAULT_POLL_TARGETS = []
```

## Migration

To create the `polling_targets` table and add sample data:

```bash
python migrate_polling_targets.py
```

## Benefits

1. **No Restart Required**: Add/remove/update polling targets without restarting the service
2. **Dynamic Configuration**: Manage polling targets via API or database admin tools
3. **Audit Trail**: Track when targets were created/updated
4. **Easy Management**: Enable/disable targets without deletion
5. **Device Validation**: Automatically validates that device exists before creating target

## Monitoring

Check polling status in logs:
```
INFO:app.services.poller:Starting polling service (database mode: True, interval: 5s)
DEBUG:app.services.poller:Polling 2 target(s)...
DEBUG:app.services.poller:Polled office-eng holding addr=0 count=10 → [100, 200, ...]
```

## Troubleshooting

### No targets are being polled

Check database:
```bash
curl http://localhost:8000/api/admin/polling/active
```

Ensure `is_active=true` for targets you want to poll.

### Target not found error

Ensure the `device_id` in polling target matches an existing device:
```bash
curl http://localhost:8000/api/admin/devices
```

### Cache not updating

Check logs for polling errors. Verify Modbus device is reachable:
```bash
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=live"
```
