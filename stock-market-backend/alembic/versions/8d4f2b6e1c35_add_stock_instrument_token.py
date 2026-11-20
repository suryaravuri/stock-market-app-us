"""add zerodha instrument_token to stock

Revision ID: 8d4f2b6e1c35
Revises: 3e9b5c1d7a20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8d4f2b6e1c35"
down_revision: Union[str, Sequence[str], None] = "3e9b5c1d7a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stock", sa.Column("instrument_token", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("stock", "instrument_token")
