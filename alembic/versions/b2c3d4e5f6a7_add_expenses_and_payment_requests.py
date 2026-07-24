"""Add expenses and payment_requests tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "paid_to_details",
            sa.Text(),
            nullable=False,
            comment="Account / UPI details to pay to",
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("installment_number", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("transaction_id", sa.String(length=100), nullable=True),
        sa.Column("receipt_url", sa.String(length=500), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("paid_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verified_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_payment_requests_request_id",
        "payment_requests",
        ["request_id"],
        unique=True,
    )
    op.create_index(
        "ix_payment_requests_status",
        "payment_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expense_id", sa.String(length=20), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_to", sa.Text(), nullable=False),
        sa.Column("transaction_id", sa.String(length=100), nullable=True),
        sa.Column("installment_number", sa.String(length=100), nullable=True),
        sa.Column("receipt_url", sa.String(length=500), nullable=True),
        sa.Column("invoice_url", sa.String(length=500), nullable=True),
        sa.Column(
            "payment_request_id",
            sa.Integer(),
            sa.ForeignKey("payment_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_expenses_expense_id", "expenses", ["expense_id"], unique=True
    )
    op.create_index(
        "ix_expenses_expense_date", "expenses", ["expense_date"], unique=False
    )
    op.create_index(
        "ix_expenses_payment_request_id",
        "expenses",
        ["payment_request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_payment_request_id", table_name="expenses")
    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_index("ix_expenses_expense_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_payment_requests_status", table_name="payment_requests")
    op.drop_index("ix_payment_requests_request_id", table_name="payment_requests")
    op.drop_table("payment_requests")
