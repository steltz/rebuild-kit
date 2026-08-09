# ticketd rewrite — Phase 1: Schema and Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phase 0 (`00-project-setup.md`) complete — `ticketd-api/`
> exists and `./scripts/check.sh` passes.
> **Read first:** `../DESIGN-architecture.md` (full schema + rationale for
> every table/index).

**Goal:** Create the Postgres schema via Alembic and a script that migrates
`tickets` and `users` data out of the legacy SQLite file
(`ticketd/db/ticketd.sqlite3`) into it.

**Architecture:** One Alembic migration creates all four tables
(`users`, `tickets`, `reset_tokens`, `notification_outbox`) as specified in
`../DESIGN-architecture.md`. A standalone, idempotent, dry-run-capable
script (`scripts/migrate_from_sqlite.py`) does the data copy — it is not
part of the FastAPI app and is only ever run manually during cutover
(Phase 6).

**Tech Stack:** Alembic, SQLAlchemy Core (for the migration script — reading
SQLite directly with the stdlib `sqlite3` module is simplest and avoids
pulling in a second ORM dialect just for a one-time read).

## Global Constraints

- Match the DDL in `../DESIGN-architecture.md` exactly — other phases'
  ORM models and queries are written against those exact column
  names/types.
- `reset_tokens` (legacy) is **not** migrated — see
  `../DESIGN-password-reset.md` "Migration note." Only `users` and
  `tickets` get copied.
- The migration script must be safe to run against a copy of production
  data without modifying the source SQLite file (read-only open).
- IDs must be preserved (`tickets.id`, `users.id` in Postgres must match
  the legacy SQLite ids) — anything that references a ticket by id
  (bookmarks, links, support tickets mentioning an id) must keep working.

---

### Task 1: SQLAlchemy models

**Files:**
- Create: `ticketd-api/app/models.py`
- Modify: `ticketd-api/migrations/env.py:target_metadata` (set to
  `from app.models import Base; target_metadata = Base.metadata`, replacing
  the `None` placeholder from Phase 0 Task 2)

**Interfaces:**
- Produces: `app.models.Base` (declarative base), `app.models.User`,
  `app.models.Ticket`, `app.models.ResetToken`,
  `app.models.NotificationOutbox` — SQLAlchemy 2.x mapped classes. Later
  phases (routes, worker, migration script) import these directly, e.g.
  `from app.models import Ticket`.

- [ ] **Step 1: Write `app/models.py`**

```python
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, CheckConstraint, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'med', 'high')", name="tickets_priority_check"),
        CheckConstraint("status IN ('open', 'closed')", name="tickets_status_check"),
        Index("tickets_slug_key", "slug", unique=True),
        Index("tickets_status_created_at_idx", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None]


class ResetToken(Base):
    __tablename__ = "reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None]


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    to_address: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    attempts: Mapped[int] = mapped_column(nullable=False, server_default="0")
    last_attempt_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None]
```

- [ ] **Step 2: Point Alembic at the metadata** — in
  `migrations/env.py`, replace `target_metadata = None` with:

```python
from app.models import Base
target_metadata = Base.metadata
```

- [ ] **Step 3: Generate and review the migration**

```bash
cd ticketd-api
alembic revision --autogenerate -m "create tickets, users, reset_tokens, notification_outbox"
```
Open the generated file under `migrations/versions/` and confirm it matches
`../DESIGN-architecture.md`'s DDL — in particular confirm the partial index
`notification_outbox_pending_idx ... WHERE sent_at IS NULL` came through
correctly (autogenerate sometimes misses `WHERE` clauses on indexes; if it
did, add it by hand using `op.create_index(..., postgresql_where=...)`).

- [ ] **Step 4: Apply and verify**

```bash
alembic upgrade head
python -c "
import asyncio
from sqlalchemy import text
from app.db import engine
async def check():
    async with engine.connect() as conn:
        r = await conn.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\"))
        print(sorted(row[0] for row in r))
asyncio.run(check())
"
```
Expected: `['alembic_version', 'notification_outbox', 'reset_tokens', 'tickets', 'users']`

- [ ] **Step 5: Commit**

```bash
git add app/models.py migrations
git commit -m "feat: add Postgres schema (tickets, users, reset_tokens, notification_outbox)"
```

---

### Task 2: SQLite → Postgres migration script

**Files:**
- Create: `ticketd-api/scripts/migrate_from_sqlite.py`
- Test: `ticketd-api/tests/test_migrate_from_sqlite.py`

**Interfaces:**
- Produces: `migrate_from_sqlite(sqlite_path: str, session: AsyncSession,
  dry_run: bool = True) -> MigrationReport` where `MigrationReport` is a
  small dataclass with `users_migrated: int`, `tickets_migrated: int`,
  `skipped: list[str]`. Used directly by Phase 6's cutover runbook.

- [ ] **Step 1: Write the failing test** — uses a tiny in-memory SQLite DB
  with the legacy schema, and asserts rows land in Postgres with matching
  ids.

```python
# tests/test_migrate_from_sqlite.py
import sqlite3
import pytest
from sqlalchemy import select
from app.models import User, Ticket
from scripts.migrate_from_sqlite import migrate_from_sqlite


@pytest.fixture
def legacy_sqlite(tmp_path):
    path = tmp_path / "ticketd.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL);
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, slug TEXT NOT NULL,
            priority TEXT, status TEXT NOT NULL, assignee_id INTEGER,
            created_at DATETIME NOT NULL, closed_at DATETIME
        );
        INSERT INTO users VALUES (1, 'a@corp.example.com', 'Alice');
        INSERT INTO tickets VALUES (1, 'Fix DB', 'fix-db', 'high', 'open', NULL, '2026-07-01T10:00:00', NULL);
        INSERT INTO tickets VALUES (2, 'fix db!', 'fix-db', 'low', 'closed', NULL, '2026-07-02T10:00:00', '2026-07-03T10:00:00');
    """)
    conn.commit()
    conn.close()
    return str(path)


@pytest.mark.asyncio
async def test_migrate_preserves_ids_and_data(legacy_sqlite, db_session):
    report = await migrate_from_sqlite(legacy_sqlite, db_session, dry_run=False)
    assert report.users_migrated == 1
    assert report.tickets_migrated == 2

    users = (await db_session.execute(select(User))).scalars().all()
    assert {u.id for u in users} == {1}

    tickets = (await db_session.execute(select(Ticket).order_by(Ticket.id))).scalars().all()
    assert [t.id for t in tickets] == [1, 2]
    # both legacy rows share slug "fix-db" -- migration does NOT dedupe
    # historical slugs (see DESIGN-slug-collisions.md); this asserts that
    # intentional behavior, not an oversight.
    assert tickets[0].slug == "fix-db"
    assert tickets[1].slug == "fix-db"


@pytest.mark.asyncio
async def test_migrate_dry_run_writes_nothing(legacy_sqlite, db_session):
    report = await migrate_from_sqlite(legacy_sqlite, db_session, dry_run=True)
    assert report.tickets_migrated == 2  # counted...
    users = (await db_session.execute(select(User))).scalars().all()
    assert users == []  # ...but nothing committed
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_migrate_from_sqlite.py -v
```
Expected: FAIL — `scripts/migrate_from_sqlite.py` doesn't exist yet.

- [ ] **Step 3: Implement**

```python
# scripts/migrate_from_sqlite.py
"""One-time migration: legacy SQLite (ticketd/db/ticketd.sqlite3) -> Postgres.

Intentionally does NOT migrate reset_tokens (see DESIGN-password-reset.md
"Migration note") and does NOT deduplicate colliding legacy slugs (see
DESIGN-slug-collisions.md open items -- renumbering historical slugs risks
breaking existing links more than it's worth).

The new tickets.slug column has a UNIQUE index (see DESIGN-architecture.md).
If the legacy data has more than a handful of colliding slugs, that unique
index must be relaxed (or a NOT VALID constraint used) before running this
migration for real -- see Task 3, "Preflight," below.
"""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Ticket


@dataclass
class MigrationReport:
    users_migrated: int = 0
    tickets_migrated: int = 0
    skipped: list[str] = field(default_factory=list)


async def migrate_from_sqlite(sqlite_path: str, session: AsyncSession, dry_run: bool = True) -> MigrationReport:
    report = MigrationReport()
    src = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        for row in src.execute("SELECT * FROM users ORDER BY id"):
            session.add(User(id=row["id"], email=row["email"], name=row["name"]))
            report.users_migrated += 1

        for row in src.execute("SELECT * FROM tickets ORDER BY id"):
            session.add(Ticket(
                id=row["id"],
                title=row["title"],
                slug=row["slug"],
                priority=row["priority"] or "med",
                status=row["status"],
                assignee_id=row["assignee_id"],
                created_at=_parse_legacy_ts(row["created_at"]),
                closed_at=_parse_legacy_ts(row["closed_at"]) if row["closed_at"] else None,
            ))
            report.tickets_migrated += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    finally:
        src.close()
    return report


def _parse_legacy_ts(value: str) -> datetime:
    # legacy timestamps are naive local time (see 01-CURRENT-BEHAVIOR-CONTRACT.md
    # section 5) -- migrated as-is, not reinterpreted as UTC, to avoid
    # silently shifting historical closed_at/created_at values. Revisit if
    # 03-OPEN-QUESTIONS.md item 3 lands on "reinterpret as UTC."
    return datetime.fromisoformat(value)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_migrate_from_sqlite.py -v
```
Expected: PASS.

- [ ] **Step 5: Add a CLI entrypoint for real runs**

```python
# append to scripts/migrate_from_sqlite.py
if __name__ == "__main__":
    import argparse
    import asyncio
    from app.db import async_session

    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite_path")
    parser.add_argument("--commit", action="store_true", help="actually write (default is dry-run)")
    args = parser.parse_args()

    async def main():
        async with async_session() as session:
            report = await migrate_from_sqlite(args.sqlite_path, session, dry_run=not args.commit)
            print(report)

    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_from_sqlite.py tests/test_migrate_from_sqlite.py
git commit -m "feat: add SQLite-to-Postgres migration script (dry-run by default)"
```

---

### Task 3: Preflight check for slug collisions in legacy data

The new schema's unique index on `tickets.slug` will reject the migration
outright if the legacy data already has colliding slugs (per
`../DESIGN-slug-collisions.md`, historical collisions are left as-is rather
than renumbered — but "left as-is" is incompatible with a hard unique
constraint, so this needs a concrete resolution, not a hand-wave).

**Files:**
- Create: `ticketd-api/scripts/check_legacy_slug_collisions.py`

- [ ] **Step 1: Write the check**

```python
# scripts/check_legacy_slug_collisions.py
"""Run against the real legacy ticketd.sqlite3 before Phase 6 cutover.
Reports any slug used by more than one ticket."""
import sqlite3
import sys


def find_collisions(sqlite_path: str) -> dict[str, list[int]]:
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, slug FROM tickets ORDER BY slug, id").fetchall()
    conn.close()
    by_slug: dict[str, list[int]] = {}
    for ticket_id, slug in rows:
        by_slug.setdefault(slug, []).append(ticket_id)
    return {slug: ids for slug, ids in by_slug.items() if len(ids) > 1}


if __name__ == "__main__":
    collisions = find_collisions(sys.argv[1])
    if not collisions:
        print("No slug collisions in legacy data. Safe to migrate as-is.")
        sys.exit(0)
    print(f"{len(collisions)} colliding slug(s) found:")
    for slug, ids in collisions.items():
        print(f"  {slug!r}: ticket ids {ids}")
    print(
        "\nDESIGN-slug-collisions.md's default is to leave historical "
        "collisions alone, but the new schema has a hard UNIQUE constraint "
        "on slug. Before running migrate_from_sqlite.py --commit, decide "
        "(see 03-OPEN-QUESTIONS.md item 2) whether to: "
        "(a) suffix all but the first of each colliding group at migration "
        "time (e.g. append '-<id>' only to the historical duplicates), or "
        "(b) relax the constraint for pre-existing rows. Do not run the "
        "real migration until this is resolved -- it will fail partway "
        "through otherwise."
    )
    sys.exit(1)
```

- [ ] **Step 2: Run against a copy of production data as part of Phase 6
  planning, not now** (no production SQLite file is available in this
  workspace). Document this as a required pre-cutover step in
  `plans/06-migration-and-cutover.md` (already cross-referenced there).

- [ ] **Step 3: Commit**

```bash
git add scripts/check_legacy_slug_collisions.py
git commit -m "chore: add preflight check for legacy slug collisions before migration"
```

---

## Definition of done for this phase

- `alembic upgrade head` creates all four tables matching
  `../DESIGN-architecture.md`.
- `migrate_from_sqlite.py` correctly copies `users` and `tickets` with
  matching ids, in dry-run mode by default, tested against a synthetic
  SQLite fixture (no real production data was available to this workspace —
  flagged in `../03-OPEN-QUESTIONS.md`).
- `check_legacy_slug_collisions.py` exists and Phase 6 references running it
  against real data before any real cutover.
