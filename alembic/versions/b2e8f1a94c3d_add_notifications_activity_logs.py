"""Add notifications, activity logs, and prospect source/follow_up fields.

Revision ID: b2e8f1a94c3d
Revises: 80472cc41c00
Create Date: 2026-07-12 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2e8f1a94c3d"
down_revision: Union[str, Sequence[str], None] = "80472cc41c00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prospects",
        sa.Column("source", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "prospects",
        sa.Column("follow_up_date", sa.Date(), nullable=True),
    )
    op.create_index(
        op.f("ix_prospects_source"),
        "prospects",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prospects_follow_up_date"),
        "prospects",
        ["follow_up_date"],
        unique=False,
    )

    notification_type = sa.Enum(
        "lead_assigned",
        "follow_up_reminder",
        "stage_changed",
        "general",
        name="notificationtype",
    )
    notification_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("prospect_id", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "lead_assigned",
                "follow_up_reminder",
                "stage_changed",
                "general",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"])
    op.create_index(op.f("ix_notifications_prospect_id"), "notifications", ["prospect_id"])
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"])
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"])

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("prospect_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("meta_data", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_user_id"), "activity_logs", ["user_id"])
    op.create_index(op.f("ix_activity_logs_prospect_id"), "activity_logs", ["prospect_id"])
    op.create_index(op.f("ix_activity_logs_action"), "activity_logs", ["action"])
    op.create_index(op.f("ix_activity_logs_entity_type"), "activity_logs", ["entity_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_activity_logs_entity_type"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_action"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_prospect_id"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_user_id"), table_name="activity_logs")
    op.drop_table("activity_logs")

    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_prospect_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")

    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_prospects_follow_up_date"), table_name="prospects")
    op.drop_index(op.f("ix_prospects_source"), table_name="prospects")
    op.drop_column("prospects", "follow_up_date")
    op.drop_column("prospects", "source")
