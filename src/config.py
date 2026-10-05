from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_key: str = Field(..., description="Static API key for X-API-Key header")
    database_url: str = Field(..., description="Async SQLAlchemy DSN")
    rabbitmq_url: str = Field(..., description="AMQP connection URL")

    outbox_poll_interval: float = Field(default=2.0, description="Outbox polling interval in seconds")
    outbox_batch_size: int = Field(default=50, description="Max outbox records per poll")
    enable_outbox_in_api: bool = Field(default=False, description="Run outbox poller in FastAPI lifespan")

    webhook_timeout: float = Field(default=10.0, description="HTTP timeout for webhook delivery in seconds")
    webhook_max_retries: int = Field(default=3, description="Max retry attempts for webhook delivery")


@lru_cache
def get_settings() -> Settings:
    return Settings()
