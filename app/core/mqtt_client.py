"""MQTT Client Manager for publishing Modbus data."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

try:
    import aiomqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class MQTTClientManager:
    """Manages MQTT connection and publishing."""

    def __init__(self) -> None:
        self._client: Optional[aiomqtt.Client] = None
        self._enabled = False
        
        if not HAS_MQTT:
            logger.warning("aiomqtt library not found. MQTT support disabled.")
            return

        if not settings.MQTT_BROKER_HOST:
            logger.info("MQTT_BROKER_HOST not set. MQTT support disabled.")
            return

        self._enabled = True
        self._host = settings.MQTT_BROKER_HOST
        self._port = settings.MQTT_BROKER_PORT
        self._username = settings.MQTT_USERNAME
        self._password = settings.MQTT_PASSWORD
        self._topic_prefix = settings.MQTT_TOPIC_PREFIX.rstrip("/")

        logger.info(f"MQTT configured: {self._host}:{self._port}")

    async def start(self) -> None:
        """Start the MQTT client (connect)."""
        if not self._enabled:
            return

        try:
            # Create client instance
            self._client = aiomqtt.Client(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            
            # Connect
            await self._client.__aenter__()
            logger.info("Connected to MQTT Broker")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker: {e}")
            # We don't raise here to keep the app running without MQTT
            self._client = None

    async def stop(self) -> None:
        """Stop the MQTT client (disconnect)."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
                logger.info("Disconnected from MQTT Broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT: {e}")
            finally:
                self._client = None

    async def publish(self, topic_suffix: str, payload: Any) -> None:
        """Publish data to MQTT.
        
        Args:
            topic_suffix: Suffix to append to prefix (e.g. 'device/holding/0')
            payload: Data to publish (will be JSON encoded)
        """
        if not self._enabled or not self._client:
            return

        topic = f"{self._topic_prefix}/{topic_suffix}"
        
        try:
            # Ensure payload is JSON serializable
            message = json.dumps(payload, default=str)
            
            await self._client.publish(topic, payload=message)
            logger.debug(f"Published to {topic}")
            
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            # Optional: Try to reconnect if connection lost?
            # For now, we just log error. aiomqtt client might need re-init if connection drops.

mqtt_manager = MQTTClientManager()
