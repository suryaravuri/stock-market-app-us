"""auto_trade.entry_type (BREAKOUT / SUPPORT_BOUNCE)

Revision ID: a4c8e1f7b360
Revises: f3b9d2a6c418
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e1f7b360"
down_revision: Union[str, Sequence[str], None] = "f3b9d2a6c418"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auto_trade",
        sa.Column("entry_type", sa.String(20), nullable=False, server_default="BREAKOUT"),
    )


def downgrade() -> None:
    op.drop_column("auto_trade", "entry_type")
