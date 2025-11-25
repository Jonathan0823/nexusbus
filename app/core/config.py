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


settings = Settings()
