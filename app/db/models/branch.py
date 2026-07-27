from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Branch(TimestampMixin, Base):
    """Branch under a state. Employees belong to a branch."""

    __tablename__ = "branches"

    id = Column(Integer, primary_key=True)

    branch_code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    state_id = Column(
        Integer,
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    state = relationship(
        "State",
        back_populates="branches",
    )

    users = relationship(
        "User",
        back_populates="branch",
        foreign_keys="User.branch_id",
    )
