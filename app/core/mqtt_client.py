"""MQTT Client Manager for publishing Modbus data."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

try:
    from gmqtt import Client as MQTTClient

    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MQTTClientManager:
    """Manages MQTT connection and publishing using gmqtt."""

    def __init__(self) -> None:
        self._client: Optional[MQTTClient] = None
        self._enabled = False

        if not HAS_MQTT:
            logger.warning(
                "mqtt_library_not_found",
                message="gmqtt library not found. MQTT support disabled.",
            )
            return

        if not settings.MQTT_BROKER_HOST:
            logger.info(
                "mqtt_disabled",
                reason="MQTT_BROKER_HOST not set",
                message="MQTT support disabled",
            )
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
            "mqtt_configured",
            host=self._host,
            port=self._port,
            client_id=client_id,
            topic_prefix=self._topic_prefix,
            message="MQTT client configured",
        )

    async def start(self) -> None:
        """Start the MQTT client (connect)."""
        if not self._enabled or not self._client:
            return

        try:
            await self._client.connect(self._host, self._port)
            logger.info(
                "mqtt_connected",
                host=self._host,
                port=self._port,
                message="Connected to MQTT Broker",
            )
        except Exception as e:
            logger.error(
                "mqtt_connect_failed",
                host=self._host,
                port=self._port,
                error=str(e),
                error_type=type(e).__name__,
                message="Failed to connect to MQTT Broker",
                exc_info=True,
            )
            # Don't raise, just log. App continues without MQTT.

    async def stop(self) -> None:
        """Stop the MQTT client (disconnect)."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
                logger.info(
                    "mqtt_disconnected",
                    host=self._host,
                    port=self._port,
                    message="Disconnected from MQTT Broker",
                )
            except Exception as e:
                logger.error(
                    "mqtt_disconnect_error",
                    host=self._host,
                    port=self._port,
                    error=str(e),
                    error_type=type(e).__name__,
                    message="Error disconnecting from MQTT",
                    exc_info=True,
                )

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
            logger.debug(
                "mqtt_published",
                topic=topic,
                topic_suffix=topic_suffix,
                payload_size=len(message),
                message="Published to MQTT",
            )

        except Exception as e:
            logger.error(
                "mqtt_publish_error",
                topic=topic,
                topic_suffix=topic_suffix,
                error=str(e),
                error_type=type(e).__name__,
                message="Failed to publish to MQTT",
                exc_info=True,
            )


mqtt_manager = MQTTClientManager()
