"""create signal lifecycle tables

Revision ID: 8c02f4ae129d
Revises: 24aba10b8da3
Create Date: 2026-08-28 10:25:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8c02f4ae129d"
down_revision: Union[str, Sequence[str], None] = "24aba10b8da3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_state",
        sa.Column("signal_state_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("previous_state", sa.String(length=40), nullable=True),
        sa.Column("last_event", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("observed_breakout_status", sa.String(length=80), nullable=True),
        sa.Column("breakout_level", sa.Numeric(18, 6), nullable=True),
        sa.Column("confirmation_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("confirmed_entry_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("signal_candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.stock_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_state_id"),
        sa.UniqueConstraint("stock_id", "timeframe", name="uq_signal_state_stock_timeframe"),
    )
    op.create_index(op.f("ix_signal_state_stock_id"), "signal_state", ["stock_id"], unique=False)
    op.create_index(op.f("ix_signal_state_timeframe"), "signal_state", ["timeframe"], unique=False)
    op.create_index(op.f("ix_signal_state_state"), "signal_state", ["state"], unique=False)

    op.create_table(
        "signal_state_history",
        sa.Column("signal_state_history_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("observed_breakout_status", sa.String(length=80), nullable=True),
        sa.Column("signal_candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.stock_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_state_history_id"),
    )
    op.create_index(op.f("ix_signal_state_history_stock_id"), "signal_state_history", ["stock_id"], unique=False)
    op.create_index(op.f("ix_signal_state_history_timeframe"), "signal_state_history", ["timeframe"], unique=False)
    op.create_index(op.f("ix_signal_state_history_to_state"), "signal_state_history", ["to_state"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signal_state_history_to_state"), table_name="signal_state_history")
    op.drop_index(op.f("ix_signal_state_history_timeframe"), table_name="signal_state_history")
    op.drop_index(op.f("ix_signal_state_history_stock_id"), table_name="signal_state_history")
    op.drop_table("signal_state_history")
    op.drop_index(op.f("ix_signal_state_state"), table_name="signal_state")
    op.drop_index(op.f("ix_signal_state_timeframe"), table_name="signal_state")
    op.drop_index(op.f("ix_signal_state_stock_id"), table_name="signal_state")
    op.drop_table("signal_state")
