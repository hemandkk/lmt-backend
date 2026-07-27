from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class State(TimestampMixin, Base):
    """Geographic state master (employees / branches belong to a state)."""

    __tablename__ = "states"

    id = Column(Integer, primary_key=True)

    state_code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
        unique=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    branches = relationship(
        "Branch",
        back_populates="state",
    )

    users = relationship(
        "User",
        back_populates="state",
        foreign_keys="User.state_id",
    )
