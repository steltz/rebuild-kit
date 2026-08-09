from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"

    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    smtp_from: str = "ticketd@example.internal"
    notify_watchers_email: str = "watchers@example.internal"

    # Matches legacy RESET_WINDOW_MIN / RATE_LIMIT_PER_HOUR (app/server.py).
    reset_window_minutes: int = 30
    rate_limit_per_hour: int = 3

    outbox_poll_interval_seconds: float = 2.0
    outbox_max_attempts: int = 5


settings = Settings()
