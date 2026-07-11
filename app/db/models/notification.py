import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class NotificationType(str, enum.Enum):
    lead_assigned = "lead_assigned"
    follow_up_reminder = "follow_up_reminder"
    stage_changed = "stage_changed"
    general = "general"


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    prospect_id = Column(
        Integer,
        ForeignKey("prospects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    type = Column(
        Enum(NotificationType),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=False)

    message = Column(Text, nullable=False)

    is_read = Column(Boolean, default=False, nullable=False, index=True)

    user = relationship("User", back_populates="notifications")
    prospect = relationship("Prospect")
