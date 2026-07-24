from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id
from app.db.models.expense import Expense
from app.repositories.expense_repository import ExpenseRepository
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate


class ExpenseService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExpenseRepository(db)

    @staticmethod
    def _user_name(user) -> str | None:
        if user is None:
            return None
        return user.name or user.email

    def _to_response(self, expense: Expense) -> ExpenseResponse:
        data = {
            "id": expense.id,
            "expense_id": expense.expense_id,
            "expense_date": expense.expense_date,
            "description": expense.description,
            "amount": expense.amount,
            "paid_to": expense.paid_to,
            "transaction_id": expense.transaction_id,
            "installment_number": expense.installment_number,
            "receipt_url": expense.receipt_url,
            "invoice_url": expense.invoice_url,
            "payment_request_id": expense.payment_request_id,
            "created_by_id": expense.created_by_id,
            "created_by_name": self._user_name(expense.creator),
            "requested_by_id": expense.requested_by_id,
            "requested_by_name": self._user_name(expense.requester),
            "approved_by_id": expense.approved_by_id,
            "approved_by_name": self._user_name(expense.approver),
            "verified_by_id": expense.verified_by_id,
            "verified_by_name": self._user_name(expense.verifier),
            "created_at": expense.created_at,
            "updated_at": expense.updated_at,
        }
        return ExpenseResponse.model_validate(data)

    def create(
        self,
        payload: ExpenseCreate,
        actor_id: int | None = None,
        receipt_file: UploadFile | None = None,
        invoice_file: UploadFile | None = None,
        payment_request_id: int | None = None,
        receipt_url: str | None = None,
        invoice_url: str | None = None,
        requested_by_id: int | None = None,
        approved_by_id: int | None = None,
        verified_by_id: int | None = None,
    ) -> ExpenseResponse:
        code = generate_id(self.db, Expense, "expense_id", "EXP")

        if receipt_file and receipt_file.filename:
            receipt_url, _, _ = FileStorage.save_file(
                upload_file=receipt_file,
                folder=f"expenses/{code}",
                filename=f"{code}_receipt",
            )

        if invoice_file and invoice_file.filename:
            invoice_url, _, _ = FileStorage.save_file(
                upload_file=invoice_file,
                folder=f"expenses/{code}",
                filename=f"{code}_invoice",
            )

        expense = Expense(
            expense_id=code,
            expense_date=payload.expense_date,
            description=payload.description,
            amount=payload.amount,
            paid_to=payload.paid_to,
            transaction_id=payload.transaction_id,
            installment_number=payload.installment_number,
            receipt_url=receipt_url,
            invoice_url=invoice_url,
            payment_request_id=payment_request_id,
            created_by_id=actor_id,
            requested_by_id=requested_by_id,
            approved_by_id=approved_by_id,
            verified_by_id=verified_by_id,
        )
        created = self.repo.create(expense)
        return self._to_response(self.repo.get_by_id(created.id) or created)

    def get(self, expense_id: int) -> ExpenseResponse:
        expense = self.repo.get_by_id(expense_id)
        if not expense:
            raise ValueError("Expense not found.")
        return self._to_response(expense)

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        date_from=None,
        date_to=None,
        search: str | None = None,
    ) -> dict:
        """All accountants and admins see every expense (no user scope)."""
        skip = (page - 1) * page_size
        total, items = self.repo.list(
            skip=skip,
            limit=page_size,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )
        return {
            "total": total,
            "items": [self._to_response(item) for item in items],
        }

    def update(
        self,
        expense_id: int,
        payload: ExpenseUpdate,
        receipt_file: UploadFile | None = None,
        invoice_file: UploadFile | None = None,
    ) -> ExpenseResponse:
        expense = self.repo.get_by_id(expense_id)
        if not expense:
            raise ValueError("Expense not found.")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(expense, key, value)

        if receipt_file and receipt_file.filename:
            url, _, _ = FileStorage.replace_file(
                old_file=expense.receipt_url,
                upload_file=receipt_file,
                folder=f"expenses/{expense.expense_id}",
                filename=f"{expense.expense_id}_receipt",
            )
            expense.receipt_url = url

        if invoice_file and invoice_file.filename:
            url, _, _ = FileStorage.replace_file(
                old_file=expense.invoice_url,
                upload_file=invoice_file,
                folder=f"expenses/{expense.expense_id}",
                filename=f"{expense.expense_id}_invoice",
            )
            expense.invoice_url = url

        updated = self.repo.update(expense)
        return self._to_response(self.repo.get_by_id(updated.id) or updated)

    def delete(self, expense_id: int) -> None:
        expense = self.repo.get_by_id(expense_id)
        if not expense:
            raise ValueError("Expense not found.")
        if expense.receipt_url:
            FileStorage.delete_file(expense.receipt_url)
        if expense.invoice_url:
            FileStorage.delete_file(expense.invoice_url)
        self.repo.delete(expense)
