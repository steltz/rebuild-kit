from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    reset_window_minutes: int = 30
    reset_rate_limit_per_hour: int = 3
    outbox_poll_interval_seconds: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
