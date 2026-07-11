from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class ActivityLog(TimestampMixin, Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    prospect_id = Column(
        Integer,
        ForeignKey("prospects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = Column(String(100), nullable=False, index=True)

    entity_type = Column(String(50), nullable=False, index=True)

    entity_id = Column(Integer, nullable=True)

    description = Column(Text, nullable=False)

    meta_data = Column(Text, nullable=True)

    user = relationship("User", back_populates="activity_logs")
    prospect = relationship("Prospect")
