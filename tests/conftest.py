import pytest
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from main import app

# Configure pytest-asyncio to treat all async tests as asyncio-driven
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient instance.
    Note: For complex async DB interactions, we might need AsyncClient from httpx,
    but for basic endpoint testing, TestClient works well enough for sync wrappers.
    """
    with TestClient(app) as c:
        yield c
