import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """Mirrors legacy `users` table. Nothing in this codebase writes to it —
    see docs/OPEN_QUESTIONS.md #7 on provisioning."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="med")
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ResetToken(Base):
    """Stores a hash of the reset token, never the plaintext (fix for the
    legacy MD5-plaintext-token problem — see docs/DESIGN.md)."""

    __tablename__ = "reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxMessage(Base):
    """Transactional outbox for notifications — fix for the legacy
    synchronous-email-in-request problem. See docs/DESIGN.md."""

    __tablename__ = "outbox_messages"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_outbox_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    to_email: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
