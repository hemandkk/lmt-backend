"""add user_branches for sales_head multi-branch assignment

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "user_branches" not in inspector.get_table_names():
        op.create_table(
            "user_branches",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["branch_id"], ["branches.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("user_id", "branch_id"),
        )
    # Backfill: existing sales_head primary branch → assigned set
    op.execute(
        """
        INSERT INTO user_branches (user_id, branch_id)
        SELECT id, branch_id
        FROM users
        WHERE role::text = 'sales_head'
          AND branch_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM user_branches ub
            WHERE ub.user_id = users.id AND ub.branch_id = users.branch_id
          )
        """
    )


def downgrade() -> None:
    op.drop_table("user_branches")
