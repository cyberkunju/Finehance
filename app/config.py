"""Application configuration management."""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = Field(default="AI Finance Platform", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Monitoring & Error Tracking
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(default=0.1, alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_profiles_sample_rate: float = Field(default=0.1, alias="SENTRY_PROFILES_SAMPLE_RATE")

    # Prometheus Metrics
    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    enable_gpu_metrics: bool = Field(default=True, alias="ENABLE_GPU_METRICS")
    gpu_metrics_interval: float = Field(default=15.0, alias="GPU_METRICS_INTERVAL")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    auth_rate_limit_per_minute: int = Field(default=10, alias="AUTH_RATE_LIMIT_PER_MINUTE")

    # AI Rate Limiting (stricter - GPU is expensive)
    ai_rate_limit_per_minute: int = Field(default=5, alias="AI_RATE_LIMIT_PER_MINUTE")
    ai_rate_limit_per_hour: int = Field(default=100, alias="AI_RATE_LIMIT_PER_HOUR")
    ai_rate_limit_parse_per_minute: int = Field(
        default=30, alias="AI_RATE_LIMIT_PARSE_PER_MINUTE"
    )  # Higher for transaction parsing

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ai_finance_platform",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")

    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    encryption_key: str = Field(default="change-me-in-production", alias="ENCRYPTION_KEY")

    # CORS
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], alias="ALLOWED_ORIGINS"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ML Models
    model_storage_path: str = Field(default="./models", alias="MODEL_STORAGE_PATH")
    global_model_path: str = Field(
        default="./models/global_categorization_model.pkl", alias="GLOBAL_MODEL_PATH"
    )
    min_transactions_for_user_model: int = Field(
        default=50, alias="MIN_TRANSACTIONS_FOR_USER_MODEL"
    )
    min_corrections_for_user_model: int = Field(default=10, alias="MIN_CORRECTIONS_FOR_USER_MODEL")

    # AI Brain (LLM Service)
    ai_brain_mode: str = Field(default="http", alias="AI_BRAIN_MODE")  # "http" or "direct"
    ai_brain_url: str = Field(default="http://localhost:8080", alias="AI_BRAIN_URL")
    ai_brain_model_path: str = Field(
        default="./ai_brain/models/financial-brain-qlora", alias="AI_BRAIN_MODEL_PATH"
    )
    ai_brain_enabled: bool = Field(default=True, alias="AI_BRAIN_ENABLED")

    # Financial API (Optional)
    plaid_client_id: str | None = Field(default=None, alias="PLAID_CLIENT_ID")
    plaid_secret: str | None = Field(default=None, alias="PLAID_SECRET")
    plaid_env: str = Field(default="sandbox", alias="PLAID_ENV")

    # Performance
    max_workers: int = Field(default=4, alias="MAX_WORKERS")
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")


# Global settings instance
settings = Settings()
