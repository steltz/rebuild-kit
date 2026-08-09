"""initial schema

Translates db/schema.sql (legacy SQLite) to Postgres, plus the outbox table
and hashed reset tokens added by this rewrite. See docs/DESIGN.md.

Revision ID: 0001
Revises:
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(), nullable=False, server_default="med"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])

    op.create_table(
        "reset_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reset_tokens_email", "reset_tokens", ["email"])

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("to_email", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')", name="ck_outbox_status"
        ),
    )
    op.create_index("ix_outbox_status_created", "outbox_messages", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox_messages")
    op.drop_table("reset_tokens")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("users")
