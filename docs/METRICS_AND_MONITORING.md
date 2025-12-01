# Metrics and Monitoring

> **Comprehensive guide to metrics collection, structured logging, and health monitoring**

**[← Main README](../README.md)** | **[Device API Guide](./DEVICE_MANAGEMENT.md)** | **[Polling Config](./POLLING_CONFIGURATION.md)**

---

## 📊 Metrics Collection

NexusBus includes built-in metrics collection for monitoring application performance and health.

### Accessing Metrics

```bash
# Get all metrics
curl http://localhost:8000/api/metrics

# Reset metrics (useful for testing)
curl -X POST http://localhost:8000/api/metrics/reset
```

### Metrics Categories

#### 1. Modbus Metrics

Tracks all Modbus operations:

```json
{
  "modbus": {
    "total_requests": 1000,
    "successful_requests": 950,
    "failed_requests": 50,
    "success_rate_percent": 95.0,
    "average_latency_ms": 12.5,
    "requests_by_type": {
      "holding": 500,
      "input": 300,
      "coil": 150,
      "discrete": 50
    },
    "errors_by_type": {
      "holding": 20,
      "input": 15
    }
  }
}
```

**Fields:**
- `total_requests`: Total number of Modbus requests
- `successful_requests`: Number of successful requests
- `failed_requests`: Number of failed requests
- `success_rate_percent`: Success rate as percentage
- `average_latency_ms`: Average request latency in milliseconds
- `requests_by_type`: Breakdown by register type
- `errors_by_type`: Error breakdown by register type

#### 2. Cache Metrics

Tracks cache performance:

```json
{
  "cache": {
    "hits": 800,
    "misses": 200,
    "sets": 1000,
    "evictions": 10,
    "hit_rate_percent": 80.0
  }
}
```

**Fields:**
- `hits`: Number of cache hits
- `misses`: Number of cache misses
- `sets`: Number of cache set operations
- `evictions`: Number of expired entries removed
- `hit_rate_percent`: Cache hit rate as percentage

#### 3. Polling Metrics

Tracks polling service performance:

```json
{
  "polling": {
    "total_cycles": 120,
    "successful_cycles": 115,
    "failed_cycles": 5,
    "total_targets_polled": 1200,
    "total_targets_success": 1150,
    "total_targets_failed": 50,
    "success_rate_percent": 95.83,
    "average_cycle_duration_ms": 250.5,
    "last_cycle_time": "2025-01-XXT10:30:45.123Z"
  }
}
```

**Fields:**
- `total_cycles`: Total number of polling cycles
- `successful_cycles`: Cycles with no failures
- `failed_cycles`: Cycles with at least one failure
- `total_targets_polled`: Total targets polled across all cycles
- `total_targets_success`: Successful target polls
- `total_targets_failed`: Failed target polls
- `success_rate_percent`: Overall success rate
- `average_cycle_duration_ms`: Average cycle duration
- `last_cycle_time`: Timestamp of last polling cycle

### Integration with Monitoring Tools

#### Prometheus

You can create a Prometheus exporter endpoint:

```python
# Example: Add to app/api/metrics_routes.py
@router.get("/prometheus")
async def prometheus_metrics():
    """Export metrics in Prometheus format."""
    metrics = metrics_collector.get_all_metrics()
    # Convert to Prometheus format
    ...
```

#### Grafana

Use the metrics endpoint to create dashboards:

1. Configure Grafana to query `/api/metrics`
2. Create visualizations for:
   - Modbus success rate over time
   - Cache hit rate trends
   - Polling cycle duration
   - Error rates by device/type

---

## 📝 Structured Logging

NexusBus uses structured logging for better observability and log aggregation.

### Configuration

Set in `.env` or environment variables:

```env
# Logging level
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Output format
LOG_JSON=false          # true for JSON (production), false for colored console (development)

# Include caller information
LOG_INCLUDE_CALLER=true # Include filename, line number, function name
```

### Log Format

#### Development Mode (Colored Console)

```
2025-01-XX 10:30:45 [info     ] polling_target_success device_id=office-eng register_type=holding address=0 count=10 values_count=10 message="Successfully polled target"
```

#### Production Mode (JSON)

```json
{
  "event": "polling_target_success",
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values_count": 10,
  "message": "Successfully polled target",
  "timestamp": "2025-01-XXT10:30:45.123Z",
  "level": "INFO",
  "logger": "app.services.poller"
}
```

### Event Types

All logs follow a consistent event naming pattern:

#### Modbus Events
- `modbus_read_success_after_retry` - Read succeeded after retries
- `modbus_read_exception` - Modbus exception during read
- `modbus_read_failed` - Read failed after all retries
- `modbus_write_exception` - Exception during write
- `modbus_gateway_reset` - Gateway connection reset
- `modbus_configs_reloaded` - Device configs reloaded

#### Polling Events
- `polling_service_started` - Polling service started
- `polling_cycle_start` - Polling cycle started
- `polling_target_success` - Target polled successfully
- `polling_target_failed` - Target poll failed
- `polling_cycle_completed` - Polling cycle completed
- `polling_service_cancelled` - Polling service cancelled

#### MQTT Events
- `mqtt_configured` - MQTT client configured
- `mqtt_connected` - Connected to MQTT broker
- `mqtt_connect_failed` - Failed to connect
- `mqtt_published` - Message published
- `mqtt_publish_failed` - Publish failed

#### Application Events
- `app_starting` - Application starting
- `app_shutting_down` - Application shutting down
- `database_initialized` - Database initialized
- `devices_loaded` - Devices loaded from database

### Log Aggregation

Structured logs are perfect for log aggregation tools:

#### ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
# Logstash configuration
input {
  file {
    path => "/var/log/nexusbus/app.log"
    codec => json
  }
}

filter {
  # Logs are already in JSON format
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "nexusbus-%{+YYYY.MM.dd}"
  }
}
```

#### Splunk

```conf
# inputs.conf
[monitor:///var/log/nexusbus]
sourcetype = nexusbus_json
```

#### Datadog

```python
# Use Datadog's log forwarder
# Logs in JSON format are automatically parsed
```

### Filtering and Searching

With structured logs, you can easily filter:

```bash
# Find all errors for a specific device
grep '"device_id":"office-eng"' app.log | grep '"level":"ERROR"'

# Find all polling failures
grep '"event":"polling_target_failed"' app.log

# Find all Modbus errors
grep '"event":"modbus.*error"' app.log
```

---

## 🏥 Health Checks

### Basic Health Check

```bash
curl http://localhost:8000/health
```

### Response Format

**Healthy (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-01-XXT10:30:45.123Z",
  "services": {
    "database": "ok",
    "mqtt": "ok",
    "modbus": "ok"
  },
  "details": {
    "database": {
      "connected": true
    },
    "mqtt": {
      "enabled": true,
      "connected": true,
      "broker": "localhost:1883"
    },
    "modbus": {
      "initialized": true,
      "total_devices": 3,
      "total_gateways": 2,
      "connected_gateways": 2,
      "gateways": [
        {
          "host": "192.168.1.10",
          "port": 502,
          "connected": true
        }
      ]
    }
  }
}
```

**Degraded (503 Service Unavailable):**
```json
{
  "status": "degraded",
  "timestamp": "2025-01-XXT10:30:45.123Z",
  "services": {
    "database": "ok",
    "mqtt": "disconnected",
    "modbus": "ok"
  },
  "details": {
    "mqtt": {
      "enabled": true,
      "connected": false,
      "broker": "localhost:1883"
    }
  }
}
```

### Service Status Values

- `ok`: Service is healthy
- `error`: Service has an error
- `disconnected`: Service is disconnected (MQTT)
- `disabled`: Service is disabled (MQTT)
- `warning`: Service has warnings (Modbus - no gateways connected yet)

### Using Health Checks

#### Kubernetes Liveness/Readiness Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

#### Docker Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s \
  CMD curl -f http://localhost:8000/health || exit 1
```

#### Monitoring Alerts

```yaml
# Prometheus alert rule
groups:
  - name: nexusbus
    rules:
      - alert: NexusBusDegraded
        expr: up{job="nexusbus"} == 0 OR http_health_status{job="nexusbus"} != 200
        for: 1m
        annotations:
          summary: "NexusBus service is degraded"
```

---

## 🔍 Best Practices

### 1. Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages (non-critical issues)
- **ERROR**: Error messages (operations failed)
- **CRITICAL**: Critical errors (application may not function)

### 2. Log Retention

For production, configure log rotation:

```bash
# Use logrotate
/var/log/nexusbus/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 app app
}
```

### 3. Metrics Retention

Metrics are in-memory and reset on restart. For long-term retention:

- Export to Prometheus
- Store in time-series database (InfluxDB, TimescaleDB)
- Send to monitoring service (Datadog, New Relic)

### 4. Alerting

Set up alerts for:

- High error rates (`modbus.failed_requests > threshold`)
- Low cache hit rate (`cache.hit_rate_percent < 50`)
- Slow polling cycles (`polling.average_cycle_duration_ms > threshold`)
- Health check failures (`health.status != "ok"`)

---

## 📚 Related Documentation

- [Device Management](./DEVICE_MANAGEMENT.md)
- [Polling Configuration](./POLLING_CONFIGURATION.md)
- [MQTT Integration](./MQTT_INTEGRATION.md)
- [Cache Inspection Guide](./CACHE_INSPECTION_GUIDE.md)

