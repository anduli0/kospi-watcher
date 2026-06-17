"""paper trading: orders, fills, positions

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17

Adds the paper-execution tables. Dialect-agnostic (SQLite + Postgres); money as
String (TEXT-backed Decimal); timestamps timezone-aware.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("proposal_id", sa.String(length=64), nullable=False),
        sa.Column("risk_decision_id", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("trading_mode", sa.String(length=16), nullable=False),
        sa.Column("filled_quantity", sa.Integer(), nullable=False),
        sa.Column("avg_fill_price", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_proposal_id", "orders", ["proposal_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index(
        "ix_orders_idempotency_key", "orders", ["idempotency_key"], unique=True
    )

    op.create_table(
        "fills",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.String(length=32), nullable=False),
        sa.Column("liquidity", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"])
    op.create_index("ix_fills_symbol", "fills", ["symbol"])

    op.create_table(
        "positions",
        sa.Column("account", sa.String(length=32), primary_key=True),
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_cost", sa.String(length=32), nullable=False),
        sa.Column("realized_pnl", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("positions")
    op.drop_table("fills")
    op.drop_table("orders")
