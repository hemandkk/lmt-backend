import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    Numeric,
    Date,
    DateTime,
    Enum,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class ProspectStage(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    follow_up = "follow_up"
    interested = "interested"
    negotiation = "negotiation"
    won = "won"
    lost = "lost"


class Prospect(TimestampMixin, Base):

    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True)

    prospect_id = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    # Personal Details

    name = Column(
        String(255),
        nullable=False,
    )

    password = Column(
        String(100),
        nullable=True,
    )

    email = Column(
        String(255),
        nullable=True,
        index=True,
    )

    phone = Column(
        String(20),
        nullable=True,
    )

    dob = Column(
        Date,
        nullable=True,
    )

    father_name = Column(
        String(255),
        nullable=True,
    )

    mother_name = Column(
        String(255),
        nullable=True,
    )

    # Course

    course_id = Column(
        Integer,
        ForeignKey("courses.id"),
        nullable=True,
    )

    specialization = Column(
        String(255),
        nullable=True,
    )

    # Address

    address = Column(
        Text,
        nullable=True,
    )

    delivery_address = Column(
        Text,
        nullable=True,
    )

    delivery_date = Column(
        Date,
        nullable=True,
    )

    # CRM

    estimated_deal_value = Column(
        Numeric(12, 2),
        default=0,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    stage = Column(
        Enum(ProspectStage),
        default=ProspectStage.new,
        nullable=False,
        index=True,
    )

    source = Column(
        String(100),
        nullable=True,
        index=True,
    )

    follow_up_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    assigned_to_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    # Exam

    exam_attended = Column(
        Boolean,
        default=False,
    )

    exam_certified = Column(
        Boolean,
        default=False,
    )

    # Google Sheets

    sheets_synced = Column(
        Boolean,
        default=False,
    )

    sheets_row_id = Column(
        String(50),
        nullable=True,
    )

    # Relationships

    assigned_to = relationship(
        "User",
        back_populates="prospects",
    )

    course = relationship(
        "Course",
        back_populates="prospects",
    )

    payments = relationship(
        "Payment",
        back_populates="prospect",
        cascade="all, delete-orphan",
    )

    documents = relationship(
        "ProspectDocument",
        back_populates="prospect",
        cascade="all, delete-orphan",
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
