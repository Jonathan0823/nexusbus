# Quick Start: Database-Driven Polling

> **Get started with automatic polling in 5 minutes**

**[← Main README](../README.md)** | **[Setup Guide](../DATABASE_SETUP.md)** | **[Device API](./DEVICE_MANAGEMENT.md)** | **[Full Polling Guide](./POLLING_CONFIGURATION.md)** | **[Migrations](../migrations/README.md)**

---

## Setup

### 1. Run Migration
```bash
python migrate_polling_targets.py
```

This will:
- Create `polling_targets` table
- Add 2 sample polling targets

### 2. Start the Application
```bash
uvicorn main:app --reload
```

The polling service will start automatically and check the database every 5 seconds.

## Test Polling Configuration

### View Active Polling Targets
```bash
curl http://localhost:8000/api/admin/polling/active
```

Expected response:
```json
[
  {
    "id": 1,
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "is_active": true,
    "description": "Poll first 10 holding registers from office-eng device",
    "created_at": "2025-11-28T09:00:00.000000",
    "updated_at": "2025-11-28T09:00:00.000000"
  },
  {
    "id": 2,
    "device_id": "formation",
    "register_type": "input",
    "address": 0,
    "count": 5,
    "is_active": true,
    "description": "Poll first 5 input registers from formation device",
    "created_at": "2025-11-28T09:00:00.000000",
    "updated_at": "2025-11-28T09:00:00.000000"
  }
]
```

### Add New Polling Target
```bash
curl -X POST http://localhost:8000/api/admin/polling \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 100,
    "count": 5,
    "description": "Temperature sensors"
  }'
```

### Check Cached Data from Polling
```bash
# Wait 5-10 seconds for polling to populate cache
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

Expected response:
```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "source": "cache",
  "cached_at": "2025-11-28T09:15:30.123456+00:00"
}
```

Notice `"source": "cache"` - this means data came from polling, not live read!

### Update Polling Target
```bash
curl -X PUT http://localhost:8000/api/admin/polling/1 \
  -H "Content-Type: application/json" \
  -d '{
    "count": 20,
    "description": "Increased to 20 registers"
  }'
```

### Disable Polling Target
```bash
curl -X DELETE http://localhost:8000/api/admin/polling/1
```

The target will be soft-deleted (`is_active=false`) and polling will stop on next cycle.

### Re-enable Polling Target
```bash
curl -X POST http://localhost:8000/api/admin/polling/1/activate
```

## Monitoring Logs

Watch the logs to see polling in action:

```
INFO:app.services.poller:Starting polling service (database mode: True, interval: 5s)
DEBUG:app.services.poller:Polling 2 target(s)...
DEBUG:app.services.poller:Polled office-eng holding addr=0 count=10 → [100, 200, 300, ...]
DEBUG:app.services.poller:Polled formation input addr=0 count=5 → [50, 60, 70, 80, 90]
```

## Benefits Over Hardcoded Configuration

| Feature | Hardcoded (`devices.py`) | Database-Driven |
|---------|-------------------------|-----------------|
| Add new target | Edit code, restart | API call, no restart |
| Remove target | Edit code, restart | API call, no restart |
| Enable/disable | Edit code, restart | API call, no restart |
| View targets | Read code | API call |
| Audit trail | Git history | Database timestamps |
| Management UI | Not possible | Easy with API |

## Next Steps

- **Build Admin UI**: Use the API to create a web interface for managing polling targets
- **Add Webhooks**: Trigger actions when polling detects changes
- **Export Data**: Create endpoints to export polling data history
- **Alerting**: Add monitoring for polling failures

See full documentation: [POLLING_CONFIGURATION.md](./POLLING_CONFIGURATION.md)
