"""API routes for exposing application metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.metrics import metrics_collector

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics(request: Request) -> dict:
    """Get all application metrics.
    
    Returns comprehensive metrics including:
    - Modbus operation statistics (requests, success rate, latency)
    - Cache statistics (hits, misses, hit rate)
    - Polling statistics (cycles, success rate, duration)
    - Application uptime
    
    Example response:
    {
        "uptime_seconds": 3600,
        "modbus": {
            "total_requests": 1000,
            "successful_requests": 950,
            "failed_requests": 50,
            "success_rate_percent": 95.0,
            "average_latency_ms": 12.5,
            "requests_by_type": {"holding": 500, "input": 300, ...},
            "errors_by_type": {"holding": 20, ...}
        },
        "cache": {
            "hits": 800,
            "misses": 200,
            "sets": 1000,
            "evictions": 10,
            "hit_rate_percent": 80.0
        },
        "polling": {
            "total_cycles": 120,
            "successful_cycles": 115,
            "failed_cycles": 5,
            "total_targets_polled": 1200,
            "total_targets_success": 1150,
            "total_targets_failed": 50,
            "success_rate_percent": 95.83,
            "average_cycle_duration_ms": 250.5,
            "last_cycle_time": "2025-01-XX..."
        }
    }
    """
    return metrics_collector.get_all_metrics()


@router.post("/reset")
async def reset_metrics(request: Request) -> dict:
    """Reset all metrics (useful for testing or starting fresh).
    
    ⚠️ Warning: This will reset all collected metrics. Use with caution.
    """
    metrics_collector.reset()
    return {
        "status": "ok",
        "message": "All metrics have been reset",
    }

