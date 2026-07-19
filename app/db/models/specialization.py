from sqlalchemy import Boolean, Column, Integer, String, Text

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Specialization(TimestampMixin, Base):
    """
    Master list for lead specialization dropdown.
    Not FK-linked to prospects — lead stores the selected name as free text.
    """

    __tablename__ = "specializations"

    id = Column(Integer, primary_key=True)

    specialization_code = Column(
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

    description = Column(
        Text,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )
