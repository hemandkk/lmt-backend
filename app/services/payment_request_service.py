from __future__ import annotations

from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id
from app.db.models.payment_request import PaymentRequest, PaymentRequestStatus
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.schemas.expense import ExpenseCreate
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestFulfill,
    PaymentRequestResponse,
    PaymentRequestUpdate,
)
from app.services.expense_service import ExpenseService


class PaymentRequestService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PaymentRequestRepository(db)

    @staticmethod
    def _user_name(user) -> str | None:
        if user is None:
            return None
        return user.name or user.email

    def _to_response(self, row: PaymentRequest) -> PaymentRequestResponse:
        expense_pk = None
        if row.expense is not None:
            expense_pk = row.expense.id
        approver_name = self._user_name(row.paid_by)
        data = {
            "id": row.id,
            "request_id": row.request_id,
            "description": row.description,
            "paid_to_details": row.paid_to_details,
            "amount": row.amount,
            "installment_number": row.installment_number,
            "status": row.status,
            "transaction_id": row.transaction_id,
            "receipt_url": row.receipt_url,
            "payment_date": row.payment_date,
            "paid_by_id": row.paid_by_id,
            "paid_by_name": approver_name,
            "approved_by_id": row.paid_by_id,
            "approved_by_name": approver_name,
            "paid_at": row.paid_at,
            "approved_at": row.paid_at,
            "verified_by_id": row.verified_by_id,
            "verified_by_name": self._user_name(row.verified_by),
            "verified_at": row.verified_at,
            "requested_by_id": row.requested_by_id,
            "requested_by_name": self._user_name(row.requested_by),
            "expense_id": expense_pk,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        return PaymentRequestResponse.model_validate(data)

    def create(
        self,
        payload: PaymentRequestCreate,
        actor_id: int | None = None,
    ) -> PaymentRequestResponse:
        code = generate_id(self.db, PaymentRequest, "request_id", "PRQ")
        row = PaymentRequest(
            request_id=code,
            description=payload.description,
            paid_to_details=payload.paid_to_details,
            amount=payload.amount,
            installment_number=payload.installment_number,
            status=PaymentRequestStatus.requested,
            requested_by_id=actor_id,
        )
        created = self.repo.create(row)
        return self._to_response(self.repo.get_by_id(created.id) or created)

    def get(self, request_id: int) -> PaymentRequestResponse:
        row = self.repo.get_by_id(request_id)
        if not row:
            raise ValueError("Payment request not found.")
        return self._to_response(row)

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: PaymentRequestStatus | None = None,
        date_from=None,
        date_to=None,
        search: str | None = None,
    ) -> dict:
        """All accountants and admins see every payment request (no user scope)."""
        skip = (page - 1) * page_size
        total, items = self.repo.list(
            skip=skip,
            limit=page_size,
            status=status,
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
        request_id: int,
        payload: PaymentRequestUpdate,
    ) -> PaymentRequestResponse:
        row = self.repo.get_by_id(request_id)
        if not row:
            raise ValueError("Payment request not found.")
        if row.status != PaymentRequestStatus.requested:
            raise ValueError(
                "Only requests in 'requested' status can be edited."
            )

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.update(row)
        return self._to_response(self.repo.get_by_id(updated.id) or updated)

    def fulfill(
        self,
        request_id: int,
        payload: PaymentRequestFulfill,
        actor_id: int,
        receipt_file: UploadFile | None = None,
    ) -> PaymentRequestResponse:
        row = self.repo.get_by_id(request_id)
        if not row:
            raise ValueError("Payment request not found.")
        if row.status != PaymentRequestStatus.requested:
            raise ValueError(
                "Only requests in 'requested' status can be fulfilled."
            )
        if not receipt_file or not receipt_file.filename:
            raise ValueError("Receipt upload is required.")

        receipt_url, _, _ = FileStorage.save_file(
            upload_file=receipt_file,
            folder=f"payment_requests/{row.request_id}",
            filename=f"{row.request_id}_receipt",
        )

        row.transaction_id = payload.transaction_id
        row.payment_date = payload.payment_date
        row.receipt_url = receipt_url
        row.status = PaymentRequestStatus.payment_done
        row.paid_by_id = actor_id
        row.paid_at = datetime.now(timezone.utc)

        updated = self.repo.update(row)
        return self._to_response(self.repo.get_by_id(updated.id) or updated)

    def verify(
        self,
        request_id: int,
        actor_id: int,
    ) -> PaymentRequestResponse:
        """
        Accountant verifies admin payment → status approved + auto expense.
        """
        row = self.repo.get_by_id(request_id)
        if not row:
            raise ValueError("Payment request not found.")
        if row.status != PaymentRequestStatus.payment_done:
            raise ValueError(
                "Only requests with status 'payment_done' can be verified."
            )
        if not row.payment_date or not row.transaction_id:
            raise ValueError("Payment details are incomplete.")

        from app.repositories.expense_repository import ExpenseRepository

        existing = ExpenseRepository(self.db).get_by_payment_request_id(row.id)
        if existing:
            raise ValueError("Expense already created for this request.")

        expense_payload = ExpenseCreate(
            expense_date=row.payment_date,
            description=row.description,
            amount=row.amount,
            paid_to=row.paid_to_details,
            transaction_id=row.transaction_id,
            installment_number=row.installment_number,
        )
        ExpenseService(self.db).create(
            payload=expense_payload,
            actor_id=actor_id,
            payment_request_id=row.id,
            receipt_url=row.receipt_url,
            requested_by_id=row.requested_by_id,
            approved_by_id=row.paid_by_id,
            verified_by_id=actor_id,
        )

        row.status = PaymentRequestStatus.approved
        row.verified_by_id = actor_id
        row.verified_at = datetime.now(timezone.utc)
        updated = self.repo.update(row)
        return self._to_response(self.repo.get_by_id(updated.id) or updated)

    def delete(self, request_id: int) -> None:
        row = self.repo.get_by_id(request_id)
        if not row:
            raise ValueError("Payment request not found.")
        if row.status == PaymentRequestStatus.approved:
            raise ValueError("Approved payment requests cannot be deleted.")
        if row.receipt_url:
            FileStorage.delete_file(row.receipt_url)
        self.repo.delete(row)
