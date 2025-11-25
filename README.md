# Modbus Middleware

A FastAPI-based middleware application designed to interface with Modbus devices (TCP/RTU). It manages connections, handles device configuration via PostgreSQL database, and exposes a REST API for reading/writing registers and managing devices dynamically.

## Features

- **Database-Driven Configuration**: Store and manage Modbus device configurations in PostgreSQL
- **Dynamic Device Management**: Add, update, or remove devices via REST API without server restart
- **Connection Pooling**: Efficiently manages Modbus TCP connections, including shared gateways
- **Request Timeout Handling**: Automatic timeout and connection reset for unresponsive devices
- **REST API**: Simple endpoints to interact with Modbus devices and manage configurations
- **Async Support**: Full async/await support with asyncpg for optimal performance
- **Polling**: Optional background polling of registers
- **Caching**: Register value caching for improved performance

## Installation

1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python -m venv venv
    # On Windows PowerShell:
    .\venv\Scripts\Activate.ps1
    # On Windows CMD:
    venv\Scripts\activate.bat
    # On Linux/Mac:
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Database Setup

This application uses PostgreSQL to store device configurations.

### 1. Install PostgreSQL

Make sure PostgreSQL is installed and running on your system.

### 2. Create Database

```sql
CREATE DATABASE modbus_db;
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update with your database credentials:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/modbus_db
DATABASE_ECHO=false
```

### 4. Initialize Database

Run the setup script to create tables and seed initial devices:

```bash
python setup_db.py
```

This will:

- Create the `modbus_devices` table
- Seed initial device configurations from hardcoded defaults

## Usage

Start the application using `uvicorn`:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive API documentation is available at `http://localhost:8000/docs`.

## Configuration

### Device Configuration

Devices can be configured in two ways:

1. **Database (Recommended)**: Manage devices via Admin API endpoints
2. **Hardcoded Fallback**: Defined in `app/config/devices.py` (used if database is unavailable)

### Device Parameters

- `device_id` (str): Unique identifier for the device (used in API URLs)
- `host` (str): IP address of the Modbus device or gateway
- `port` (int): TCP port (default is usually 502 or 8899 for some gateways)
- `slave_id` (int): The Modbus Slave ID (Unit ID)
- `timeout` (int): Connection/Read timeout in seconds (default: 10)
- `framer` (str): The framing used (`RTU` or `SOCKET`)
- `max_retries` (int): Maximum retry attempts (default: 5)
- `retry_delay` (float): Delay between retries in seconds (default: 0.1)

### Shared Gateways

If multiple devices share the same `host` and `port` (e.g., multiple RS485 devices connected to a single Modbus TCP Gateway), the `ModbusClientManager` will automatically handle connection sharing and serialization.

### Timeout Configuration

API requests have a 5-second timeout by default. If a Modbus request takes longer, it will automatically timeout and reset the connection. Configure in `app/config/devices.py`:

```python
API_REQUEST_TIMEOUT_SECONDS = 5  # Adjust as needed
```

### Polling Configuration

Configure background polling in `app/config/devices.py`:

- `DEFAULT_POLL_TARGETS`: A list of registers to poll periodically
- `POLL_INTERVAL_SECONDS`: How often to poll (in seconds)

## Project Structure

```
modbus_middleware/
├── app/
│   ├── api/
│   │   ├── routes.py          # Modbus device API endpoints
│   │   └── admin_routes.py    # Admin API for device management
│   ├── config/
│   │   └── devices.py         # Device configuration loader
│   ├── core/
│   │   ├── config.py          # Application settings
│   │   ├── modbus_client.py   # Modbus client manager
│   │   └── cache.py           # Register caching
│   ├── database/
│   │   ├── models.py          # SQLModel database models
│   │   ├── connection.py      # Database connection
│   │   └── crud.py            # CRUD operations
│   └── services/
│       └── poller.py          # Background polling service
├── main.py                    # Application entry point
├── setup_db.py                # Database setup script
├── requirements.txt           # Python dependencies
└── .env.example               # Environment variables template
```

## API Endpoints

### Modbus Device API

The Modbus API is prefixed with `/api/devices`.

#### List Devices

**GET** `/api/devices`

Returns a list of all configured devices.

#### List Gateways

**GET** `/api/devices/gateways`

Returns the status of all active Modbus gateways (connections).

#### Read Registers

**GET** `/api/devices/{device_id}/registers`

Reads registers from a device.

**Parameters:**

- `device_id` (path): The ID of the device
- `address` (query): Starting register address (0-based)
- `count` (query): Number of registers to read (default: 1, max: 125)
- `register_type` (query): Type of register (`holding`, `input`, `coil`, `discrete`). Default: `holding`
- `source` (query): `live` or `cache`. Default: `live`

**Example:**

```bash
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10"
```

#### Write Register

**POST** `/api/devices/{device_id}/registers/write`

Writes a value to a holding register.

**Body:**

```json
{
  "address": 10,
  "value": 123,
  "register_type": "holding"
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/devices/office-eng/registers/write \
  -H "Content-Type: application/json" \
  -d '{"address": 10, "value": 123, "register_type": "holding"}'
```

---

### Admin API

The Admin API is prefixed with `/api/admin/devices`.

#### List All Devices

**GET** `/api/admin/devices`

Returns all devices including inactive ones.

#### List Active Devices

**GET** `/api/admin/devices/active`

Returns only active devices.

#### Get Device Details

**GET** `/api/admin/devices/{device_id}`

Get details of a specific device.

#### Create Device

**POST** `/api/admin/devices`

Create a new Modbus device configuration.

**Body:**

```json
{
  "device_id": "new-device",
  "host": "10.19.20.149",
  "port": 8899,
  "slave_id": 1,
  "timeout": 10,
  "framer": "RTU"
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "new-device",
    "host": "10.19.20.149",
    "port": 8899,
    "slave_id": 1
  }'
```

#### Update Device

**PUT** `/api/admin/devices/{device_id}`

Update device configuration.

**Body:**

```json
{
  "timeout": 15,
  "max_retries": 3
}
```

#### Delete Device

**DELETE** `/api/admin/devices/{device_id}`

Soft delete a device (sets `is_active` to false).

#### Activate Device

**POST** `/api/admin/devices/{device_id}/activate`

Reactivate a previously deleted device.

#### Reload Configurations

**POST** `/api/admin/devices/reload`

Reload device configurations from database into the Modbus manager without restarting the server.

**Example:**

```bash
curl -X POST http://localhost:8000/api/admin/devices/reload
```

## Features in Detail

### Automatic Timeout & Recovery

- API requests timeout after 5 seconds if Modbus device is unresponsive
- Automatically resets the gateway connection on timeout
- Next request will attempt a fresh connection
- No manual server restart needed

### Database-Driven Configuration

- Device configurations stored in PostgreSQL
- Manage devices via REST API
- Hot reload configurations without server restart
- Fallback to hardcoded configs if database unavailable

### Async Performance

- Full async/await support throughout the application
- Uses `asyncpg` for non-blocking database operations
- Concurrent request handling for optimal throughput
- Thread pool for blocking Modbus operations

## Health Check

**GET** `/health`

Returns server health status.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok"
}
```

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --log-level debug
```

### Database Migrations

For production, use Alembic for database migrations:

```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Create a migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Troubleshooting

### Database Connection Issues

If the application fails to connect to the database, it will automatically fall back to hardcoded device configurations in `app/config/devices.py`.

Check logs for:

```
WARNING: Failed to load devices from database: <error>. Using hardcoded configs.
```

### Modbus Timeout Issues

If Modbus requests are timing out:

1. Check device connectivity
2. Verify IP address and port
3. Confirm slave_id is correct
4. Increase timeout value via Admin API
5. Check gateway connection status: `GET /api/devices/gateways`

### Connection Reset

If you see "Connection reset" messages, the timeout handler is working correctly. The gateway will automatically reconnect on the next request.

## License

[Your License Here]
