# Modbus Middleware

> **FastAPI-based middleware for Modbus TCP/RTU devices with database-driven configuration**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

---

## 📚 Documentation Navigation

| **Quick Start**                       | **Device Management**                                                  | **Polling**                                       | **MQTT**                                       | **Migrations**                            |
| ------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------- | ----------------------------------------- |
| [Database Setup](./DATABASE_SETUP.md) | [Device API Guide](./docs/DEVICE_MANAGEMENT.md)                        | [Polling Config](./docs/POLLING_CONFIGURATION.md) | [MQTT Guide](./docs/MQTT_INTEGRATION.md)       | [Migration Guide](./migrations/README.md) |
- ✅ **Database-Driven Configuration** - Store and manage Modbus devices in PostgreSQL
- ✅ **Dynamic Device Management** - Add/update/remove devices via REST API without restart
- ✅ **Automatic Polling** - Configure registers to poll automatically from database
- ✅ **Hot-Reload** - Apply configuration changes without server restart
- ✅ **Connection Pooling** - Efficiently manage Modbus TCP connections & shared gateways
- ✅ **Request Timeout Handling** - Automatic timeout and connection reset
- ✅ **REST API** - Complete API for device interaction and management
- ✅ **Async Support** - Full async/await with asyncpg for optimal performance
- ✅ **Caching** - Register value caching for improved performance
- ✅ **MQTT Integration** - Real-time data publishing to MQTT brokers
- ✅ **Soft Delete** - Deactivate devices/polling without losing configuration

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
git clone <repository-url>
cd modbus_middleware

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

**Configure Environment:**

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

**Run Migrations:**

```bash
python migrate.py
```

This creates:

- ✅ `modbus_devices` table with sample devices
- ✅ `polling_targets` table with sample polling configs

**[Full Migration Guide →](./migrations/README.md)**

### 3. Start Application

```bash
uvicorn main:app --reload
```

**Access:**

- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## 📖 API Quick Reference

### Device Operations

| Endpoint                            | Method | Description    | Docs                                              |
| ----------------------------------- | ------ | -------------- | ------------------------------------------------- |
| `/api/devices`                      | GET    | List devices   | [→](./docs/DEVICE_MANAGEMENT.md#list-all-devices) |
| `/api/devices/{id}/registers`       | GET    | Read registers | [→](#read-registers)                              |
| `/api/devices/{id}/registers/write` | POST   | Write register | [→](#write-register)                              |
| `/api/devices/gateways`             | GET    | Gateway status | [→](#list-gateways)                               |

### Admin - Device Management

| Endpoint                    | Method | Description            | Docs                                                          |
| --------------------------- | ------ | ---------------------- | ------------------------------------------------------------- |
| `/api/admin/devices`        | GET    | List all devices       | [→](./docs/DEVICE_MANAGEMENT.md#list-all-devices)             |
| `/api/admin/devices`        | POST   | Create device          | [→](./docs/DEVICE_MANAGEMENT.md#create-new-device)            |
| `/api/admin/devices/{id}`   | PUT    | Update device          | [→](./docs/DEVICE_MANAGEMENT.md#update-device)                |
| `/api/admin/devices/{id}`   | DELETE | Soft delete            | [→](./docs/DEVICE_MANAGEMENT.md#delete-device-soft-delete)    |
| `/api/admin/devices/reload` | POST   | **Hot-reload configs** | [→](./docs/DEVICE_MANAGEMENT.md#reload-device-configurations) |

### Admin - Polling Management

| Endpoint                  | Method | Description           | Docs                                                                   |
| ------------------------- | ------ | --------------------- | ---------------------------------------------------------------------- |
| `/api/admin/polling`      | GET    | List polling targets  | [→](./docs/POLLING_CONFIGURATION.md#list-all-polling-targets)          |
| `/api/admin/polling`      | POST   | Create polling target | [→](./docs/POLLING_CONFIGURATION.md#create-new-polling-target)         |
| `/api/admin/polling/{id}` | PUT    | Update target         | [→](./docs/POLLING_CONFIGURATION.md#update-polling-target)             |
| `/api/admin/polling/{id}` | DELETE | Soft delete           | [→](./docs/POLLING_CONFIGURATION.md#delete-polling-target-soft-delete) |

### Admin - Cache Management

| Endpoint                     | Method | Description            | Docs |
| ---------------------------- | ------ | ---------------------- | ---- |
| `/api/admin/cache`           | GET    | Inspect all cache      | -    |
| `/api/admin/cache/stats`     | GET    | Cache statistics       | -    |
| `/api/admin/cache/device/{id}` | GET  | Inspect device cache   | -    |
| `/api/admin/cache`           | DELETE | Clear all cache        | -    |

**[Complete API Documentation →](./docs/DEVICE_MANAGEMENT.md)**

---

## 📦 Configuration

### Environment Variables

This application uses a `.env` file for configuration. Copy `.env.example` to `.env` to start.

**Database Configuration**

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string. | `postgresql+asyncpg://postgres:postgres@localhost:5432/modbus_db` |
| `DATABASE_ECHO` | If `true`, logs SQL queries. | `false` |

**MQTT Configuration (Optional)**

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MQTT_BROKER_HOST` | Broker hostname/IP. Set to enable MQTT. | `None` |
| `MQTT_BROKER_PORT` | Broker port number. | `1883` |
| `MQTT_USERNAME` | MQTT Username. | `None` |
| `MQTT_PASSWORD` | MQTT Password. | `None` |
| `MQTT_TOPIC_PREFIX` | Prefix for published topics. | `modbus/data` |

**Application Settings**

| Variable | Description | Default |
| :--- | :--- | :--- |
| `APP_NAME` | Application name. | `Modbus Middleware` |
| `APP_VERSION` | Application version. | `0.1.0` |
| `POLL_INTERVAL_SECONDS` | Polling interval for background service. | `5` |

### Device Parameters

| Parameter     | Type    | Required | Description                     | Default |
| ------------- | ------- | -------- | ------------------------------- | ------- |
| `device_id`   | string  | ✅       | Unique device identifier        | -       |
| `host`        | string  | ✅       | IP address or hostname          | -       |
| `port`        | integer | ✅       | TCP port (e.g., 502, 8899)      | -       |
| `slave_id`    | integer | ✅       | Modbus slave ID (1-247)         | -       |
| `timeout`     | integer | ❌       | Connection timeout (seconds)    | 10      |
| `framer`      | string  | ❌       | RTU, SOCKET, or ASCII           | RTU     |
| `max_retries` | integer | ❌       | Max retry attempts              | 5       |
| `retry_delay` | float   | ❌       | Delay between retries (seconds) | 0.1     |

**[Full Configuration Guide →](./docs/DEVICE_MANAGEMENT.md#device-parameters)**

---

## 💡 Usage Examples

### Read Registers

```bash
# Read 10 holding registers starting at address 0
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10"

# Read from cache (faster, uses polling data)
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

### Write Register

```bash
curl -X POST http://localhost:8000/api/devices/office-eng/registers/write \
  -H "Content-Type: application/json" \
  -d '{"address": 10, "value": 123, "register_type": "holding"}'
```

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

# Reload to apply changes
curl -X POST http://localhost:8000/api/admin/devices/reload
```

**[More Examples →](./docs/DEVICE_MANAGEMENT.md#usage-examples)**

### Configure Polling

```bash
# Create polling target
curl -X POST http://localhost:8000/api/admin/polling \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "description": "Main control registers"
  }'

# Changes apply automatically (hot-reload)
# Wait 5 seconds, then check cache
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

**[Polling Guide →](./docs/POLLING_CONFIGURATION.md)**

---

## 🗂️ Project Structure

```
modbus_middleware/
├── .env.example                       # Environment variables template
├── DATABASE_SETUP.md                  # Setup guide & docs index
├── main.py                            # Application entry point
├── migrate.py                         # Main migration runner
├── requirements.txt                   # Python dependencies
│
├── app/
│   ├── __init__.py
│   ├── dependencies.py               # Dependency injection
│   ├── schemas.py                    # Pydantic schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── admin_routes.py           # Admin device management
│   │   ├── cache_routes.py           # Admin cache inspection
│   │   ├── polling_routes.py         # Admin polling management
│   │   └── routes.py                 # Device API endpoints
│   ├── config/
│   │   ├── __init__.py
│   │   └── devices.py                # Device configuration loader
│   ├── core/
│   │   ├── __init__.py
│   │   ├── cache.py                  # Register caching
│   │   ├── config.py                 # Application settings
│   │   ├── modbus_client.py          # Modbus client manager
│   │   └── mqtt_client.py            # MQTT client manager
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py             # Database connection
│   │   ├── crud.py                   # CRUD operations
│   │   └── models.py                 # SQLModel database models
│   └── services/
│       ├── __init__.py
│       └── poller.py                 # Background polling service
│
├── docs/                              # Documentation
│   ├── CACHE_INSPECTION_GUIDE.md     # Cache debugging guide
│   ├── DEVICE_MANAGEMENT.md          # Device API guide
│   ├── MQTT_INTEGRATION.md           # MQTT integration guide
│   ├── POLLING_CONFIGURATION.md      # Polling guide
│   └── POLLING_QUICK_START.md        # Quick polling guide
│
└── migrations/                        # Database migrations
    ├── README.md                     # Migration guide
    ├── base.py                       # Migration utilities
    ├── 001_initial_setup.py          # Migration: Create devices table
    └── 002_add_polling_targets.py    # Migration: Create polling table
```

---

## 🎯 Key Features Explained

### Hot-Reload Configuration

**No restart needed!**

```bash
# 1. Add device
curl -X POST /api/admin/devices -d '{...}'

# 2. Reload (applies instantly)
curl -X POST /api/admin/devices/reload

# 3. Use immediately
curl "http://localhost:8000/api/devices/new-device/registers?..."
```

**Polling auto-reloads** every cycle (default: 5 seconds).

**[Learn More →](./docs/DEVICE_MANAGEMENT.md#hot-reload-support)**

### Automatic Polling

Configure registers to poll automatically and serve from cache:

```bash
# Configure polling via database
POST /api/admin/polling

# Data polled every 5 seconds
# Access cached data (fast!)
GET /api/devices/{id}/registers?source=cache
```

**[Polling Guide →](./docs/POLLING_CONFIGURATION.md)**

### Connection Management

- **Shared Gateways**: Multiple devices on same gateway share one connection
- **Auto Recovery**: Timeout handling with automatic reconnection
- **Request Serialization**: Prevents slave ID conflicts
- **Thread Pooling**: Non-blocking Modbus operations

**[Architecture Details →](./docs/DEVICE_MANAGEMENT.md#architecture)**

---

## 🧪 Testing

```bash
# 1. Check health
curl http://localhost:8000/health

# 2. List devices
curl http://localhost:8000/api/admin/devices

# 3. Test read
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10"

# 4. Check gateway status
curl http://localhost:8000/api/devices/gateways
```

**[Full Testing Guide →](./docs/POLLING_QUICK_START.md)**

---

## 🔧 Development

### Running in Development

```bash
uvicorn main:app --reload --log-level debug
```

### Creating New Migrations

```bash
# Create migration file
cp migrations/001_initial_setup.py migrations/003_my_feature.py

# Edit the migration
# Update migrate.py to include it

# Run it
python migrate.py --migration 003
```

**[Migration Guide →](./migrations/README.md#creating-new-migrations)**

---

## ⚠️ Important Notes

### Always Reload After Device Changes

```bash
# ❌ WRONG - changes won't apply
curl -X POST /api/admin/devices -d '{...}'

# ✅ CORRECT - reload to apply
curl -X POST /api/admin/devices -d '{...}'
curl -X POST /api/admin/devices/reload
```

### Polling Auto-Reloads

Polling configuration reloads automatically every polling cycle. **No manual reload needed for polling!**

### Soft Delete

- DELETE endpoints set `is_active=false` (preserves data)
- Reactivate with `/activate` endpoint
- Data remains in database for audit trail

---

## 📚 Learn More

### By Topic

- **Getting Started**: [DATABASE_SETUP.md](./DATABASE_SETUP.md)
- **Device Management**: [DEVICE_MANAGEMENT.md](./docs/DEVICE_MANAGEMENT.md)
- **Polling Setup**: [POLLING_CONFIGURATION.md](./docs/POLLING_CONFIGURATION.md)
- **Quick Testing**: [POLLING_QUICK_START.md](./docs/POLLING_QUICK_START.md)
- **Database Migrations**: [migrations/README.md](./migrations/README.md)

### By Task

| I want to...        | Read this                                                              |
| ------------------- | ---------------------------------------------------------------------- |
| Set up the database | [DATABASE_SETUP.md](./DATABASE_SETUP.md)                               |
| Add a new device    | [Device Creation Guide](./docs/DEVICE_MANAGEMENT.md#create-new-device) |
| Configure polling   | [Polling Configuration](./docs/POLLING_CONFIGURATION.md)               |
| Create a migration  | [Migration Guide](./migrations/README.md#creating-new-migrations)      |
| Troubleshoot issues | [Troubleshooting](#troubleshooting)                                    |

---

## 🚨 Troubleshooting

### Database Connection Issues

Check `.env` configuration:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/modbus_db
```

If database is unavailable, app falls back to hardcoded configs in `app/config/devices.py`.

**[More Help →](./docs/DEVICE_MANAGEMENT.md#troubleshooting)**

### Device Not Found

Did you forget to reload?

```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

### Modbus Timeout

1. Check device connectivity: `ping {host}`
2. Verify port is open
3. Confirm slave_id is correct
4. Check gateway status: `GET /api/devices/gateways`
5. Increase timeout via Admin API

**[Troubleshooting Guide →](./docs/DEVICE_MANAGEMENT.md#troubleshooting)**

---

## 📝 License

[Your License Here]

---

## 🔗 Quick Links

- **[📖 Complete Documentation Index](./DATABASE_SETUP.md)**
- **[🔧 Device API Reference](./docs/DEVICE_MANAGEMENT.md)**
- **[📊 Polling Configuration](./docs/POLLING_CONFIGURATION.md)**
- **[📡 MQTT Integration](./docs/MQTT_INTEGRATION.md)**
- **[🗃️ Database Migrations](./migrations/README.md)**
- **[💻 Interactive API Docs](http://localhost:8000/docs)** (when running)

---

**Built with ❤️ using FastAPI, PostgreSQL, and pymodbus**