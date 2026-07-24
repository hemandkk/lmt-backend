"""Add actor fields on expenses (requester, approver, verifier)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-24 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_expenses_requested_by_id_users",
        "expenses",
        "users",
        ["requested_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_expenses_approved_by_id_users",
        "expenses",
        "users",
        ["approved_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_expenses_verified_by_id_users",
        "expenses",
        "users",
        ["verified_by_id"],
        ["id"],
    )
    op.create_index(
        "ix_expenses_requested_by_id",
        "expenses",
        ["requested_by_id"],
    )
    op.create_index(
        "ix_expenses_approved_by_id",
        "expenses",
        ["approved_by_id"],
    )
    op.create_index(
        "ix_expenses_verified_by_id",
        "expenses",
        ["verified_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_verified_by_id", table_name="expenses")
    op.drop_index("ix_expenses_approved_by_id", table_name="expenses")
    op.drop_index("ix_expenses_requested_by_id", table_name="expenses")
    op.drop_constraint(
        "fk_expenses_verified_by_id_users", "expenses", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_expenses_approved_by_id_users", "expenses", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_expenses_requested_by_id_users", "expenses", type_="foreignkey"
    )
    op.drop_column("expenses", "verified_by_id")
    op.drop_column("expenses", "approved_by_id")
    op.drop_column("expenses", "requested_by_id")
