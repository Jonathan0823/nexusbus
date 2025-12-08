"""Circuit Breaker pattern implementation for Modbus connections.

Prevents cascading failures when Modbus devices are offline by failing fast
after repeated failures, then gradually testing recovery.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from app.core.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit tripped, reject all requests
    HALF_OPEN = "half_open"  # Testing recovery with single request


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""
    
    def __init__(self, device_id: str, time_until_retry: float):
        self.device_id = device_id
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit breaker OPEN for device '{device_id}'. "
            f"Retry in {time_until_retry:.1f}s"
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: float = 30.0  # Seconds to wait before half-open
    success_threshold: int = 1  # Successes needed in half-open to close


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single device/endpoint.
    
    States:
    - CLOSED: Normal operation. Failures increment counter.
    - OPEN: After failure_threshold reached. All calls rejected immediately.
    - HALF_OPEN: After recovery_timeout expires. One test call allowed.
    
    Usage:
        breaker = CircuitBreaker("device-1", config)
        result = await breaker.call(some_async_func, arg1, arg2)
    """
    
    device_id: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    
    # State tracking
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self._failure_count
    
    def _time_until_retry(self) -> float:
        """Seconds until circuit can transition to half-open."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        remaining = self.config.recovery_timeout - elapsed
        return max(0.0, remaining)
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._state != CircuitState.OPEN:
            return False
        return self._time_until_retry() <= 0
    
    def _record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info(
                    "circuit_breaker_closed",
                    device_id=self.device_id,
                    message="Circuit breaker closed after successful recovery",
                )
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def _record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._success_count = 0
        
        if self._state == CircuitState.HALF_OPEN:
            # Failed during recovery test, go back to open
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker_reopened",
                device_id=self.device_id,
                message="Circuit breaker reopened after failed recovery attempt",
            )
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    device_id=self.device_id,
                    failure_count=self._failure_count,
                    recovery_timeout=self.config.recovery_timeout,
                    message="Circuit breaker opened after repeated failures",
                )
    
    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitOpenError: If circuit is open and not ready for retry
            Exception: Any exception from func (also recorded as failure)
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "circuit_breaker_half_open",
                        device_id=self.device_id,
                        message="Circuit breaker entering half-open state for recovery test",
                    )
                else:
                    # Still in cooldown, reject immediately
                    raise CircuitOpenError(self.device_id, self._time_until_retry())
        
        # Execute the function outside the lock to avoid blocking
        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self._record_success()
            return result
        except Exception as e:
            async with self._lock:
                self._record_failure()
            raise
    
    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        logger.info(
            "circuit_breaker_reset",
            device_id=self.device_id,
            message="Circuit breaker manually reset",
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "device_id": self.device_id,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "time_until_retry": self._time_until_retry() if self._state == CircuitState.OPEN else None,
        }


class CircuitBreakerRegistry:
    """Manages circuit breakers for multiple devices."""
    
    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = default_config or CircuitBreakerConfig()
        self._lock = asyncio.Lock()
    
    async def get_or_create(self, device_id: str) -> CircuitBreaker:
        """Get existing circuit breaker or create new one for device."""
        async with self._lock:
            if device_id not in self._breakers:
                self._breakers[device_id] = CircuitBreaker(
                    device_id=device_id,
                    config=self._default_config,
                )
            return self._breakers[device_id]
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            device_id: breaker.get_status()
            for device_id, breaker in self._breakers.items()
        }
    
    async def reset(self, device_id: str) -> bool:
        """Reset circuit breaker for a device."""
        async with self._lock:
            if device_id in self._breakers:
                self._breakers[device_id].reset()
                return True
            return False
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
