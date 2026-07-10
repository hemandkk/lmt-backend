from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)

    course_code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    specialization = Column(
        String(255),
        nullable=True,
    )

    duration = Column(
        String(100),
        nullable=True,
    )

    fees = Column(
        Integer,
        nullable=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    prospects = relationship(
        "Prospect",
        back_populates="course",
    )