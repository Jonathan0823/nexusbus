"""Application configuration using Pydantic settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/modbus_db"
    DATABASE_ECHO: bool = False
    
    # Application settings
    APP_NAME: str = "Modbus Middleware"
    APP_VERSION: str = "0.1.0"
    POLL_INTERVAL_SECONDS: int = 5
    CACHE_TTL_SECONDS: int = 300  # Cache entries expire after 5 minutes

    # MQTT Configuration (Optional)
    MQTT_BROKER_HOST: str | None = None
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str | None = None
    MQTT_PASSWORD: str | None = None
    MQTT_TOPIC_PREFIX: str = "modbus/data"


settings = Settings()
