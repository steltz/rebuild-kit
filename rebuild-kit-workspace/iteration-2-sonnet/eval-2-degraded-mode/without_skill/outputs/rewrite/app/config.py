"""
Runtime configuration.

Values here are conservative defaults, not evidence-derived tuning. None of
them come from a load test or production observation — we don't have either
yet (see docs/00-EVIDENCE-AND-ASSUMPTIONS.md). Revisit anything marked
EVIDENCE-NEEDED once real traffic/DB data is available.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKETD_")

    # --- Database -----------------------------------------------------
    database_url: str = "postgresql+psycopg://ticketd:ticketd@localhost:5432/ticketd"

    # --- Behavior ported verbatim from ticketd/app/server.py ----------
    reset_window_minutes: int = 30          # server.py:16 RESET_WINDOW_MIN
    rate_limit_per_hour: int = 3            # server.py:17 RATE_LIMIT_PER_HOUR

    # Undocumented bypass header, preserved for parity (see behavior
    # inventory + risk register — NOT validated against any evidence of who
    # actually relies on it). Comparison is constant-time in auth.py; that is
    # a pure security hardening with no behavioral difference, not a scope
    # change.
    internal_bypass_header: str = "X-Internal-Bypass"
    internal_bypass_value: str = "1"

    # --- SMTP (outbox worker) ------------------------------------------
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    smtp_timeout_seconds: int = 30
    mail_from: str = "ticketd@example.internal"

    # EVIDENCE-NEEDED: no traffic data to size this. Small, conservative
    # default for a low-volume internal tool.
    worker_poll_interval_seconds: int = 5
    worker_batch_size: int = 20
    worker_max_attempts: int = 5


settings = Settings()
