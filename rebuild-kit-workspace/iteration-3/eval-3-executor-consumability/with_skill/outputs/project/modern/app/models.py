from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Ticket(Base):
    """Mirrors docs/contracts/ddl.sql. slug UNIQUE is WO-005/PB-003 scope (blocked on OQ-001) --
    not added here. priority/status CHECKs replicate the legacy DB-level enforcement exactly,
    including the uncaught-500-on-invalid-priority gap this WO reproduces as-is."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# reset_tokens is intentionally NOT modeled here: it's out of this WO's scope (PB-002/WO-003
# redesigns it entirely) and no route in WO-001 reads or writes it. Its table is still created
# by the initial migration, as a legacy-shape mirror, purely so the replay harness's db_dump
# state comparison has a matching (empty) table on both sides -- see migrations/versions.
