"""daily briefs

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17

Adds the daily_briefs table (news roundup, one per KST day).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_briefs",
        sa.Column("date_kst", sa.String(length=10), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("market_read", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("generated_by", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_daily_briefs_created_at", "daily_briefs", ["created_at"])


def downgrade() -> None:
    op.drop_table("daily_briefs")
