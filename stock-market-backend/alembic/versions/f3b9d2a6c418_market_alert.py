"""market_alert: early-breakout and TradingView alerts

Revision ID: f3b9d2a6c418
Revises: e7a3c5b1f902
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3b9d2a6c418"
down_revision: Union[str, Sequence[str], None] = "e7a3c5b1f902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_alert",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("candle_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("level", sa.Float(), nullable=True),
        sa.Column("volume_ratio", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("source", "symbol", "candle_start", name="uq_market_alert_candle"),
    )
    op.create_index("ix_market_alert_created_at", "market_alert", ["created_at"])
    op.create_index("ix_market_alert_symbol", "market_alert", ["symbol"])


def downgrade() -> None:
    op.drop_table("market_alert")
