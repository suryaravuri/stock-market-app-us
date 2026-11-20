"""create backtest tables

Revision ID: c9e4a1b7d302
Revises: b5a7e3c9d214
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9e4a1b7d302"
down_revision: Union[str, Sequence[str], None] = "b5a7e3c9d214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_run",
        sa.Column("backtest_run_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("symbols", sa.String(500), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backtest_run_status", "backtest_run", ["status"])

    op.create_table(
        "backtest_trade",
        sa.Column("backtest_trade_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("backtest_run_id", sa.Integer(), sa.ForeignKey("backtest_run.backtest_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("signal_time", sa.DateTime(timezone=True)),
        sa.Column("entry_time", sa.DateTime(timezone=True)),
        sa.Column("entry_price", sa.Float()),
        sa.Column("exit_time", sa.DateTime(timezone=True)),
        sa.Column("exit_price", sa.Float()),
        sa.Column("shares", sa.Integer()),
        sa.Column("initial_stop", sa.Float()),
        sa.Column("final_stop", sa.Float()),
        sa.Column("target", sa.Float()),
        sa.Column("pnl", sa.Float()),
        sa.Column("pnl_percent", sa.Float()),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(30)),
    )
    op.create_index("ix_backtest_trade_backtest_run_id", "backtest_trade", ["backtest_run_id"])


def downgrade() -> None:
    op.drop_index("ix_backtest_trade_backtest_run_id", table_name="backtest_trade")
    op.drop_table("backtest_trade")
    op.drop_index("ix_backtest_run_status", table_name="backtest_run")
    op.drop_table("backtest_run")
