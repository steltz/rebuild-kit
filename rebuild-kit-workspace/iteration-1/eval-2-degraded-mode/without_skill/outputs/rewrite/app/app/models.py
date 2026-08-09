"""SQLAlchemy models mirroring rewrite/sql/001_initial.sql."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    # Q2: never touched by app code; exists for a possible external writer.
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)  # NOT unique (Q7)
    priority: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResetToken(Base):
    __tablename__ = "reset_tokens"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)  # sha256 hex (ADR-002)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEmail(Base):
    __tablename__ = "outbox_emails"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
