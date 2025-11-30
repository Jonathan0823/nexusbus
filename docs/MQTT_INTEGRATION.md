# MQTT Integration Guide 📡

Modbus Middleware supports optional MQTT integration to publish polled data to an MQTT broker in real-time. This is useful for historical data logging, integration with IoT platforms (e.g., ThingsBoard, Home Assistant), or other external systems.

## 📋 Overview

When enabled, the polling service will publish data to a configured MQTT topic immediately after a successful polling cycle. This allows for "fire-and-forget" real-time data streaming without polling the REST API.

### Features
- **Real-time Publishing**: Data is sent immediately after it is read from the device.
- **Non-blocking**: MQTT publishing happens in the background and does not delay the polling loop.
- **Automatic Reconnection**: The client handles connection drops automatically.
- **Structured Topics**: Topics are organized by device and register type for easy subscription.

---

## ⚙️ Configuration

MQTT support is **disabled by default**. To enable it, configure the following variables in your `.env` file:

```ini
# MQTT Configuration
# Leave MQTT_BROKER_HOST empty to disable MQTT support
MQTT_BROKER_HOST=localhost      # Broker hostname or IP
MQTT_BROKER_PORT=1883           # Default: 1883
MQTT_USERNAME=my_user           # Optional
MQTT_PASSWORD=my_password       # Optional
MQTT_TOPIC_PREFIX=modbus/data   # Default: modbus/data
```

### Configuration Parameters

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MQTT_BROKER_HOST` | Hostname or IP of your MQTT broker. Required to enable MQTT. | `None` |
| `MQTT_BROKER_PORT` | Port number of the MQTT broker. | `1883` |
| `MQTT_USERNAME` | Username for MQTT authentication. | `None` |
| `MQTT_PASSWORD` | Password for MQTT authentication. | `None` |
| `MQTT_TOPIC_PREFIX` | Base string prepended to all topics. | `modbus/data` |

---

## 📦 Dependencies

The MQTT functionality relies on the `gmqtt` library.

This is already included in `requirements.txt`. If you need to install it manually:

```bash
pip install gmqtt
```

---

## 📡 Topic Structure

Data is published to topics following this hierarchy:

```
{prefix}/{device_id}/{register_type}/{address}
```

### Components
- **{prefix}**: Configured via `MQTT_TOPIC_PREFIX` (default: `modbus/data`).
- **{device_id}**: Unique ID of the Modbus device (e.g., `office-eng`).
- **{register_type}**: Type of register (`holding`, `input`, `coil`, `discrete`).
- **{address}**: Starting address of the read operation.

### Examples
- `modbus/data/office-eng/holding/0`
- `modbus/data/formation/input/100`
- `factory/floor1/machine-A/coil/10` (if prefix is `factory/floor1`)

---

## 📄 Payload Format

The payload is a JSON object containing the values and metadata.

```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "timestamp": 1732935600.123456
}
```

### Fields
- **device_id** *(string)*: ID of the source device.
- **register_type** *(string)*: Type of register polled.
- **address** *(integer)*: Starting address.
- **count** *(integer)*: Number of registers read.
- **values** *(array)*: List of values read.
- **timestamp** *(float)*: Unix timestamp of the poll event.

---

## 🧪 Testing & Verification

### 1. Using `mosquitto_sub` (CLI)

If you have the Mosquitto clients installed, you can verify the data stream easily.

**Subscribe to everything:**
```bash
mosquitto_sub -h localhost -t "modbus/data/#" -v
```

**Subscribe to a specific device:**
```bash
mosquitto_sub -h localhost -t "modbus/data/office-eng/#" -v
```

### 2. Using Python

You can use a simple Python script to verify subscriptions.

```python
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("modbus/data/#")

def on_message(client, userdata, msg):
    print(f"{msg.topic} {str(msg.payload)}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
client.loop_forever()
```

---

## 💡 Integration Tips

### Home Assistant
You can map these topics to Home Assistant sensors.

```yaml
mqtt:
  sensor:
    - name: "Office Temperature"
      state_topic: "modbus/data/office-eng/holding/0"
      value_template: "{{ value_json.values[0] / 10.0 }}"
      unit_of_measurement: "°C"
```

### ThingsBoard
ThingsBoard Gateway can be configured to subscribe to these topics and map them to device telemetry.

---

## 🔧 Troubleshooting

### "gmqtt library not found"
- Ensure `gmqtt` is installed: `pip install gmqtt`
- If using the provided virtual environment, it should be installed automatically via `requirements.txt`.

### No Data Appearing
1.  **Check Environment**: Verify `MQTT_BROKER_HOST` is set in `.env`.
2.  **Check Logs**: Look for "Connected to MQTT Broker" in the application startup logs.
3.  **Broker Status**: Verify your broker is running (e.g., `systemctl status mosquitto`).
4.  **Polling Status**: MQTT messages are only sent when polling happens. Ensure you have active polling targets (`/api/admin/polling/active`).
5.  **Firewall**: Ensure port 1883 (or your configured port) is open.

### Connection Refused
- Check if the broker requires authentication (`MQTT_USERNAME`/`MQTT_PASSWORD`).
- Verify the port number.