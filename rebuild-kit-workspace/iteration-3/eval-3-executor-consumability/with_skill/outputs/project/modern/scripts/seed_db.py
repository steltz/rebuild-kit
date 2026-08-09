#!/usr/bin/env python3
"""Applies the T2 replay fixture's starting state to a freshly-migrated Postgres database --
the translated equivalent of verification/replay/corpus/seed.sql (SQLite) for modern/. Single
source of truth for the row *values* is kept here in Python (not a hand-written SQL file) so
row shape stays in sync with app/models.py; only the DATA mirrors seed.sql, not the schema
(alembic owns the schema). Run after `alembic upgrade head`, before serving traffic.

Usage: DATABASE_URL=postgresql+psycopg://... python scripts/seed_db.py
"""
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models import Ticket, User


def seed(session: Session) -> None:
    session.add(User(id=1, email="jdoe@corp.example.com", name="J Doe"))
    session.flush()

    def ts(s: str) -> datetime:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

    session.add_all(
        [
            Ticket(
                id=1,
                title="Printer on fire",
                slug="printer-on-fire",
                priority="high",
                status="open",
                assignee_id=None,
                created_at=ts("2026-07-01T09:00:00"),
                closed_at=None,
            ),
            Ticket(
                id=2,
                title="Minor typo on login page",
                slug="minor-typo-on-login-page",
                priority="low",
                status="open",
                assignee_id=None,
                created_at=ts("2026-07-02T10:00:00"),
                closed_at=None,
            ),
            Ticket(
                id=3,
                title="Old closed ticket",
                slug="old-closed-ticket",
                priority="med",
                status="closed",
                assignee_id=None,
                created_at=ts("2026-06-01T08:00:00"),
                closed_at=ts("2026-06-02T08:00:00"),
            ),
        ]
    )
    session.flush()

    # Explicit ids were inserted against a BY DEFAULT identity column -- bump the sequence so
    # the next app-driven insert continues at 4, matching legacy's sqlite rowid continuation.
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('users', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM users))"
        )
    )
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('tickets', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM tickets))"
        )
    )
    session.commit()


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)
    with Session(engine) as session:
        seed(session)
    print(f"[seed_db] seeded {database_url}")


if __name__ == "__main__":
    main()
