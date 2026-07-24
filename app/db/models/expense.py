from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Expense(TimestampMixin, Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)

    expense_id: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    paid_to: Mapped[str] = mapped_column(Text, nullable=False)

    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    installment_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    # Who recorded this expense (manual create or verify action)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # Copied from linked payment request when auto-created
    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # Admin who fulfilled / paid the linked request
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # Accountant who verified the payment (statement check)
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    creator = relationship("User", foreign_keys=[created_by_id])
    requester = relationship("User", foreign_keys=[requested_by_id])
    approver = relationship("User", foreign_keys=[approved_by_id])
    verifier = relationship("User", foreign_keys=[verified_by_id])
    payment_request = relationship(
        "PaymentRequest",
        back_populates="expense",
        foreign_keys=[payment_request_id],
    )
