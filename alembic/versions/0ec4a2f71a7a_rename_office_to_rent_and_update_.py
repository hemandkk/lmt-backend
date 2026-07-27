"""rename office to rent and update payment categories

Revision ID: 0ec4a2f71a7a
Revises: e5f6a7b8c9d0
Create Date: 2026-07-27 14:57:49.712213

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0ec4a2f71a7a'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    # Convert existing data
    op.execute("""
        UPDATE payment_requests
        SET payment_type = 'rent'
        WHERE payment_type = 'office'
    """)

    op.execute("""
        UPDATE expenses
        SET expense_type = 'rent'
        WHERE expense_type = 'office'
    """)


def downgrade():
    op.execute("""
        UPDATE payment_requests
        SET payment_type = 'office'
        WHERE payment_type = 'rent'
    """)

    op.execute("""
        UPDATE expenses
        SET expense_type = 'office'
        WHERE expense_type = 'rent'
    """)

