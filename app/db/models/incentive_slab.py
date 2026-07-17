from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    Numeric,
)

from app.db.base import Base
from app.db.mixins import TimestampMixin


class IncentiveSlab(TimestampMixin, Base):
    """Lead-count incentive brackets, e.g. 10–15 leads → ₹500."""

    __tablename__ = "incentive_slabs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    min_leads = Column(
        Integer,
        nullable=False,
    )

    max_leads = Column(
        Integer,
        nullable=True,
    )

    incentive_amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )
