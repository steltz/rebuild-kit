"""initial schema

Revision ID: 66595a7d7bcc
Revises: 
Create Date: 2026-08-09 08:36:57.008509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66595a7d7bcc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Mirrors docs/contracts/ddl.sql (legacy) translated per
    docs/migration/mapping.md, WO-001 scope only: tickets.slug UNIQUE (PB-003/WO-005) and
    reset_tokens' redesign (PB-002/WO-003) are explicitly NOT part of this WO -- both tables
    below reproduce their CURRENT (legacy) shape, not their eventual target shape."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )
    # Legacy-shape mirror (no PK, matching docs/contracts/ddl.sql exactly) -- kept out of
    # app/models.py since no WO-001 route touches it; exists only so the replay harness's
    # db_dump state comparison has a matching (empty) table on both sides. WO-003 replaces
    # this table wholesale per docs/migration/mapping.md.
    op.create_table(
        "reset_tokens",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("created_ts", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("reset_tokens")
    op.drop_table("tickets")
    op.drop_table("users")
