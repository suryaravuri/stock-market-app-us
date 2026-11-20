"""zerodha trade fills and broker order status

Revision ID: b5a7e3c9d214
Revises: 8d4f2b6e1c35
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5a7e3c9d214"
down_revision: Union[str, Sequence[str], None] = "8d4f2b6e1c35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("zerodha_order", sa.Column("kite_status", sa.String(40), nullable=True))
    op.add_column("zerodha_order", sa.Column("kite_status_message", sa.Text(), nullable=True))
    op.add_column("zerodha_order", sa.Column("filled_quantity", sa.Integer(), nullable=True))
    op.add_column("zerodha_order", sa.Column("average_price", sa.Numeric(14, 2), nullable=True))

    op.create_table(
        "zerodha_trade",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kite_user_id", sa.String(40), nullable=False),
        sa.Column("kite_trade_id", sa.String(40), nullable=False),
        sa.Column("kite_order_id", sa.String(40), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("tradingsymbol", sa.String(40), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("product", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(14, 4), nullable=False),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "kite_trade_id", name="uq_zerodha_trade_user_trade"),
    )
    op.create_index("ix_zerodha_trade_user_id", "zerodha_trade", ["user_id"])
    op.create_index("ix_zerodha_trade_kite_order_id", "zerodha_trade", ["kite_order_id"])
    op.create_index("ix_zerodha_trade_tradingsymbol", "zerodha_trade", ["tradingsymbol"])
    op.create_index("ix_zerodha_trade_fill_time", "zerodha_trade", ["fill_time"])


def downgrade() -> None:
    op.drop_table("zerodha_trade")
    op.drop_column("zerodha_order", "average_price")
    op.drop_column("zerodha_order", "filled_quantity")
    op.drop_column("zerodha_order", "kite_status_message")
    op.drop_column("zerodha_order", "kite_status")
