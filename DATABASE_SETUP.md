# Modbus Middleware - Database Migrations & Device Management

> **Complete guide to database setup and device configuration**

**[← Back to Main README](./README.md)** | **[Migrations Guide →](./migrations/README.md)** | **[Device API →](./docs/DEVICE_MANAGEMENT.md)** | **[Polling →](./docs/POLLING_CONFIGURATION.md)**

---

## 📚 Documentation Index

| Document | Description |
|----------|-------------|
| [Device Management](./docs/DEVICE_MANAGEMENT.md) | Complete device CRUD API guide |
| [Polling Configuration](./docs/POLLING_CONFIGURATION.md) | Automatic register polling setup |
| [Polling Quick Start](./docs/POLLING_QUICK_START.md) | Quick guide for testing polling |
| [Migrations README](./migrations/README.md) | Database migration system |

## 🚀 Quick Start

### 1. Setup Database

Run all migrations to create tables and seed data:

```bash
python migrate.py
```

This creates:
- ✅ `modbus_devices` table with sample devices
- ✅ `polling_targets` table with sample polling configs

### 2. Start Application

```bash
uvicorn main:app --reload
```

### 3. Access Admin APIs

| Feature | Endpoint |
|---------|----------|
| **Devices** | http://localhost:8000/api/admin/devices |
| **Polling** | http://localhost:8000/api/admin/polling |
| **API Docs** | http://localhost:8000/docs |

## 📦 Migration System

### Directory Structure

```
modbus_middleware/
├── migrate.py                          # Main migration runner
├── migrations/
│   ├── __init__.py                    # Package init
│   ├── base.py                        # Migration utilities
│   ├── README.md                      # Migration docs
│   ├── 001_initial_setup.py          # Device table
│   └── 002_add_polling_targets.py    # Polling table
└── docs/
    ├── DEVICE_MANAGEMENT.md           # Device API docs
    ├── POLLING_CONFIGURATION.md       # Polling docs
    └── POLLING_QUICK_START.md         # Quick guide
```

### Running Migrations

```bash
# Run all migrations
python migrate.py

# Run specific migration
python migrate.py --migration 001

# Run individual migration directly
python -m migrations.001_initial_setup
```

## 🔧 Device Management

### Create Device

```bash
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "warehouse-1",
    "host": "192.168.1.100",
    "port": 502,
    "slave_id": 3,
    "framer": "SOCKET"
  }'
```

### Reload Configurations (IMPORTANT!)

After creating/updating devices, **always reload**:

```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Full Device API

See [DEVICE_MANAGEMENT.md](./docs/DEVICE_MANAGEMENT.md) for complete guide.

## 📊 Polling Configuration

### Create Polling Target

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

### Hot-Reload

Changes take effect automatically within 5 seconds (next polling cycle). **No restart needed!**

### Check Cached Data

```bash
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

### Full Polling API

See [POLLING_CONFIGURATION.md](./docs/POLLING_CONFIGURATION.md) for complete guide.

## 🗂️ Database Schema

### modbus_devices

| Column | Type | Description |
|--------|------|-------------|
| device_id | VARCHAR(50) PK | Unique device identifier |
| host | VARCHAR(100) | IP address or hostname |
| port | INTEGER | TCP port number |
| slave_id | INTEGER | Modbus slave ID |
| timeout | INTEGER | Connection timeout (seconds) |
| framer | VARCHAR(20) | RTU, SOCKET, or ASCII |
| max_retries | INTEGER | Max retry attempts |
| retry_delay | FLOAT | Delay between retries |
| is_active | BOOLEAN | Active status |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

### polling_targets

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | Auto-increment ID |
| device_id | VARCHAR(50) | Reference to device |
| register_type | VARCHAR(20) | holding, input, coil, discrete |
| address | INTEGER | Starting register address |
| count | INTEGER | Number of registers (1-125) |
| is_active | BOOLEAN | Active status |
| description | VARCHAR(200) | Optional description |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## 📖 Features

### ✅ Database-Driven Configuration
- No hardcoded device configs
- Store everything in PostgreSQL
- Easy to manage via API

### ✅ Hot-Reload Support
- **Devices**: Reload via `/api/admin/devices/reload`
- **Polling**: Automatic reload every polling cycle
- No application restart needed!

### ✅ Soft Delete
- Deactivate instead of delete
- Preserve configuration history
- Easy to reactivate

### ✅ Validation
- Automatic validation of device parameters
- Check device existence before creating polling targets
- Validate register types and ranges

### ✅ Audit Trail
- Track creation timestamps
- Track update timestamps
- See full history in database

## 🛠️ API Endpoints

### Device Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/devices` | List all devices |
| GET | `/api/admin/devices/active` | List active devices |
| GET | `/api/admin/devices/{id}` | Get device details |
| POST | `/api/admin/devices` | Create device |
| PUT | `/api/admin/devices/{id}` | Update device |
| DELETE | `/api/admin/devices/{id}` | Soft delete device |
| POST | `/api/admin/devices/{id}/activate` | Reactivate device |
| POST | `/api/admin/devices/reload` | **Reload configurations** |

### Polling Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/polling` | List all polling targets |
| GET | `/api/admin/polling/active` | List active targets |
| GET | `/api/admin/polling/device/{id}` | Get targets for device |
| GET | `/api/admin/polling/{id}` | Get target details |
| POST | `/api/admin/polling` | Create polling target |
| PUT | `/api/admin/polling/{id}` | Update target |
| DELETE | `/api/admin/polling/{id}` | Soft delete target |
| POST | `/api/admin/polling/{id}/activate` | Reactivate target |

## 🧪 Testing

### 1. Run Migrations
```bash
python migrate.py
```

### 2. Start Application
```bash
uvicorn main:app --reload
```

### 3. Test Device API
```bash
# List devices
curl http://localhost:8000/api/admin/devices

# Create device
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test", "host": "localhost", "port": 502, "slave_id": 1}'

# Reload
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### 4. Test Polling API
```bash
# List polling targets
curl http://localhost:8000/api/admin/polling/active

# Create polling target
curl -X POST http://localhost:8000/api/admin/polling \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test", "register_type": "holding", "address": 0, "count": 10}'

# Wait 5 seconds, then check cache
curl "http://localhost:8000/api/devices/test/registers?address=0&count=10&source=cache"
```

## 🚨 Important Notes

### Always Reload After Device Changes!

```bash
# ❌ WRONG - changes not applied
curl -X POST /api/admin/devices -d '{...}'

# ✅ CORRECT - reload to apply
curl -X POST /api/admin/devices -d '{...}'
curl -X POST /api/admin/devices/reload
```

### Polling Auto-Reloads

Polling targets reload automatically every cycle (no manual reload needed).

### Soft Delete vs Hard Delete

- `DELETE /api/admin/devices/{id}` → Sets `is_active=false` (soft delete)
- Data remains in database
- Can be reactivated with `/activate` endpoint

## 📚 Learn More

- **[Device Management Guide](./docs/DEVICE_MANAGEMENT.md)** - Complete CRUD API documentation
- **[Polling Configuration](./docs/POLLING_CONFIGURATION.md)** - Advanced polling setup
- **[Migrations Guide](./migrations/README.md)** - Creating new migrations
- **[Swagger UI](http://localhost:8000/docs)** - Interactive API docs

## 🔍 Troubleshooting

### Database Connection Error

Check `.env` file:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/modbus_db
```

### Device Not Found After Creation

Did you reload?
```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Polling Not Working

1. Check if polling targets exist and are active
2. Check if referenced devices exist
3. Check application logs for errors
4. Verify device is reachable

### Import Errors

Run from project root:
```bash
cd d:/coding/modbus_middleware
python migrate.py
```

## 🤝 Contributing

When adding new features:

1. Create migration script in `migrations/`
2. Update `migrate.py` to include new migration
3. Document API changes in `docs/`
4. Test thoroughly before deploying

## 📝 License

[Your License Here]
