"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "RSS Manager"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./rss_manager.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes, auto-refreshed on activity
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days sliding window
    ALGORITHM: str = "HS256"
    REFRESH_COOKIE_NAME: str = "rss_refresh_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Feed settings
    DEFAULT_FETCH_INTERVAL: int = 3600  # 1 hour in seconds
    MAX_ARTICLES_PER_FEED: int = 1000
    FEED_BROWSER_HEADLESS: bool = True
    CLOAKBROWSER_USER_DATA_DIR: str | None = None
    CLOAKBROWSER_PROXY: str | None = None
    CLOAKBROWSER_GEOIP: bool = False
    CLOAKBROWSER_HUMANIZE: bool = True

    # Push Notification (Web Push)
    VAPID_PUBLIC_KEY: str | None = None
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_CONTACT_EMAIL: str | None = None
    NOTIFICATION_ENCRYPTION_KEY: str | None = Field(None, min_length=32)

    # Request safety
    MAX_IMPORT_BYTES: int = 10 * 1024 * 1024
    ALLOW_PRIVATE_FETCH_URLS: bool = False

    @field_validator("NOTIFICATION_ENCRYPTION_KEY", mode="before")
    @classmethod
    def normalize_notification_key(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self

        weak_secrets = {
            "your-secret-key-change-in-production",
            "rss_manager_secret_key_2024_production",
            "your_super_secret_key_at_least_32_characters_long",
        }
        if self.SECRET_KEY in weak_secrets or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be a unique value of at least 32 characters in production"
            )
        if not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.ALLOW_PRIVATE_FETCH_URLS:
            raise ValueError("Private outbound targets cannot be enabled in production")
        if self.COOKIE_SAMESITE == "none":
            raise ValueError("Use lax or strict authentication cookies")
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Create settings instance - will read from environment variables
settings = Settings()
