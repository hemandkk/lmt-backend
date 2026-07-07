from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Enum,
    Text,
    Boolean,
)

from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin

import enum


class DocumentType(str, enum.Enum):
    aadhaar = "aadhaar"
    sslc = "sslc"
    plus_two = "plus_two"
    degree = "degree"
    agreement = "agreement"
    passport = "passport"
    photo = "photo"
    receipt = "receipt"
    other = "other"


class ProspectDocument(TimestampMixin, Base):

    __tablename__ = "prospect_documents"

    id = Column(Integer, primary_key=True)

    document_id = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    prospect_id = Column(
        Integer,
        ForeignKey("prospects.id"),
        nullable=False,
    )

    document_type = Column(
        Enum(DocumentType),
        nullable=False,
    )

    original_filename = Column(
        String(255),
        nullable=False,
    )

    stored_filename = Column(
        String(255),
        nullable=False,
        unique=True,
    )

    file_url = Column(
        String(500),
        nullable=False,
    )

    mime_type = Column(
        String(100),
    )

    file_size = Column(
        Integer,
    )

    remarks = Column(Text)

    verified = Column(
        Boolean,
        default=False,
    )

    prospect = relationship(
        "Prospect",
        back_populates="documents",
    )