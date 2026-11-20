"""create analysis-only post-entry position lifecycle tables

Revision ID: b7d31f2a6c90
Revises: 5f9c4e72a114
Create Date: 2026-08-28 11:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7d31f2a6c90"
down_revision: Union[str, Sequence[str], None] = "5f9c4e72a114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "position_state",
        sa.Column("position_state_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("signal_cycle_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("previous_state", sa.String(length=40), nullable=True),
        sa.Column("last_event", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("initial_stop", sa.Numeric(18, 6), nullable=False),
        sa.Column("active_stop", sa.Numeric(18, 6), nullable=False),
        sa.Column("target_1", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_2", sa.Numeric(18, 6), nullable=True),
        sa.Column("initial_risk_per_share", sa.Numeric(18, 6), nullable=False),
        sa.Column("target_1_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("target_2_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_evaluated_candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("exit_reason", sa.String(length=80), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.stock_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("position_state_id"),
        sa.UniqueConstraint("stock_id", "timeframe", "signal_cycle_number", name="uq_position_state_stock_timeframe_cycle"),
    )
    op.create_index("ix_position_state_stock_id", "position_state", ["stock_id"])
    op.create_index("ix_position_state_timeframe", "position_state", ["timeframe"])
    op.create_index("ix_position_state_signal_cycle_number", "position_state", ["signal_cycle_number"])
    op.create_index("ix_position_state_state", "position_state", ["state"])

    op.create_table(
        "position_state_history",
        sa.Column("position_state_history_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("position_state_id", sa.BigInteger(), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("signal_cycle_number", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("active_stop", sa.Numeric(18, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["position_state_id"], ["position_state.position_state_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.stock_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("position_state_history_id"),
    )
    op.create_index("ix_position_state_history_position_state_id", "position_state_history", ["position_state_id"])
    op.create_index("ix_position_state_history_stock_id", "position_state_history", ["stock_id"])
    op.create_index("ix_position_state_history_timeframe", "position_state_history", ["timeframe"])
    op.create_index("ix_position_state_history_signal_cycle_number", "position_state_history", ["signal_cycle_number"])
    op.create_index("ix_position_state_history_to_state", "position_state_history", ["to_state"])


def downgrade() -> None:
    op.drop_index("ix_position_state_history_to_state", table_name="position_state_history")
    op.drop_index("ix_position_state_history_signal_cycle_number", table_name="position_state_history")
    op.drop_index("ix_position_state_history_timeframe", table_name="position_state_history")
    op.drop_index("ix_position_state_history_stock_id", table_name="position_state_history")
    op.drop_index("ix_position_state_history_position_state_id", table_name="position_state_history")
    op.drop_table("position_state_history")
    op.drop_index("ix_position_state_state", table_name="position_state")
    op.drop_index("ix_position_state_signal_cycle_number", table_name="position_state")
    op.drop_index("ix_position_state_timeframe", table_name="position_state")
    op.drop_index("ix_position_state_stock_id", table_name="position_state")
    op.drop_table("position_state")
