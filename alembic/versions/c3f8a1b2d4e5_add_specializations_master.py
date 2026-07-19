"""add specializations master

Revision ID: c3f8a1b2d4e5
Revises: 60c499aa6558
Create Date: 2026-07-19 14:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f8a1b2d4e5"
down_revision: Union[str, Sequence[str], None] = "60c499aa6558"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "specializations" in inspector.get_table_names():
        return

    op.create_table(
        "specializations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("specialization_code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_specializations_specialization_code"),
        "specializations",
        ["specialization_code"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "specializations" not in inspector.get_table_names():
        return
    op.drop_index(
        op.f("ix_specializations_specialization_code"),
        table_name="specializations",
    )
    op.drop_table("specializations")
