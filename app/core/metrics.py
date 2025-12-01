"""Metrics collection for monitoring application performance."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict

from app.core.modbus_client import RegisterType


@dataclass
class ModbusMetrics:
    """Metrics for Modbus operations."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    requests_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def record_request(
        self,
        register_type: RegisterType,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a Modbus request."""
        self.total_requests += 1
        type_key = register_type.value
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.errors_by_type[type_key] += 1
        
        self.requests_by_type[type_key] += 1
        self.total_latency_ms += latency_ms
    
    def get_average_latency_ms(self) -> float:
        """Get average request latency in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage (0-100)."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0


@dataclass
class CacheMetrics:
    """Metrics for cache operations."""
    
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
    
    def record_set(self) -> None:
        """Record a cache set operation."""
        self.sets += 1
    
    def record_eviction(self) -> None:
        """Record a cache eviction."""
        self.evictions += 1
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate as percentage (0-100)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100.0


@dataclass
class PollingMetrics:
    """Metrics for polling operations."""
    
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    total_targets_polled: int = 0
    total_targets_success: int = 0
    total_targets_failed: int = 0
    total_cycle_duration_ms: float = 0.0
    last_cycle_time: datetime | None = None
    
    def record_cycle(
        self,
        success_count: int,
        failure_count: int,
        duration_ms: float,
    ) -> None:
        """Record a polling cycle."""
        self.total_cycles += 1
        self.total_targets_polled += success_count + failure_count
        self.total_targets_success += success_count
        self.total_targets_failed += failure_count
        self.total_cycle_duration_ms += duration_ms
        self.last_cycle_time = datetime.now(timezone.utc)
        
        if failure_count == 0:
            self.successful_cycles += 1
        else:
            self.failed_cycles += 1
    
    def get_average_cycle_duration_ms(self) -> float:
        """Get average polling cycle duration in milliseconds."""
        if self.total_cycles == 0:
            return 0.0
        return self.total_cycle_duration_ms / self.total_cycles
    
    def get_success_rate(self) -> float:
        """Get polling success rate as percentage (0-100)."""
        if self.total_targets_polled == 0:
            return 100.0
        return (self.total_targets_success / self.total_targets_polled) * 100.0


class MetricsCollector:
    """Central metrics collector for the application."""
    
    def __init__(self) -> None:
        self.modbus = ModbusMetrics()
        self.cache = CacheMetrics()
        self.polling = PollingMetrics()
        self.start_time = datetime.now(timezone.utc)
    
    def get_all_metrics(self) -> Dict:
        """Get all collected metrics as a dictionary."""
        return {
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "modbus": {
                "total_requests": self.modbus.total_requests,
                "successful_requests": self.modbus.successful_requests,
                "failed_requests": self.modbus.failed_requests,
                "success_rate_percent": round(self.modbus.get_success_rate(), 2),
                "average_latency_ms": round(self.modbus.get_average_latency_ms(), 2),
                "requests_by_type": dict(self.modbus.requests_by_type),
                "errors_by_type": dict(self.modbus.errors_by_type),
            },
            "cache": {
                "hits": self.cache.hits,
                "misses": self.cache.misses,
                "sets": self.cache.sets,
                "evictions": self.cache.evictions,
                "hit_rate_percent": round(self.cache.get_hit_rate(), 2),
            },
            "polling": {
                "total_cycles": self.polling.total_cycles,
                "successful_cycles": self.polling.successful_cycles,
                "failed_cycles": self.polling.failed_cycles,
                "total_targets_polled": self.polling.total_targets_polled,
                "total_targets_success": self.polling.total_targets_success,
                "total_targets_failed": self.polling.total_targets_failed,
                "success_rate_percent": round(self.polling.get_success_rate(), 2),
                "average_cycle_duration_ms": round(self.polling.get_average_cycle_duration_ms(), 2),
                "last_cycle_time": (
                    self.polling.last_cycle_time.isoformat()
                    if self.polling.last_cycle_time
                    else None
                ),
            },
        }
    
    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.modbus = ModbusMetrics()
        self.cache = CacheMetrics()
        self.polling = PollingMetrics()
        self.start_time = datetime.now(timezone.utc)


# Global metrics instance
metrics_collector = MetricsCollector()

