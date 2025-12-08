"""Unit tests for Circuit Breaker pattern.

Tests state transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
"""

import pytest
from unittest.mock import AsyncMock

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def config():
    """Quick-failing config for tests."""
    return CircuitBreakerConfig(
        failure_threshold=3,      # Open after 3 failures
        recovery_timeout=0.1,     # 100ms cooldown for fast tests
        success_threshold=1,      # 1 success to close
    )


@pytest.fixture
def breaker(config):
    """Fresh circuit breaker instance."""
    return CircuitBreaker(device_id="test-device", config=config)


# ============================================================
# State Transition Tests
# ============================================================

@pytest.mark.asyncio
async def test_initial_state_is_closed(breaker):
    """Circuit starts in CLOSED state."""
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_success_keeps_closed(breaker):
    """Successful calls keep circuit CLOSED."""
    mock_func = AsyncMock(return_value="ok")
    
    result = await breaker.call(mock_func)
    
    assert result == "ok"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_failure_increments_count(breaker):
    """Failures increment counter but stay CLOSED."""
    mock_func = AsyncMock(side_effect=Exception("Device offline"))
    
    # First failure
    with pytest.raises(Exception, match="Device offline"):
        await breaker.call(mock_func)
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 1


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold(breaker):
    """Circuit opens after failure_threshold failures."""
    mock_func = AsyncMock(side_effect=Exception("Device offline"))
    
    # 3 failures (threshold)
    for _ in range(3):
        with pytest.raises(Exception, match="Device offline"):
            await breaker.call(mock_func)
    
    # Circuit should be OPEN now
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


@pytest.mark.asyncio
async def test_open_circuit_rejects_immediately(breaker):
    """OPEN circuit rejects calls with CircuitOpenError."""
    mock_func = AsyncMock(side_effect=Exception("Device offline"))
    
    # Open the circuit
    for _ in range(3):
        with pytest.raises(Exception):
            await breaker.call(mock_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Next call should be rejected immediately (not call the func)
    mock_func.reset_mock()
    with pytest.raises(CircuitOpenError) as exc_info:
        await breaker.call(mock_func)
    
    assert exc_info.value.device_id == "test-device"
    assert exc_info.value.time_until_retry > 0
    mock_func.assert_not_called()  # Function was NOT called!


@pytest.mark.asyncio
async def test_circuit_half_open_after_timeout(breaker):
    """Circuit transitions to HALF_OPEN after recovery timeout."""
    import asyncio
    
    mock_func = AsyncMock(side_effect=Exception("Device offline"))
    
    # Open the circuit
    for _ in range(3):
        with pytest.raises(Exception):
            await breaker.call(mock_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for recovery timeout (100ms)
    await asyncio.sleep(0.15)
    
    # Next call should attempt (HALF_OPEN transition)
    mock_func.reset_mock()
    with pytest.raises(Exception):
        await breaker.call(mock_func)
    
    # State should be OPEN again (failed recovery)
    assert breaker.state == CircuitState.OPEN
    mock_func.assert_called_once()  # Function WAS called this time


@pytest.mark.asyncio
async def test_circuit_closes_on_recovery_success(breaker):
    """Circuit closes after successful call in HALF_OPEN state."""
    import asyncio
    
    # Mock: fail 3x, then succeed
    mock_func = AsyncMock(side_effect=[
        Exception("fail"),
        Exception("fail"),
        Exception("fail"),
        "success!",
    ])
    
    # Open the circuit
    for _ in range(3):
        with pytest.raises(Exception):
            await breaker.call(mock_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for recovery timeout
    await asyncio.sleep(0.15)
    
    # Successful recovery call
    result = await breaker.call(mock_func)
    
    assert result == "success!"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_success_resets_failure_count(breaker):
    """Success in CLOSED state resets failure count."""
    fail_func = AsyncMock(side_effect=Exception("fail"))
    success_func = AsyncMock(return_value="ok")
    
    # 2 failures (below threshold)
    for _ in range(2):
        with pytest.raises(Exception):
            await breaker.call(fail_func)
    
    assert breaker.failure_count == 2
    
    # 1 success should reset
    await breaker.call(success_func)
    
    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_manual_reset(breaker):
    """Manual reset returns circuit to CLOSED."""
    mock_func = AsyncMock(side_effect=Exception("fail"))
    
    # Open the circuit
    for _ in range(3):
        with pytest.raises(Exception):
            await breaker.call(mock_func)
    
    assert breaker.state == CircuitState.OPEN
    
    # Manual reset
    breaker.reset()
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


# ============================================================
# Registry Tests
# ============================================================

@pytest.mark.asyncio
async def test_registry_creates_breakers():
    """Registry creates breakers for new devices."""
    registry = CircuitBreakerRegistry()
    
    breaker1 = await registry.get_or_create("device-1")
    breaker2 = await registry.get_or_create("device-2")
    
    assert breaker1.device_id == "device-1"
    assert breaker2.device_id == "device-2"
    assert breaker1 is not breaker2


@pytest.mark.asyncio
async def test_registry_reuses_breakers():
    """Registry returns same breaker for same device."""
    registry = CircuitBreakerRegistry()
    
    breaker1 = await registry.get_or_create("device-1")
    breaker2 = await registry.get_or_create("device-1")
    
    assert breaker1 is breaker2


@pytest.mark.asyncio
async def test_registry_independent_circuits():
    """Each device has independent circuit state."""
    config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=10)
    registry = CircuitBreakerRegistry(default_config=config)
    
    breaker1 = await registry.get_or_create("device-1")
    breaker2 = await registry.get_or_create("device-2")
    
    # Fail device-1 twice to open its circuit
    fail_func = AsyncMock(side_effect=Exception("fail"))
    for _ in range(2):
        with pytest.raises(Exception):
            await breaker1.call(fail_func)
    
    assert breaker1.state == CircuitState.OPEN
    assert breaker2.state == CircuitState.CLOSED  # Independent!
