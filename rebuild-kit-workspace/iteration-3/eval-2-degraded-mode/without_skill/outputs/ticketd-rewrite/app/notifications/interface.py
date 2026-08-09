from typing import Protocol


class NotificationBackend(Protocol):
    """Swap point for the outbox worker's send step. SMTP today
    (smtp_backend.py, mirrors legacy app/notify.py); replace with a real
    queue-backed implementation once production infra/volume is known —
    see docs/OPEN_QUESTIONS.md #6."""

    async def send(self, to: str, body: str) -> None: ...
