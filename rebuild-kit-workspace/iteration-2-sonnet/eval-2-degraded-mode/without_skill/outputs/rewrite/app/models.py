"""
SQLAlchemy models mirroring rewrite/db/schema.postgres.sql.

Kept intentionally close to the legacy shape (ticketd/db/schema.sql) so the
diff between "what the old system stored" and "what this stores" is easy to
audit. See that file's comments for the two deliberate structural changes
(TIMESTAMPTZ, hashed reset tokens) and the outbox table added to fix
Known Problem #1.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# BIGSERIAL on Postgres (matches db/schema.postgres.sql), but plain INTEGER
# on SQLite — SQLite only treats a column declared exactly INTEGER PRIMARY
# KEY as its autoincrementing rowid alias; BIGINT does not qualify, which
# breaks autoincrement for the in-memory test suite (tests/conftest.py).
# Production always runs Postgres, so this only affects tests.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="med")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    assignee_id: Mapped[int | None] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResetToken(Base):
    """
    Stores a HASH of the reset token, not the token itself.

    Fixes Known Problem #2 (MD5 tokens, ticketd/app/server.py:90). The
    plaintext token is generated with `secrets.token_urlsafe` (see
    app/services/tokens.py), emailed to the user, and never written to disk.
    Only its SHA-256 hash is persisted, so a database read alone can't be
    turned into a usable reset token.
    """

    __tablename__ = "reset_tokens"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationOutbox(Base):
    """
    Transactional outbox. Fixes Known Problem #1 (synchronous SMTP send
    inside the request path, ticketd/app/notify.py + server.py:76,94).

    Request handlers INSERT a row here as part of their normal DB
    transaction and return immediately. app/worker.py is a separate process
    that polls unsent rows and performs the actual SMTP send, so an SMTP
    outage delays notifications instead of stalling API responses.
    """

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    to_email: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
