"""market predictions

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17

Adds the market_predictions table (house prediction + daily brief). Dialect-
agnostic; timestamps timezone-aware; the full prediction is stored in JSON.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_predictions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("regime", sa.String(length=24), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.String(length=16), nullable=False),
        sa.Column("agent_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_market_predictions_created_at", "market_predictions", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("market_predictions")
