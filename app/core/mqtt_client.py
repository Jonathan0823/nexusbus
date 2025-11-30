"""MQTT Client Manager for publishing Modbus data."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

try:
    from gmqtt import Client as MQTTClient

    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class MQTTClientManager:
    """Manages MQTT connection and publishing using gmqtt."""

    def __init__(self) -> None:
        self._client: Optional[MQTTClient] = None
        self._enabled = False

        if not HAS_MQTT:
            logger.warning("gmqtt library not found. MQTT support disabled.")
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

        # Generate unique client ID
        client_id = f"modbus-middleware-{uuid.uuid4().hex[:8]}"
        self._client = MQTTClient(client_id)

        # Set auth if provided
        if self._username:
            self._client.set_auth_credentials(self._username, self._password)

        logger.info(
            f"MQTT configured: {self._host}:{self._port} (Client ID: {client_id})"
        )

    async def start(self) -> None:
        """Start the MQTT client (connect)."""
        if not self._enabled or not self._client:
            return

        try:
            await self._client.connect(self._host, self._port)
            logger.info("Connected to MQTT Broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker: {e}")
            # Don't raise, just log. App continues without MQTT.

    async def stop(self) -> None:
        """Stop the MQTT client (disconnect)."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
                logger.info("Disconnected from MQTT Broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT: {e}")

    async def publish(self, topic_suffix: str, payload: Any) -> None:
        """Publish data to MQTT.

        Args:
            topic_suffix: Suffix to append to prefix (e.g. 'device/holding/0')
            payload: Data to publish (will be JSON encoded)
        """
        if not self._enabled or not self._client:
            return

        if not self._client.is_connected:
            # Optional: Try to reconnect logic could go here,
            # but gmqtt handles auto-reconnect for lost connections usually.
            # If initial connect failed, we might be disconnected.
            return

        topic = f"{self._topic_prefix}/{topic_suffix}"

        try:
            # Ensure payload is JSON serializable
            message = json.dumps(payload, default=str)

            self._client.publish(topic, message, qos=0)
            logger.debug(f"Published to {topic}")

        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")


mqtt_manager = MQTTClientManager()
