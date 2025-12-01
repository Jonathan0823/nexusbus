from __future__ import annotations

import asyncio
import logging
from contextlib import suppress, asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as devices_router
from app.api.admin_routes import router as admin_router
from app.api.polling_routes import router as polling_router
from app.api.cache_routes import router as cache_router
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

from app.core.mqtt_client import mqtt_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown logic.
    """
    # --- STARTUP LOGIC ---
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

    # Start MQTT Client
    await mqtt_manager.start()
    app.state.mqtt_manager = mqtt_manager

    # Start polling task (now loads targets from database automatically)
    logger.info("Starting polling service (loading targets from database)")
    app.state.poller_task = asyncio.create_task(
        poll_registers(
            manager=app.state.modbus_manager,
            cache=app.state.register_cache,
            interval_seconds=POLL_INTERVAL_SECONDS,
            use_database=True,  # Use database for polling targets
            fallback_targets=DEFAULT_POLL_TARGETS,  # Fallback if DB is empty
            mqtt_manager=app.state.mqtt_manager,
        ),
        name="modbus-poller",
    )

    yield  # Application is running...

    # --- SHUTDOWN LOGIC ---
    logger.info("Shutting down Modbus middleware service")
    poller_task = getattr(app.state, "poller_task", None)
    if poller_task:
        poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await poller_task

    manager: ModbusClientManager = app.state.modbus_manager
    await manager.close_all()

    # Stop MQTT Client
    mqtt_manager_inst = getattr(app.state, "mqtt_manager", None)
    if mqtt_manager_inst:
        await mqtt_manager_inst.stop()

    cache: RegisterCache = app.state.register_cache
    await cache.clear()

    # Close database connections
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(title="Modbus Middleware", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(devices_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(polling_router, prefix="/api")
app.include_router(cache_router, prefix="/api")


@app.get("/health", tags=["system"])
async def healthcheck(
    request: Request,
) -> dict:
    """Comprehensive health check endpoint.

    Checks:
    - Application status
    - Database connectivity
    - MQTT connection status
    - Modbus gateway status

    Returns:
        - 200: All services healthy
        - 503: One or more services degraded
    """
    from sqlalchemy import select
    from app.database.connection import async_session_maker
    from fastapi import status
    from fastapi.responses import JSONResponse

    health = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "ok",
            "mqtt": "ok",
            "modbus": "ok",
        },
        "details": {},
    }

    overall_status = "ok"
    http_status = status.HTTP_200_OK

    # Check database
    try:
        async with async_session_maker() as session:
            await session.execute(select(1))
        health["details"]["database"] = {"connected": True}
    except Exception as e:
        health["services"]["database"] = "error"
        health["details"]["database"] = {"connected": False, "error": str(e)}
        overall_status = "degraded"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check MQTT
    try:
        mqtt_mgr = getattr(request.app.state, "mqtt_manager", None)
        if mqtt_mgr:
            if mqtt_mgr._enabled:
                is_connected = (
                    mqtt_mgr._client is not None
                    and hasattr(mqtt_mgr._client, "is_connected")
                    and mqtt_mgr._client.is_connected
                )
                health["details"]["mqtt"] = {
                    "enabled": True,
                    "connected": is_connected,
                    "broker": f"{mqtt_mgr._host}:{mqtt_mgr._port}",
                }
                if not is_connected:
                    health["services"]["mqtt"] = "disconnected"
                    overall_status = "degraded"
                    if http_status == status.HTTP_200_OK:
                        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            else:
                health["details"]["mqtt"] = {"enabled": False}
                health["services"]["mqtt"] = "disabled"
        else:
            health["details"]["mqtt"] = {"enabled": False}
            health["services"]["mqtt"] = "disabled"
    except Exception as e:
        health["services"]["mqtt"] = "error"
        health["details"]["mqtt"] = {"error": str(e)}
        overall_status = "degraded"
        if http_status == status.HTTP_200_OK:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Modbus gateways
    # Note: Gateways are lazy-initialized (only created on first request)
    # So having no connected gateways is not necessarily an error
    try:
        manager = getattr(request.app.state, "modbus_manager", None)
        if manager:
            gateways = manager.get_gateways_status()
            connected_gateways = sum(1 for gw in gateways if gw["connected"])
            total_devices = len(manager.list_devices())
            health["details"]["modbus"] = {
                "initialized": True,
                "total_devices": total_devices,
                "total_gateways": len(gateways),
                "connected_gateways": connected_gateways,
                "gateways": gateways,
            }
            # Only mark as warning if we have devices but no gateways at all
            # (gateways are lazy-initialized, so this is expected until first request)
            if total_devices > 0 and len(gateways) == 0:
                health["services"]["modbus"] = "warning"
                # Don't degrade overall status - gateways will connect on first use
            elif len(gateways) > 0 and connected_gateways == 0:
                health["services"]["modbus"] = "warning"
                # Don't degrade overall status - connections may be idle
            else:
                health["services"]["modbus"] = "ok"
        else:
            # Manager not initialized - this is an error
            health["details"]["modbus"] = {"initialized": False}
            health["services"]["modbus"] = "error"
            overall_status = "degraded"
            if http_status == status.HTTP_200_OK:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        health["services"]["modbus"] = "error"
        health["details"]["modbus"] = {"error": str(e)}
        overall_status = "degraded"
        if http_status == status.HTTP_200_OK:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    health["status"] = overall_status

    return JSONResponse(content=health, status_code=http_status)

