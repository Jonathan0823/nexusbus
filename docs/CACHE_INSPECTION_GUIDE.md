# Cache Inspection Guide

## 📚 How to Check Cached Data

Ada beberapa cara untuk cek data yang ada di cache:

---

## 1. **Method 1: Read with `source=cache`** (Existing)

Cara paling simple - pakai endpoint existing dengan parameter `source=cache`:

```bash
# Get cached data untuk office-eng
curl "http://localhost:8000/api/devices/office-eng/registers?address=0&count=10&source=cache"
```

**Response (kalau ada di cache)**:
```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "source": "cache",               // ← Dari cache!
  "cached_at": "2025-11-30T09:05:30.123456+00:00"  // ← Timestamp polling
}
```

**Response (kalau tidak ada di cache)**:
```json
{
  "device_id": "office-eng",
  "register_type": "holding",
  "address": 0,
  "count": 10,
  "values": [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
  "source": "live"  // ← Fallback ke live read (langsung dari device)
}
```

**Tips**: Lihat field `source` dan `cached_at` untuk tau apakah dari cache atau live!

---

## 2. **Method 2: Inspect All Cache** (New! ✨)

Endpoint baru untuk lihat **semua** data yang ada di cache:

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
    "age_seconds": 12.5  // ← Umur cache (detik)
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

Get statistik cache:

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

**Useful untuk**:
- Cek berapa entry di cache
- Cek device mana aja yang ada di cache
- Cek kapan terakhir di-update

---

## 4. **Method 4: Inspect Device Cache** (New! ✨)

Lihat semua cache untuk device tertentu:

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

Hapus semua cache (useful untuk testing):

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

**Warning**: Setelah clear, polling cycle berikutnya akan populate cache lagi.

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

### Step 1: Start app dengan polling
```bash
uvicorn main:app --reload
```

### Step 2: Wait 5-10 seconds untuk polling populate cache

### Step 3: Check cache
```bash
curl http://localhost:8000/api/admin/cache/stats
```

Expected:
```json
{
  "total_entries": 2,  // ← Ada data!
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

1. **Check `source` field** untuk tau apakah dari cache atau live
2. **Check `cached_at` timestamp** untuk tau kapan terakhir di-update
3. **Check `age_seconds`** untuk tau berapa lama data di cache
4. **Use `/stats` endpoint** untuk quick overview
5. **Use `source=cache`** di production untuk fast response

---

## 🐛 Troubleshooting

### Cache kosong / tidak ada data

**Check:**
```bash
curl http://localhost:8000/api/admin/cache/stats
```

If `total_entries: 0`:
1. ✅ Apakah polling targets sudah dikonfigurasi?
   ```bash
   curl http://localhost:8000/api/admin/polling/active
   ```
2. ✅ Apakah polling service running?
   - Check logs untuk "Polling X target(s)..."
3. ✅ Apakah polling berhasil?
   - Check logs untuk "✓ Polled ..." atau "✗ Poll failed"

### Cache tidak update

**Check timestamps:**
```bash
curl http://localhost:8000/api/admin/cache | jq '.[].cached_at'
```

If timestamps stuck (tidak berubah tiap 5 detik):
1. ✅ Check logs untuk polling errors
2. ✅ Check device connectivity
3. ✅ Check `max_retries` setting (should be 1 for shared gateway)

### `source: live` instead of `cache`

**Possible reasons:**
1. Cache key tidak match:
   - Request: `address=0, count=10`
   - Cached: `address=0, count=5` ← Beda count!
2. Polling target tidak ada untuk kombinasi device+register+address+count tersebut
3. Cache expired / cleared

**Solution:**
Check apa yang ada di cache:
```bash
curl http://localhost:8000/api/admin/cache/device/office-eng
```

Match address & count dengan request Anda.

---

**Sekarang kamu bisa monitor cache dengan mudah!** 🎉
