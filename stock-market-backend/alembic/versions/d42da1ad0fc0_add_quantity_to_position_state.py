"""add quantity to position state

Revision ID: d42da1ad0fc0
Revises: f16a01b2c3d4
Create Date: 2026-09-02 13:31:43.350878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd42da1ad0fc0'
down_revision: Union[str, Sequence[str], None] = 'f16a01b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
