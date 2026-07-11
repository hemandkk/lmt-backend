from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    Numeric,
)

from app.db.base import Base
from app.db.mixins import TimestampMixin


class IncentiveSlab(TimestampMixin, Base):
    __tablename__ = "incentive_slabs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    min_amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    max_amount = Column(
        Numeric(12, 2),
        nullable=True,
    )

    rate_percent = Column(
        Numeric(5, 2),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )