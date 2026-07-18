from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.schemas.payment import PaymentUpdate


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_by_id(self, payment_id: int) -> Payment | None:
        return (
            self.db.query(Payment)
            .options(
                joinedload(Payment.prospect),
                joinedload(Payment.verified_by),
            )
            .filter(Payment.id == payment_id)
            .first()
        )

    def get_by_payment_id(self, payment_id: str) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(Payment.payment_id == payment_id)
            .first()
        )

    def get_by_prospect(self, prospect_id: int) -> list[Payment]:
        return (
            self.db.query(Payment)
            .options(joinedload(Payment.verified_by))
            .filter(Payment.prospect_id == prospect_id)
            .order_by(Payment.payment_date.desc())
            .all()
        )

    def list(
        self,
        skip: int = 0,
        limit: int = 20,
        assigned_to_id: int | None = None,
        prospect_id: int | None = None,
        admission_stages: list[str] | None = None,
    ) -> tuple[int, list[Payment]]:
        query = (
            self.db.query(Payment)
            .options(joinedload(Payment.verified_by))
            .join(Prospect, Prospect.id == Payment.prospect_id)
        )

        if assigned_to_id is not None:
            query = query.filter(Prospect.assigned_to_id == assigned_to_id)

        if prospect_id is not None:
            query = query.filter(Payment.prospect_id == prospect_id)

        if admission_stages:
            query = query.filter(Prospect.admission_stage.in_(admission_stages))

        total = query.count()
        items = (
            query.order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return total, items

    def update(self, payment: Payment, data: PaymentUpdate) -> Payment:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(payment, field, value)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def update_receipt(self, payment: Payment, receipt_url: str) -> Payment:
        payment.receipt_url = receipt_url
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_by_transaction_number(
        self, transaction_number: str
    ) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(Payment.transaction_number == transaction_number)
            .first()
        )

    def delete(self, payment: Payment) -> None:
        self.db.delete(payment)
        self.db.commit()

    def exists(self, payment_id: str) -> bool:
        return (
            self.db.query(Payment)
            .filter(Payment.payment_id == payment_id)
            .count()
            > 0
        )

    def summary_breakdown(
        self,
        assigned_to_id: int | None = None,
        prospect_id: int | None = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        from decimal import Decimal

        from app.db.models.payment import PaymentStatus, PaymentType

        query = self.db.query(Payment).join(
            Prospect, Prospect.id == Payment.prospect_id
        )
        if assigned_to_id is not None:
            query = query.filter(Prospect.assigned_to_id == assigned_to_id)
        if prospect_id is not None:
            query = query.filter(Payment.prospect_id == prospect_id)
        if date_from is not None:
            query = query.filter(Payment.payment_date >= date_from)
        if date_to is not None:
            query = query.filter(Payment.payment_date <= date_to)

        payments = query.all()
        by_type = {
            PaymentType.advance.value: Decimal("0"),
            PaymentType.installment.value: Decimal("0"),
            PaymentType.full.value: Decimal("0"),
        }
        by_status = {
            PaymentStatus.completed.value: Decimal("0"),
            PaymentStatus.pending.value: Decimal("0"),
            PaymentStatus.failed.value: Decimal("0"),
        }
        total_collected = Decimal("0")

        for payment in payments:
            amount = Decimal(str(payment.amount or 0))
            ptype = (
                payment.payment_type.value
                if hasattr(payment.payment_type, "value")
                else str(payment.payment_type)
            )
            pstatus = (
                payment.payment_status.value
                if hasattr(payment.payment_status, "value")
                else str(payment.payment_status)
            )
            if ptype in by_type:
                by_type[ptype] += amount
            if pstatus in by_status:
                by_status[pstatus] += amount
            if pstatus == PaymentStatus.completed.value:
                total_collected += amount

        return {
            "total_collected": total_collected,
            "total_count": len(payments),
            "by_type": by_type,
            "by_status": by_status,
        }
