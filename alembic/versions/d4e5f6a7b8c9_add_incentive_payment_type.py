"""add incentive payment type to payment_requests and expenses

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add payment_type and employee_id to payment_requests
    op.add_column(
        "payment_requests",
        sa.Column(
            "payment_type",
            sa.String(20),
            nullable=False,
            server_default="office",
        ),
    )
    op.create_index(
        "ix_payment_requests_payment_type",
        "payment_requests",
        ["payment_type"],
    )
    op.add_column(
        "payment_requests",
        sa.Column("employee_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_payment_requests_employee_id",
        "payment_requests",
        ["employee_id"],
    )
    op.create_foreign_key(
        "fk_payment_requests_employee_id",
        "payment_requests",
        "users",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add expense_type and employee_id to expenses
    op.add_column(
        "expenses",
        sa.Column(
            "expense_type",
            sa.String(20),
            nullable=False,
            server_default="office",
        ),
    )
    op.create_index(
        "ix_expenses_expense_type",
        "expenses",
        ["expense_type"],
    )
    op.add_column(
        "expenses",
        sa.Column("employee_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_expenses_employee_id",
        "expenses",
        ["employee_id"],
    )
    op.create_foreign_key(
        "fk_expenses_employee_id",
        "expenses",
        "users",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_expenses_employee_id", "expenses", type_="foreignkey")
    op.drop_index("ix_expenses_employee_id", table_name="expenses")
    op.drop_column("expenses", "employee_id")
    op.drop_index("ix_expenses_expense_type", table_name="expenses")
    op.drop_column("expenses", "expense_type")

    op.drop_constraint(
        "fk_payment_requests_employee_id", "payment_requests", type_="foreignkey"
    )
    op.drop_index("ix_payment_requests_employee_id", table_name="payment_requests")
    op.drop_column("payment_requests", "employee_id")
    op.drop_index("ix_payment_requests_payment_type", table_name="payment_requests")
    op.drop_column("payment_requests", "payment_type")
