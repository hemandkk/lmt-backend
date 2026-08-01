from sqlalchemy import Boolean, Column, Integer, String

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Designation(TimestampMixin, Base):
    """
    Master list for employee designation dropdown.
    Not FK-linked to users — user stores the selected name as free text.
    """

    __tablename__ = "designations"

    id = Column(Integer, primary_key=True)

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
