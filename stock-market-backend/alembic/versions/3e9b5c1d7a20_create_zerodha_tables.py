"""create zerodha session and order audit tables

Revision ID: 3e9b5c1d7a20
Revises: 7dd260d3390a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3e9b5c1d7a20"
down_revision: Union[str, Sequence[str], None] = "7dd260d3390a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zerodha_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kite_user_id", sa.String(40), nullable=False),
        sa.Column("kite_user_name", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("login_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_zerodha_session_user_id", "zerodha_session", ["user_id"], unique=True)

    op.create_table(
        "zerodha_order",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kite_user_id", sa.String(40), nullable=True),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("tradingsymbol", sa.String(40), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("product", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("last_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("kite_order_id", sa.String(40), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_zerodha_order_user_id", "zerodha_order", ["user_id"])
    op.create_index("ix_zerodha_order_tradingsymbol", "zerodha_order", ["tradingsymbol"])
    op.create_index("ix_zerodha_order_status", "zerodha_order", ["status"])
    op.create_index("ix_zerodha_order_kite_order_id", "zerodha_order", ["kite_order_id"])
    op.create_index("ix_zerodha_order_created_at", "zerodha_order", ["created_at"])


def downgrade() -> None:
    op.drop_table("zerodha_order")
    op.drop_table("zerodha_session")
