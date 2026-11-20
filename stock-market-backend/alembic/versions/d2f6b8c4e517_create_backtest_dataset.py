"""create backtest_dataset (CSV uploads)

Revision ID: d2f6b8c4e517
Revises: c9e4a1b7d302
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2f6b8c4e517"
down_revision: Union[str, Sequence[str], None] = "c9e4a1b7d302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_dataset",
        sa.Column("backtest_dataset_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("source_timezone", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="UPLOADING"),
        sa.Column("base_timeframe", sa.String(10), nullable=True),
        sa.Column("chunks_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_bar", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_bar", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bars_by_timeframe", postgresql.JSONB(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backtest_dataset_symbol", "backtest_dataset", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_backtest_dataset_symbol", table_name="backtest_dataset")
    op.drop_table("backtest_dataset")
