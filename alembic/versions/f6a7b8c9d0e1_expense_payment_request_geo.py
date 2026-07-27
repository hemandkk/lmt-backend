"""add state/branch to expenses and payment_requests

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "6ef65be1bd39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("state_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.create_index("ix_expenses_state_id", "expenses", ["state_id"])
    op.create_index("ix_expenses_branch_id", "expenses", ["branch_id"])
    op.create_foreign_key(
        "fk_expenses_state_id_states",
        "expenses",
        "states",
        ["state_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_expenses_branch_id_branches",
        "expenses",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "payment_requests", sa.Column("state_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "payment_requests", sa.Column("branch_id", sa.Integer(), nullable=True)
    )
    op.create_index("ix_payment_requests_state_id", "payment_requests", ["state_id"])
    op.create_index(
        "ix_payment_requests_branch_id", "payment_requests", ["branch_id"]
    )
    op.create_foreign_key(
        "fk_payment_requests_state_id_states",
        "payment_requests",
        "states",
        ["state_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payment_requests_branch_id_branches",
        "payment_requests",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_payment_requests_branch_id_branches",
        "payment_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_payment_requests_state_id_states",
        "payment_requests",
        type_="foreignkey",
    )
    op.drop_index("ix_payment_requests_branch_id", table_name="payment_requests")
    op.drop_index("ix_payment_requests_state_id", table_name="payment_requests")
    op.drop_column("payment_requests", "branch_id")
    op.drop_column("payment_requests", "state_id")

    op.drop_constraint(
        "fk_expenses_branch_id_branches", "expenses", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_expenses_state_id_states", "expenses", type_="foreignkey"
    )
    op.drop_index("ix_expenses_branch_id", table_name="expenses")
    op.drop_index("ix_expenses_state_id", table_name="expenses")
    op.drop_column("expenses", "branch_id")
    op.drop_column("expenses", "state_id")
