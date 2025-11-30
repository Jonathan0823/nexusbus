# Cache Inspection Guide

## 📚 How to Check Cached Data

There are several ways to check the data currently stored in the cache:

---

## 1. **Method 1: Read with `source=cache`** (Existing)

The simplest way is to use the existing endpoint with the `source=cache` parameter:

```bash
# Get cached data for office-eng
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

**Response (if found in cache)**:
```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "source": "cache",               // ← From cache!
  "cached_at": "2025-11-30T09:05:30.123456+00:00"  // ← Polling timestamp
}
```

**Response (if NOT found in cache)**:
```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "source": "live"  // ← Fallback to live read (directly from device)
}
```

**Tip**: Look at the `source` and `cached_at` fields to know if the data is from cache or live!

---

## 2. **Method 2: Inspect All Cache** (New! ✨)

New endpoint to view **all** data currently in the cache:

```bash
curl http://localhost:8000/api/admin/cache
```

**Response**:
```json
[
  {
    "key": "office-eng:holding:0:10",
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
    "cached_at": "2025-11-30T09:05:30.123456+00:00",
    "age_seconds": 12.5  // ← Cache age (seconds)
  },
  {
    "key": "office-eng:holding:100:5",
    "device_id": "office-eng",
    "register_type": "holding",
    "address": 100,
    "count": 5,
    "values": [50, 60, 70, 80, 90],
    "cached_at": "2025-11-30T09:05:35.456789+00:00",
    "age_seconds": 7.2
  }
]
```

---

## 3. **Method 3: Cache Stats** (New! ✨)

Get cache statistics:

```bash
curl http://localhost:8000/api/admin/cache/stats
```

**Response**:
```json
{
  "total_entries": 2,
  "devices": ["office-eng", "formation"],
  "oldest_entry": "2025-11-30T09:05:30.123456+00:00",
  "newest_entry": "2025-11-30T09:05:35.456789+00:00",
  "cache_keys": [
    "office-eng:holding:0:10",
    "office-eng:holding:100:5"
  ]
}
```

**Useful for**:
- Checking how many entries are in the cache
- Checking which devices are in the cache
- Checking when the cache was last updated

---

## 4. **Method 4: Inspect Device Cache** (New! ✨)

View all cache entries for a specific device:

```bash
curl http://localhost:8000/api/admin/cache/device/office-eng
```

**Response**:
```json
[
  {
    "key": "office-eng:holding:0:10",
    "register_type": "holding",
    "address": 0,
    "count": 10,
    "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
    "cached_at": "2025-11-30T09:05:30.123456+00:00"
  },
  {
    "key": "office-eng:holding:100:5",
    "register_type": "holding",
    "address": 100,
    "count": 5,
    "values": [50, 60, 70, 80, 90],
    "cached_at": "2025-11-30T09:05:35.456789+00:00"
  }
]
```

---

## 5. **Method 5: Clear Cache** (New! ✨)

Clear all cache (useful for testing):

```bash
curl -X DELETE http://localhost:8000/api/admin/cache
```

**Response**:
```json
{
  "status": "ok",
  "message": "Cleared 2 cache entries"
}
```

**Warning**: After clearing, the next polling cycle will populate the cache again.

---

## 📊 New API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/cache` | Inspect all cache entries |
| GET | `/api/admin/cache/stats` | Get cache statistics |
| GET | `/api/admin/cache/device/{device_id}` | Inspect cache for specific device |
| DELETE | `/api/admin/cache` | Clear all cache |

**All available in Swagger UI**: http://localhost:8000/docs

---

## 🧪 Testing Cache Updates

### Step 1: Start app with polling
```bash
uvicorn main:app --reload
```

### Step 2: Wait 5-10 seconds for polling to populate cache

### Step 3: Check cache
```bash
curl http://localhost:8000/api/admin/cache/stats
```

Expected:
```json
{
  "total_entries": 2,  // ← Data exists!
  "devices": ["office-eng", "formation"],
  ...
}
```

### Step 4: Get cached data
```bash
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

Check `source` field:
- `"source": "cache"` ✅ Cache working!
- `"source": "live"` ❌ Not cached yet

### Step 5: Monitor updates

Wait 5 seconds, check `cached_at` timestamp changes:
```bash
# First check
curl http://localhost:8000/api/admin/cache | jq '.[0].cached_at'
# Output: "2025-11-30T09:05:30.123456+00:00"

# Wait 5 seconds...

# Second check
curl http://localhost:8000/api/admin/cache | jq '.[0].cached_at'
# Output: "2025-11-30T09:05:35.123456+00:00"  ← Updated!
```

---

## 🎯 Quick Commands

```bash
# Check if cache is working
curl http://localhost:8000/api/admin/cache/stats | jq '.total_entries'

# View all cache
curl http://localhost:8000/api/admin/cache | jq

# View specific device
curl http://localhost:8000/api/admin/cache/device/office-eng | jq

# Get cached data (with timestamp)
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache" | jq '{source, cached_at, values}'

# Clear cache (for testing)
curl -X DELETE http://localhost:8000/api/admin/cache
```

---

## 💡 Tips

1. **Check `source` field** to know if data is from cache or live
2. **Check `cached_at` timestamp** to know when it was last updated
3. **Check `age_seconds`** to know how old the cache data is
4. **Use `/stats` endpoint** for a quick overview
5. **Use `source=cache`** in production for fast response

---

## 🐛 Troubleshooting

### Cache empty / no data

**Check:**
```bash
curl http://localhost:8000/api/admin/cache/stats
```

If `total_entries: 0`:
1. ✅ Are polling targets configured?
   ```bash
   curl http://localhost:8000/api/admin/polling/active
   ```
2. ✅ Is the polling service running?
   - Check logs for "Polling X target(s)..."
3. ✅ Is polling successful?
   - Check logs for "✓ Polled ..." or "✗ Poll failed"

### Cache not updating

**Check timestamps:**
```bash
curl http://localhost:8000/api/admin/cache | jq '.[].cached_at'
```

If timestamps stuck (not changing every 5 seconds):
1. ✅ Check logs for polling errors
2. ✅ Check device connectivity
3. ✅ Check `max_retries` setting (should be 1 for shared gateway)

### `source: live` instead of `cache`

**Possible reasons:**
1. Cache key mismatch:
   - Request: `address=0, count=10`
   - Cached: `address=0, count=5` ← Different count!
2. No polling target for that combination of device+register+address+count
3. Cache expired / cleared

**Solution:**
Check what is in the cache:
```bash
curl http://localhost:8000/api/admin/cache/device/office-eng
```

Match address & count with your request.

---

**Now you can monitor the cache easily!** 🎉