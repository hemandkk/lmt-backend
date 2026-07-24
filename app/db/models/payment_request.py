from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class PaymentRequestStatus(str, enum.Enum):
    requested = "requested"
    payment_done = "payment_done"
    approved = "approved"


class PaymentRequest(TimestampMixin, Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)

    request_id: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)

    paid_to_details: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Account / UPI details to pay to",
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    installment_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[PaymentRequestStatus] = mapped_column(
        Enum(
            PaymentRequestStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
            length=30,
        ),
        default=PaymentRequestStatus.requested,
        nullable=False,
        index=True,
    )

    # Admin fulfillment fields
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    paid_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Accountant verification
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    requested_by = relationship("User", foreign_keys=[requested_by_id])
    paid_by = relationship("User", foreign_keys=[paid_by_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])
    expense = relationship(
        "Expense",
        back_populates="payment_request",
        uselist=False,
        foreign_keys="Expense.payment_request_id",
    )
