"""add source-aware analytics metadata and synthetic candle observations

Revision ID: e15e5a90c2b1
Revises: c41a8e2d90f1
Create Date: 2026-08-28 13:10:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e15e5a90c2b1"
down_revision: Union[str, Sequence[str], None] = "c41a8e2d90f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position_test_state",
        sa.Column(
            "analytics_candle_source",
            sa.String(length=40),
            nullable=False,
            server_default="SYNTHETIC_UNRECORDED",
        ),
    )

    # Existing #15D real-candle test runs are identifiable from their immutable
    # opening-history event. Existing synthetic #15C-2 runs cannot be fully
    # reconstructed because their OHLC observations were not persisted, so they
    # intentionally remain SYNTHETIC_UNRECORDED rather than mixing market prices.
    op.execute(
        """
        UPDATE position_test_state p
           SET analytics_candle_source = 'MARKET_CANDLE'
         WHERE EXISTS (
             SELECT 1
               FROM position_test_state_history h
              WHERE h.position_test_state_id = p.position_test_state_id
                AND h.event = 'TEST_POSITION_OPENED_FOR_REAL_CANDLE_MONITORING'
         )
        """
    )

    op.create_table(
        "position_test_candle_observation",
        sa.Column("position_test_candle_observation_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("position_test_state_id", sa.BigInteger(), nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("high_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("low_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["position_test_state_id"], ["position_test_state.position_test_state_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("position_test_candle_observation_id"),
        sa.UniqueConstraint("test_run_id", "candle_time", name="uq_position_test_observation_run_candle"),
    )
    op.create_index(
        "ix_position_test_candle_observation_position_id",
        "position_test_candle_observation",
        ["position_test_state_id"],
    )
    op.create_index(
        "ix_position_test_candle_observation_run_id",
        "position_test_candle_observation",
        ["test_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_position_test_candle_observation_run_id", table_name="position_test_candle_observation")
    op.drop_index("ix_position_test_candle_observation_position_id", table_name="position_test_candle_observation")
    op.drop_table("position_test_candle_observation")
    op.drop_column("position_test_state", "analytics_candle_source")
