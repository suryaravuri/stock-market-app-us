"""holding style per watchlist stock + auto_trade records

Revision ID: e7a3c5b1f902
Revises: d2f6b8c4e517
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a3c5b1f902"
down_revision: Union[str, Sequence[str], None] = "d2f6b8c4e517"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watchlist_stock",
        sa.Column("holding_style", sa.String(10), nullable=False, server_default="SWING"),
    )

    op.create_table(
        "auto_trade",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlist.watchlist_id", ondelete="SET NULL"), nullable=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("broker", sa.String(20), nullable=False, server_default="ALPACA_PAPER"),
        sa.Column("broker_order_id", sa.String(64), nullable=True),
        sa.Column("holding_style", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("stop_loss_price", sa.Float(), nullable=True),
        sa.Column("take_profit_price", sa.Float(), nullable=True),
        sa.Column("trail_percent", sa.Float(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("exit_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="OPEN"),
        sa.Column("exit_reason", sa.String(20), nullable=True),
        sa.Column("exit_note", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auto_trade_user_id", "auto_trade", ["user_id"])
    op.create_index("ix_auto_trade_symbol", "auto_trade", ["symbol"])
    op.create_index("ix_auto_trade_status", "auto_trade", ["status"])


def downgrade() -> None:
    op.drop_table("auto_trade")
    op.drop_column("watchlist_stock", "holding_style")
