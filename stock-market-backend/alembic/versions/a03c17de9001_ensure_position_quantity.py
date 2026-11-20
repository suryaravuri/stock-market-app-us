"""Complete quantity migration after the previous empty revision.

Revision ID: a03c17de9001
Revises: d42da1ad0fc0
"""
from alembic import op

revision = "a03c17de9001"
down_revision = "d42da1ad0fc0"
branch_labels = None
depends_on = None


def upgrade():
    # IF NOT EXISTS also supports local databases where quantity was added manually.
    op.execute("ALTER TABLE position_state ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE position_state ALTER COLUMN quantity DROP DEFAULT")


def downgrade():
    # Preserve quantity and its data: the previous revision already expected it.
    pass
