from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.db.models.expense import Expense


class ExpenseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, expense: Expense) -> Expense:
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def get_by_id(self, expense_id: int) -> Expense | None:
        return (
            self.db.query(Expense)
            .options(
                joinedload(Expense.creator),
                joinedload(Expense.requester),
                joinedload(Expense.approver),
                joinedload(Expense.verifier),
            )
            .filter(Expense.id == expense_id)
            .first()
        )

    def get_by_expense_id(self, expense_code: str) -> Expense | None:
        return (
            self.db.query(Expense)
            .filter(Expense.expense_id == expense_code)
            .first()
        )

    def get_by_payment_request_id(
        self, payment_request_id: int
    ) -> Expense | None:
        return (
            self.db.query(Expense)
            .filter(Expense.payment_request_id == payment_request_id)
            .first()
        )

    def list(
        self,
        skip: int = 0,
        limit: int = 20,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
    ) -> tuple[int, list[Expense]]:
        query = self.db.query(Expense).options(
            joinedload(Expense.creator),
            joinedload(Expense.requester),
            joinedload(Expense.approver),
            joinedload(Expense.verifier),
        )

        if date_from is not None:
            query = query.filter(Expense.expense_date >= date_from)
        if date_to is not None:
            query = query.filter(Expense.expense_date <= date_to)
        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                (Expense.description.ilike(like))
                | (Expense.paid_to.ilike(like))
                | (Expense.transaction_id.ilike(like))
                | (Expense.expense_id.ilike(like))
            )

        total = query.count()
        items = (
            query.order_by(Expense.expense_date.desc(), Expense.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return total, items

    def update(self, expense: Expense) -> Expense:
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def delete(self, expense: Expense) -> None:
        self.db.delete(expense)
        self.db.commit()
