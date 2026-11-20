"""add signal cycle tracking for new-session rearming

Revision ID: 5f9c4e72a114
Revises: 8c02f4ae129d
Create Date: 2026-08-28 10:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5f9c4e72a114"
down_revision: Union[str, Sequence[str], None] = "8c02f4ae129d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signal_state",
        sa.Column("cycle_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "signal_state",
        sa.Column("cycle_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "signal_state_history",
        sa.Column("cycle_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.execute("UPDATE signal_state SET cycle_started_at = created_at WHERE cycle_started_at IS NULL")
    op.alter_column("signal_state", "cycle_number", server_default=None)
    op.alter_column("signal_state_history", "cycle_number", server_default=None)


def downgrade() -> None:
    op.drop_column("signal_state_history", "cycle_number")
    op.drop_column("signal_state", "cycle_started_at")
    op.drop_column("signal_state", "cycle_number")
