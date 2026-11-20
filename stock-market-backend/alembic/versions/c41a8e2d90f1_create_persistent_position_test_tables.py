"""create isolated controlled persistent position test tables

Revision ID: c41a8e2d90f1
Revises: b7d31f2a6c90
Create Date: 2026-08-28 11:55:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c41a8e2d90f1"
down_revision: Union[str, Sequence[str], None] = "b7d31f2a6c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "position_test_state",
        sa.Column("position_test_state_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
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
        sa.PrimaryKeyConstraint("position_test_state_id"),
        sa.UniqueConstraint("test_run_id", name="uq_position_test_state_run_id"),
    )
    op.create_index("ix_position_test_state_test_run_id", "position_test_state", ["test_run_id"], unique=True)
    op.create_index("ix_position_test_state_stock_id", "position_test_state", ["stock_id"])

    op.create_table(
        "position_test_state_history",
        sa.Column("position_test_state_history_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("position_test_state_id", sa.BigInteger(), nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("active_stop", sa.Numeric(18, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["position_test_state_id"], ["position_test_state.position_test_state_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("position_test_state_history_id"),
    )
    op.create_index("ix_position_test_state_history_position_id", "position_test_state_history", ["position_test_state_id"])
    op.create_index("ix_position_test_state_history_run_id", "position_test_state_history", ["test_run_id"])


def downgrade() -> None:
    op.drop_index("ix_position_test_state_history_run_id", table_name="position_test_state_history")
    op.drop_index("ix_position_test_state_history_position_id", table_name="position_test_state_history")
    op.drop_table("position_test_state_history")
    op.drop_index("ix_position_test_state_stock_id", table_name="position_test_state")
    op.drop_index("ix_position_test_state_test_run_id", table_name="position_test_state")
    op.drop_table("position_test_state")
