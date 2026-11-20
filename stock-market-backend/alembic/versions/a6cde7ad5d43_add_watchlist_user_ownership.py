"""add watchlist user ownership

Revision ID: a6cde7ad5d43
Revises: 9777d7b089f7
Create Date: 2026-09-23 10:50:47.134758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6cde7ad5d43'
down_revision: Union[str, Sequence[str], None] = '9777d7b089f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable initially.
    op.add_column(
        "watchlist",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # 2. Assign existing watchlists only if an application user exists.
    # op.execute(
    #     """
    #     UPDATE watchlist
    #     SET user_id = (
    #         SELECT id
    #         FROM app_user
    #         ORDER BY id
    #         LIMIT 1
    #     )
    #     WHERE user_id IS NULL
    #       AND EXISTS (SELECT 1 FROM app_user)
    #     """
    # )

    # 2. Handle legacy watchlists created before user ownership existed.
    #
    # If no application users exist yet, remove legacy unowned watchlists.
    # Otherwise assign them to the first ADMIN (or first available user).

    op.execute(
        """
        DELETE FROM watchlist
        WHERE user_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM app_user
          )
        """
    )

    op.execute(
        """
        UPDATE watchlist
        SET user_id = (
            SELECT id
            FROM app_user
            ORDER BY
                CASE WHEN role = 'ADMIN' THEN 0 ELSE 1 END,
                id
            LIMIT 1
        )
        WHERE user_id IS NULL
        """
    )

def downgrade() -> None:
    op.drop_index(
        "ix_watchlist_user_id",
        table_name="watchlist",
    )

    op.drop_constraint(
        "fk_watchlist_user_id_app_user",
        "watchlist",
        type_="foreignkey",
    )

    op.drop_column(
        "watchlist",
        "user_id",
    )