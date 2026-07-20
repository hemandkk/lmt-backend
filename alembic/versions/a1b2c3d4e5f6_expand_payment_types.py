"""Expand payment types: rename full → full_payment, add fee types

Revision ID: a1b2c3d4e5f6
Revises: 0202c6612320
Create Date: 2026-07-20 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "0202c6612320"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename legacy value (PostgreSQL 10+)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'paymenttype'
                  AND e.enumlabel = 'full'
            ) THEN
                ALTER TYPE paymenttype RENAME VALUE 'full' TO 'full_payment';
            END IF;
        END
        $$;
        """
    )

    for value in (
        "full_payment",
        "registration_fee",
        "before_exam_fee",
        "after_result_fee",
    ):
        op.execute(
            f"ALTER TYPE paymenttype ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # PostgreSQL cannot easily remove enum values; remap data then recreate.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'paymenttype'
                  AND e.enumlabel = 'full_payment'
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'paymenttype'
                  AND e.enumlabel = 'full'
            ) THEN
                ALTER TYPE paymenttype RENAME VALUE 'full_payment' TO 'full';
            END IF;
        END
        $$;
        """
    )
    # New fee values are left in place (safe no-op for downgrade of ADD VALUE).
