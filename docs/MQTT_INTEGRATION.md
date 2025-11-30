# MQTT Integration Guide 📡

Modbus Middleware supports optional MQTT integration to publish polled data to an MQTT broker in real-time. This is useful for historical data logging, integration with IoT platforms (e.g., ThingsBoard, Home Assistant), or other external systems.

## ⚙️ Configuration

MQTT support is **disabled by default**. To enable it, configure the following variables in your `.env` file:

```ini
# MQTT Configuration
# Leave MQTT_BROKER_HOST empty to disable MQTT support
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=          # Optional
MQTT_PASSWORD=          # Optional
MQTT_TOPIC_PREFIX=modbus/data
```

### Key Parameters:
- **MQTT_BROKER_HOST**: Hostname or IP of your MQTT broker (e.g., `localhost`, `192.168.1.100`).
- **MQTT_TOPIC_PREFIX**: Base prefix for all topics. Default is `modbus/data`.

---

## 📡 Topic Structure

Data is published to topics following this hierarchy:

```
{prefix}/{device_id}/{register_type}/{address}
```

### Examples:
- `modbus/data/office-eng/holding/0`
- `modbus/data/formation/input/100`

---

## 📦 Payload Format

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

- **values**: Array of integers read from the registers.
- **timestamp**: Unix timestamp of when the data was polled.

---

## 🧪 Testing with Mosquitto

You can use the `mosquitto_sub` command-line tool to verify that data is being published.

### Subscribe to All Data
```bash
mosquitto_sub -h localhost -t "modbus/data/#" -v
```

### Subscribe to Specific Device
```bash
mosquitto_sub -h localhost -t "modbus/data/office-eng/#" -v
```

---

## 💡 Behavior Notes

1.  **Fire & Forget**: The middleware publishes data asynchronously. If the MQTT broker is unreachable, it logs an error but **does not block** the polling loop.
2.  **Auto-Reconnect**: The client attempts to reconnect automatically if the connection drops (handled by `aiomqtt`).
3.  **Optional**: If `MQTT_BROKER_HOST` is not set, the MQTT module is completely skipped.

---

## 🔧 Troubleshooting
    
### "gmqtt library not found"
Ensure you have installed the required dependencies:
```bash
pip install gmqtt
```

### No Data Appearing
1.  Check if `MQTT_BROKER_HOST` is set in `.env`.
2.  Check application logs for "Connected to MQTT Broker".
3.  Verify your broker is running and accessible.
4.  Check if the polling service is actually running and polling data (look for "✓ Polled..." logs).
