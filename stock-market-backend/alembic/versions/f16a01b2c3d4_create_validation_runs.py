"""phase 16A strategy baseline freeze and validation run tracking

Revision ID: f16a01b2c3d4
Revises: e15e5a90c2b1
Create Date: 2026-08-28 14:15:00
"""
from alembic import op
import sqlalchemy as sa
revision = "f16a01b2c3d4"
down_revision = "e15e5a90c2b1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("validation_run",
        sa.Column("validation_run_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_version", sa.String(80), nullable=False),
        sa.Column("validation_phase", sa.String(80), nullable=False),
        sa.Column("execution_mode", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=False),
        sa.Column("baseline_manifest", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("validation_run_id"))
    op.create_index("ix_validation_run_strategy_version", "validation_run", ["strategy_version"])
    op.create_index("ix_validation_run_status", "validation_run", ["status"])
    for table in ("signal_state", "signal_state_history", "position_state", "position_state_history"):
        op.add_column(table, sa.Column("validation_run_id", sa.BigInteger(), nullable=True))
        op.add_column(table, sa.Column("strategy_version", sa.String(80), nullable=True))
        op.create_foreign_key(f"fk_{table}_validation_run", table, "validation_run", ["validation_run_id"], ["validation_run_id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_validation_run_id", table, ["validation_run_id"])
        op.create_index(f"ix_{table}_strategy_version", table, ["strategy_version"])

def downgrade():
    for table in ("position_state_history", "position_state", "signal_state_history", "signal_state"):
        op.drop_index(f"ix_{table}_strategy_version", table_name=table)
        op.drop_index(f"ix_{table}_validation_run_id", table_name=table)
        op.drop_constraint(f"fk_{table}_validation_run", table, type_="foreignkey")
        op.drop_column(table, "strategy_version"); op.drop_column(table, "validation_run_id")
    op.drop_index("ix_validation_run_status", table_name="validation_run")
    op.drop_index("ix_validation_run_strategy_version", table_name="validation_run")
    op.drop_table("validation_run")
