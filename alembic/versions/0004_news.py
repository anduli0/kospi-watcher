"""news items

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-17

Adds the news_items table (dated, retention-pruned headlines).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_items",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_kst", sa.String(length=10), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_news_items_topic", "news_items", ["topic"])
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"])
    op.create_index("ix_news_items_date_kst", "news_items", ["date_kst"])


def downgrade() -> None:
    op.drop_table("news_items")
