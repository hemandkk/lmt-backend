"""add states, branches, and user state/branch FKs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("state_code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_states_state_code", "states", ["state_code"])

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.ForeignKeyConstraint(["state_id"], ["states.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("branch_code"),
    )
    op.create_index("ix_branches_branch_code", "branches", ["branch_code"])
    op.create_index("ix_branches_state_id", "branches", ["state_id"])

    op.add_column("users", sa.Column("state_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_state_id", "users", ["state_id"])
    op.create_index("ix_users_branch_id", "users", ["branch_id"])
    op.create_foreign_key(
        "fk_users_state_id_states",
        "users",
        "states",
        ["state_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_users_branch_id_branches",
        "users",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_branch_id_branches", "users", type_="foreignkey")
    op.drop_constraint("fk_users_state_id_states", "users", type_="foreignkey")
    op.drop_index("ix_users_branch_id", table_name="users")
    op.drop_index("ix_users_state_id", table_name="users")
    op.drop_column("users", "branch_id")
    op.drop_column("users", "state_id")
    op.drop_index("ix_branches_state_id", table_name="branches")
    op.drop_index("ix_branches_branch_code", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_states_state_code", table_name="states")
    op.drop_table("states")
