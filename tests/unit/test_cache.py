"""Unit tests for RegisterCache."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.cache import RegisterCache, CachedEntry
from app.core.modbus_client import RegisterType


# ============================================================
# CachedEntry Tests
# ============================================================

def test_cached_entry_not_expired():
    """Entry should not be expired when within TTL."""
    entry = CachedEntry(
        device_id="test",
        register_type=RegisterType.HOLDING,
        address=0,
        count=1,
        data=[100],
        timestamp=datetime.now(timezone.utc),
        ttl_seconds=300,
    )
    assert entry.is_expired() is False


def test_cached_entry_expired():
    """Entry should be expired when past TTL."""
    old_time = datetime.now(timezone.utc) - timedelta(seconds=400)
    entry = CachedEntry(
        device_id="test",
        register_type=RegisterType.HOLDING,
        address=0,
        count=1,
        data=[100],
        timestamp=old_time,
        ttl_seconds=300,
    )
    assert entry.is_expired() is True


# ============================================================
# RegisterCache Tests
# ============================================================

@pytest.fixture
def mock_metrics():
    """Mock metrics collector for all cache tests."""
    mock = MagicMock()
    mock.cache = MagicMock()
    mock.cache.record_set = MagicMock()
    mock.cache.record_hit = MagicMock()
    mock.cache.record_miss = MagicMock()
    mock.cache.record_eviction = MagicMock()
    return mock


@pytest.fixture
def cache():
    """Fresh cache for each test."""
    return RegisterCache(default_ttl_seconds=60)


@pytest.mark.asyncio
async def test_cache_set_and_get(cache, mock_metrics):
    """Test basic set and get operations."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        
        entry = await cache.get("device-1", RegisterType.HOLDING, 0, 10)
        
        assert entry is not None
        assert entry.data == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert entry.device_id == "device-1"


@pytest.mark.asyncio
async def test_cache_get_missing(cache, mock_metrics):
    """Test get returns None for missing entries."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        entry = await cache.get("nonexistent", RegisterType.HOLDING, 0, 1)
        assert entry is None


@pytest.mark.asyncio
async def test_cache_different_keys(cache, mock_metrics):
    """Test different cache keys are independent."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100])
        await cache.set("device-1", RegisterType.INPUT, 0, 1, [200])
        await cache.set("device-2", RegisterType.HOLDING, 0, 1, [300])
        
        entry1 = await cache.get("device-1", RegisterType.HOLDING, 0, 1)
        entry2 = await cache.get("device-1", RegisterType.INPUT, 0, 1)
        entry3 = await cache.get("device-2", RegisterType.HOLDING, 0, 1)
        
        assert entry1.data == [100]
        assert entry2.data == [200]
        assert entry3.data == [300]


@pytest.mark.asyncio
async def test_cache_clear(cache, mock_metrics):
    """Test clearing all cache entries."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100])
        await cache.set("device-2", RegisterType.HOLDING, 0, 1, [200])
        
        await cache.clear()
        
        entry1 = await cache.get("device-1", RegisterType.HOLDING, 0, 1)
        entry2 = await cache.get("device-2", RegisterType.HOLDING, 0, 1)
        
        assert entry1 is None
        assert entry2 is None


@pytest.mark.asyncio
async def test_cache_get_stats(cache, mock_metrics):
    """Test cache statistics."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100])
        await cache.set("device-2", RegisterType.HOLDING, 0, 1, [200])
        
        stats = await cache.get_stats()
        
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert stats["expired_entries"] == 0


@pytest.mark.asyncio
async def test_cache_cleanup_expired(cache, mock_metrics):
    """Test cleanup of expired entries."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        # Add entry then manually set it as expired by backdating timestamp
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100], ttl_seconds=1)
        
        # Manually make it expired by backdating the timestamp
        key = cache._key("device-1", RegisterType.HOLDING, 0, 1)
        cache._store[key].timestamp = datetime.now(timezone.utc) - timedelta(seconds=10)
        
        # Cleanup should remove it
        removed = await cache.cleanup_expired()
        
        assert removed == 1


@pytest.mark.asyncio
async def test_cache_custom_ttl(cache, mock_metrics):
    """Test custom TTL per entry."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100], ttl_seconds=3600)
        
        entry = await cache.get("device-1", RegisterType.HOLDING, 0, 1)
        
        assert entry is not None
        assert entry.ttl_seconds == 3600


@pytest.mark.asyncio
async def test_cache_overwrites_existing(cache, mock_metrics):
    """Test that set overwrites existing entry."""
    with patch("app.core.metrics.metrics_collector", mock_metrics):
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [100])
        await cache.set("device-1", RegisterType.HOLDING, 0, 1, [999])
        
        entry = await cache.get("device-1", RegisterType.HOLDING, 0, 1)
        
        assert entry.data == [999]
