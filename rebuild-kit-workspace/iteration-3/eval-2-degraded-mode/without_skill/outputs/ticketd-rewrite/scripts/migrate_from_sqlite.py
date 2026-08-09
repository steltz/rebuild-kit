"""One-time data migration: legacy db/ticketd.sqlite3 -> Postgres.

Usage:
    python scripts/migrate_from_sqlite.py /path/to/ticketd.sqlite3

Reads the legacy SQLite file read-only. Never point this at the live file
while the legacy Flask app is running. reset_tokens are NOT migrated —
they're short-lived and MD5-derived; see docs/DESIGN.md and
docs/MIGRATION_PLAN.md for the reasoning. This script has not been run
against real data yet (no production DB access at time of writing).
"""

import asyncio
import datetime
import sqlite3
import sys

from app.db import async_session
from app.models import Ticket, User


def _parse_naive_local(value: str | None) -> datetime.datetime | None:
    """Legacy stored naive local time via datetime.now().isoformat() (no
    offset). We can't recover the original timezone, so we treat it as UTC
    on import — flagged, not silently assumed correct. See
    docs/OPEN_QUESTIONS.md #8."""
    if value is None:
        return None
    return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone.utc)


async def migrate(sqlite_path: str) -> None:
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    async with async_session() as session:
        for row in conn.execute("SELECT * FROM users"):
            session.add(User(id=row["id"], email=row["email"], name=row["name"]))

        for row in conn.execute("SELECT * FROM tickets"):
            session.add(
                Ticket(
                    id=row["id"],
                    title=row["title"],
                    slug=row["slug"],
                    priority=row["priority"],
                    status=row["status"],
                    assignee_id=row["assignee_id"],
                    created_at=_parse_naive_local(row["created_at"]),
                    closed_at=_parse_naive_local(row["closed_at"]),
                )
            )

        await session.commit()

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(migrate(sys.argv[1]))
