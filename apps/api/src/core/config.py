"""Application configuration using pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"

    # CORS
    cors_origins: str = "http://localhost:3000"  # Comma-separated origins

    # Vnstock
    vnstock_source: str = "VCI"  # Default data source (VCI is most reliable)

    # Upstash Redis (supports both naming conventions)
    upstash_redis_url: str = ""
    upstash_redis_token: str = ""
    upstash_redis_rest_url: str = ""  # Alternative name from Upstash dashboard
    upstash_redis_rest_token: str = ""  # Alternative name from Upstash dashboard

    @property
    def redis_url(self) -> str:
        """Get Redis URL (supports both naming conventions)."""
        return self.upstash_redis_rest_url or self.upstash_redis_url

    @property
    def redis_token(self) -> str:
        """Get Redis token (supports both naming conventions)."""
        return self.upstash_redis_rest_token or self.upstash_redis_token

    # Scheduler
    scheduler_enabled: bool = True
    intraday_collect_hour: int = 15
    intraday_collect_minute: int = 30
    intraday_symbols: str = "VCB,FPT,VNM,VIC,VHM"  # Comma-separated VN30 subset
    intraday_retention_days: int = 30

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_standard_max: int = 100  # requests per window
    rate_limit_standard_window: int = 60  # seconds
    rate_limit_heavy_max: int = 20  # requests per window
    rate_limit_heavy_window: int = 60  # seconds


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
