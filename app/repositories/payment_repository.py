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
            .options(joinedload(Payment.prospect))
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
    ) -> tuple[int, list[Payment]]:
        query = self.db.query(Payment).join(
            Prospect, Prospect.id == Payment.prospect_id
        )

        if assigned_to_id is not None:
            query = query.filter(Prospect.assigned_to_id == assigned_to_id)

        if prospect_id is not None:
            query = query.filter(Payment.prospect_id == prospect_id)

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
