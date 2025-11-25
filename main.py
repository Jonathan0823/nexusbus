from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as devices_router
from app.api.admin_routes import router as admin_router
from app.config.devices import (
    DEFAULT_POLL_TARGETS,
    DEVICE_CONFIGS,
    POLL_INTERVAL_SECONDS,
    load_device_configs,
)
from app.core.cache import RegisterCache
from app.core.modbus_client import ModbusClientManager
from app.services.poller import poll_registers
from app.database.connection import create_db_and_tables, close_db, async_session_maker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Modbus Middleware", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(devices_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting Modbus middleware service")
    
    # Initialize database
    try:
        logger.info("Creating database tables...")
        await create_db_and_tables()
        logger.info("Database initialized")
        
        # Load devices from database
        async with async_session_maker() as session:
            device_configs = await load_device_configs(session)
        logger.info(f"Loaded {len(device_configs)} device(s) from database")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}. Using hardcoded configs.")
        device_configs = DEVICE_CONFIGS
    
    # Initialize Modbus manager with loaded configs
    app.state.modbus_manager = ModbusClientManager(device_configs)
    app.state.register_cache = RegisterCache()

    if DEFAULT_POLL_TARGETS:
        logger.info(
            "Starting polling task with %s target(s) every %ss",
            len(DEFAULT_POLL_TARGETS),
            POLL_INTERVAL_SECONDS,
        )
        app.state.poller_task = asyncio.create_task(
            poll_registers(
                manager=app.state.modbus_manager,
                cache=app.state.register_cache,
                targets=DEFAULT_POLL_TARGETS,
                interval_seconds=POLL_INTERVAL_SECONDS,
            ),
            name="modbus-poller",
        )
    else:
        app.state.poller_task = None


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("Shutting down Modbus middleware service")
    poller_task = getattr(app.state, "poller_task", None)
    if poller_task:
        poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await poller_task

    manager: ModbusClientManager = app.state.modbus_manager
    await manager.close_all()
    cache: RegisterCache = app.state.register_cache
    await cache.clear()
    
    # Close database connections
    await close_db()
    logger.info("Database connections closed")


@app.get("/health", tags=["system"])
async def healthcheck() -> dict:
    return {"status": "ok"}

