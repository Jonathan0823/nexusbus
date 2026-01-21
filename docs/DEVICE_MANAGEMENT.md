# Device Management Guide

> **Comprehensive guide to managing Modbus devices via API**

**[← Main README](../README.md)** | **[Database Setup](../DATABASE_SETUP.md)** | **[Polling Config](./POLLING_CONFIGURATION.md)** | **[MQTT Guide](./MQTT_INTEGRATION.md)**

---

## 📚 Overview

The Device Management API allows you to register, configure, and manage Modbus devices dynamically. All configurations are stored in the database and can be updated without restarting the application.

## 🏗️ Architecture

The system uses a **connection pooling** mechanism:

- **Shared Gateways**: Multiple devices on the same IP/Port share a single TCP connection.
- **Request Serialization**: Requests to the same gateway are queued to prevent collisions.
- **Automatic Recovery**: Broken connections are automatically detected and reset.

---

## 🚀 API Endpoints

### 1. List All Devices

Get a list of all configured devices.

```http
GET /api/admin/devices
```

**Response:**

```json
[
  {
    "device_id": "office-eng",
    "host": "localhost",
    "port": 5020,
    "slave_id": 1,
    "framer": "tcp",
    "is_active": true,
    "timeout": 10,
    "max_retries": 3
  }
]
```

### 2. Create New Device

Register a new Modbus device.

```http
POST /api/admin/devices
Content-Type: application/json
```

**Body:**

```json
{
  "device_id": "warehouse-1",
  "host": "192.168.1.100",
  "port": 502,
  "slave_id": 1,
  "framer": "tcp",
  "timeout": 5,
  "description": "Main warehouse sensor"
}
```

### 3. Update Device

Update an existing device's configuration.

```http
PUT /api/admin/devices/{device_id}
```

**Body:**

```json
{
  "timeout": 10,
  "max_retries": 5
}
```

### 4. Delete Device (Soft Delete)

Deactivate a device. It remains in the database but `is_active` is set to `false`.

```http
DELETE /api/admin/devices/{device_id}
```

### 5. Reload Device Configurations

**Critical Step**: After adding or modifying devices, you must reload the configuration for changes to take effect in the running application.

```http
POST /api/admin/devices/reload
```

---

## ⚙️ Device Parameters

| Parameter     | Type    | Required | Description                                              | Default |
| :------------ | :------ | :------- | :------------------------------------------------------- | :------ |
| `device_id`   | string  | ✅       | Unique identifier for the device. No spaces recommended. | -       |
| `host`        | string  | ✅       | IP address or hostname.                                  | -       |
| `port`        | integer | ✅       | TCP port number.                                         | 502     |
| `slave_id`    | integer | ✅       | Modbus Slave ID (Unit ID).                               | 1       |
| `framer`      | string  | ❌       | Protocol type (`tcp`, `rtu`, `ascii`, `udp`).            | `tcp`   |
| `timeout`     | float   | ❌       | Read/Write timeout in seconds.                           | 3.0     |
| `max_retries` | integer | ❌       | Number of retries on failure.                            | 3       |
| `retry_delay` | float   | ❌       | Delay between retries in seconds.                        | 0.1     |

---

## 💡 Usage Examples

### Reading Registers

Once a device is registered and active, you can read its registers:

```bash
# Read 10 holding registers starting at 0
curl "http://localhost:8000/api/devices/warehouse-1/registers?address=0&count=10&register_type=holding"
```

### Writing Registers

```bash
# Write value 123 to holding register 5
curl -X POST http://localhost:8000/api/devices/warehouse-1/registers/write \
  -H "Content-Type: application/json" \
  -d '{
    "address": 5,
    "value": 123,
    "register_type": "holding"
  }'
```

---

## 🔄 Hot-Reload Support

The application supports hot-reloading of device configurations. This means you don't need to restart the entire server when adding a new device.

**Workflow:**

1.  `POST /api/admin/devices` (Add new device to DB)
2.  `POST /api/admin/devices/reload` (Tell app to refresh connections)
3.  Start using the new device immediately.

---

## 🔧 Troubleshooting

### "Device not found"

- Did you run the **reload** endpoint? (`POST /api/admin/devices/reload`)
- Check if the device is `is_active: true`.

### "Connection refused"

- Verify IP and Port.
- Check if the physical device is powered on.
- Verify no firewall is blocking the connection.

### "Gateway busy"

- If multiple devices share the same IP/Port (Gateway), and one is slow, others might wait.
- Increase `timeout` if the network is slow.

### Data is Stale

- If reading with `source=cache`, ensure the Polling Service is running and configured for this device.
- Check [Polling Configuration](./POLLING_CONFIGURATION.md).

---

