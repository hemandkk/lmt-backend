from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class PaymentType(str, enum.Enum):
    advance = "advance"
    installment = "installment"
    full = "full"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class PaymentMethod(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    card = "card"
    bank_transfer = "bank_transfer"
    cheque = "cheque"

class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_id: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType),
        nullable=False,
    )
    
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod),
        nullable=False,
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.completed,
        nullable=False,
        index=True,
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    receipt_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    transaction_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # Relationships
    prospect = relationship(
        "Prospect",
        back_populates="payments",
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )

    receipt_url: Mapped[str | None]

    transaction_number: Mapped[str | None]

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    # Bank/UPI reference number if different from transaction_number

    created_by: Mapped[int | None]

    notes: Mapped[str |None]