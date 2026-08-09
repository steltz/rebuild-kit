"""SMTP notification backend. Mirrors legacy app/notify.py's connection
parameters, but is now called from the outbox worker (app/notifications/worker.py)
instead of inline in a request handler — that's the actual fix for the
synchronous-email problem. See docs/DESIGN.md 'Fix 1'.
"""

import asyncio
import smtplib

from app.config import settings


class SmtpNotificationBackend:
    async def send(self, to: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to, body)

    def _send_sync(self, to: str, body: str) -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            s.sendmail(settings.smtp_from, [to], body)
