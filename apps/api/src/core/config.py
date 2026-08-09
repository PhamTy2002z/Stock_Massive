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

    # Auth (JWT)
    auth_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "http://localhost:3000"  # Comma-separated origins

    # Vnstock
    vnstock_source: str = "VCI"  # Default data source (VCI is most reliable)
    # Quota là 20 request/phút khi thiếu key, 60 khi có — adapter tự giãn nhịp theo.
    vnstock_api_key: str = ""

    # FiinQuant — Main Source cho market và valuation, xem docs/adr/0002
    fiinquant_username: str = ""
    fiinquant_password: str = ""

    # Universe — tập mã được thu thập và phục vụ, trần 100 mã (src/stocks/universe.py).
    # Rỗng là hợp lệ: ứng dụng chạy được và Collector không có gì để làm.
    universe_symbols: str = ""  # Comma-separated

    # Upstash Redis (supports both naming conventions)
    upstash_redis_url: str = ""
    upstash_redis_token: str = ""
    upstash_redis_rest_url: str = ""  # Alternative name from Upstash dashboard
    upstash_redis_rest_token: str = ""  # Alternative name from Upstash dashboard
    cache_redis_url: str = ""  # Standard Redis URL for local/self-hosted deployments

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

    # Daily OHLCV Collector
    # Disabled by default: the full-market job exhausts vnstock Guest quota and
    # competes with interactive dashboard requests. Hybrid collectors own this
    # refresh path instead.
    daily_ohlcv_enabled: bool = False
    daily_ohlcv_hour: int = 16  # 4 PM Vietnam time (after market close)
    daily_ohlcv_minute: int = 0
    daily_ohlcv_delay: float = 2.0  # Delay between requests to avoid rate limit
    daily_ohlcv_batch_size: int = 50  # Symbols per batch

    # Financial Statements Job
    financial_statements_enabled: bool = True
    financial_statements_hour: int = 2  # 02:00 ICT (Sunday)
    financial_statements_minute: int = 0
    financial_statements_delay: float = 2.0  # seconds between API calls

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_standard_max: int = 100  # requests per window
    rate_limit_standard_window: int = 60  # seconds
    rate_limit_heavy_max: int = 20  # requests per window
    rate_limit_heavy_window: int = 60  # seconds

    # Sector Historical Performance Job
    # Disabled until a persisted cache exists; otherwise every restart after
    # 15:45 retries a broad vnstock scan and starves interactive requests.
    sector_historical_enabled: bool = False
    sector_historical_hour: int = 15  # 15:45 ICT (after sector-performance job at 15:30)
    sector_historical_minute: int = 45
    sector_historical_delay: float = 1.2  # seconds between API calls (~50 req/min)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
