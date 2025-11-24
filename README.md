# Modbus Middleware

A FastAPI-based middleware application designed to interface with Modbus devices (TCP/RTU). It manages connections, handles device configuration, and exposes a REST API for reading and writing registers.

## Features

-   **Device Management**: Centralized configuration for multiple Modbus devices.
-   **Connection Pooling**: Efficiently manages Modbus TCP connections, including shared gateways.
-   **REST API**: Simple endpoints to interact with Modbus devices.
-   **Polling**: Optional background polling of registers.

## Installation

1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Start the application using `uvicorn` (ensure uvicorn is installed, or run via python if a runner script exists, but typically for FastAPI):

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive API documentation is available at `http://localhost:8000/docs`.

## Configuration

The main configuration file is located at `app/config/devices.py`. This file defines the devices the middleware will connect to.

### Device Configuration (`DEVICE_CONFIGS`)

The `DEVICE_CONFIGS` list contains `DeviceConfig` objects. Each object represents a single Modbus device (or slave).

**Parameters:**

-   `device_id` (str): Unique identifier for the device (used in API URLs).
-   `host` (str): IP address of the Modbus device or gateway.
-   `port` (int): TCP port (default is usually 502 or 8899 for some gateways).
-   `slave_id` (int): The Modbus Slave ID (Unit ID).
-   `timeout` (int): Connection/Read timeout in seconds.
-   `framer` (FramerType): The framing used. Common values:
    -   `FramerType.SOCKET` (Modbus TCP)
    -   `FramerType.RTU` (Modbus RTU over TCP)

**Example:**

```python
DeviceConfig(
    device_id="sensor-01",
    host="192.168.1.100",
    port=502,
    slave_id=1,
    framer=FramerType.SOCKET
)
```

### Shared Gateways

If multiple devices share the same `host` and `port` (e.g., multiple RS485 devices connected to a single Modbus TCP Gateway), the `ModbusClientManager` will automatically handle connection sharing and serialization. You just need to define them as separate `DeviceConfig` entries with different `slave_id`s.

### Polling Configuration

You can configure background polling in `app/config/devices.py`:

-   `DEFAULT_POLL_TARGETS`: A list of registers to poll periodically.
-   `POLL_INTERVAL_SECONDS`: How often to poll (in seconds).

## Project Structure

-   `app/config/`: Configuration files.
-   `app/core/`: Core logic (Modbus client, caching).
-   `app/api/`: API route definitions.
-   `main.py`: Application entry point.

## API Endpoints

The API is prefixed with `/api`.

### List Devices
**GET** `/api/devices`
Returns a list of all configured devices.

### List Gateways
**GET** `/api/devices/gateways`
Returns the status of all active Modbus gateways (connections).

### Read Registers
**GET** `/api/devices/{device_id}/registers`

Reads registers from a device.

**Parameters:**
-   `device_id` (path): The ID of the device.
-   `address` (query): Starting register address (0-based).
-   `count` (query): Number of registers to read (default: 1).
-   `register_type` (query): Type of register (`holding`, `input`, `coil`, `discrete`). Default: `holding`.
-   `source` (query): `live` or `cache`. Default: `live`.

**Example:**
`GET /api/devices/sensor-01/registers?address=10&count=2`

### Write Register
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
