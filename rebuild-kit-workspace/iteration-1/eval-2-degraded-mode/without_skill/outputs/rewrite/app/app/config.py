"""Env-driven settings (prefix TICKETD_). Compat flags: see ADR-003."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKETD_")

    database_url: str = "postgresql+psycopg://localhost/ticketd"

    # SMTP — legacy values from ticketd/app/notify.py [S]
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    smtp_timeout: int = 30
    mail_from: str = "ticketd@example.internal"
    watchers_addr: str = "watchers@example.internal"  # hardcoded in legacy server.py:76
    smtp_legacy_headerless: bool = True  # ADR-001: reproduce legacy envelope-only mail

    # Reset-token knobs — legacy constants, server.py:16-17 [S]
    reset_window_min: int = 30
    rate_limit_per_hour: int = 3

    # Compat flags — ADR-003
    enable_legacy_csv_export: bool = True
    allow_internal_bypass: bool = False  # legacy default was effectively True; see ADR-002

    # Timezone legacy naive timestamps were written in. UNKNOWN — placeholder (ADR-004).
    legacy_tz: str = "UTC"


settings = Settings()
