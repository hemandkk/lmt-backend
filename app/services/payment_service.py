from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.repositories.payment_repository import PaymentRepository
from app.repositories.prospect_repository import ProspectRepository
from app.schemas.payment import PaymentCreate, PaymentUpdate


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.payment_repo = PaymentRepository(db)

    def create_payment(
        self,
        payment_in: PaymentCreate,
        current_user_id: int,
        receipt_file: UploadFile | None = None,
    ) -> Payment:
        prospect = ProspectRepository.get_by_id(self.db, payment_in.prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        if payment_in.transaction_number:
            existing = self.payment_repo.get_by_transaction_number(
                payment_in.transaction_number
            )
            if existing:
                raise ValueError("Transaction number already exists.")

        payment_code = generate_id(self.db, Payment, "payment_id", "PAY")
        receipt_url = None

        if receipt_file and receipt_file.filename:
            receipt_url, _, _ = FileStorage.save_file(
                upload_file=receipt_file,
                folder=f"prospects/{prospect.prospect_id}/receipts",
                filename=payment_code,
            )

        payment = Payment(
            payment_id=payment_code,
            prospect_id=payment_in.prospect_id,
            amount=payment_in.amount,
            payment_type=payment_in.payment_type,
            payment_method=payment_in.payment_method,
            payment_status=payment_in.payment_status,
            payment_date=payment_in.payment_date,
            transaction_number=payment_in.transaction_number,
            reference_number=payment_in.reference_number,
            notes=payment_in.notes,
            receipt_url=receipt_url,
            created_by=current_user_id,
        )
        created = self.payment_repo.create(payment)
        self._sync_sheets(payment_in.prospect_id, current_user_id)
        return created

    def _sync_sheets(
        self, prospect_id: int, actor_id: int | None = None
    ) -> None:
        from app.services.google_sheets_service import GoogleSheetsService

        GoogleSheetsService.sync_prospect_by_id(
            self.db, prospect_id, actor_id=actor_id
        )

    def get_payment(self, payment_id: int) -> Payment | None:
        return self.payment_repo.get_by_id(payment_id)

    def list_payments(
        self,
        skip: int = 0,
        limit: int = 20,
        assigned_to_id: int | None = None,
        prospect_id: int | None = None,
    ):
        return self.payment_repo.list(
            skip=skip,
            limit=limit,
            assigned_to_id=assigned_to_id,
            prospect_id=prospect_id,
        )

    def get_payments_by_prospect(self, prospect_id: int):
        return self.payment_repo.get_by_prospect(prospect_id)

    def update_payment(
        self, payment_id: int, payment_in: PaymentUpdate
    ) -> Payment:
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise ValueError("Payment not found.")

        if payment_in.transaction_number:
            existing = self.payment_repo.get_by_transaction_number(
                payment_in.transaction_number
            )
            if existing and existing.id != payment.id:
                raise ValueError("Transaction number already exists.")

        updated = self.payment_repo.update(payment, payment_in)
        self._sync_sheets(updated.prospect_id)
        return updated

    def upload_receipt(
        self, payment_id: int, file: UploadFile
    ) -> Payment:
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise ValueError("Payment not found.")

        prospect = ProspectRepository.get_by_id(self.db, payment.prospect_id)
        folder = (
            f"prospects/{prospect.prospect_id}/receipts"
            if prospect
            else "payments"
        )

        if payment.receipt_url:
            receipt_url, _, _ = FileStorage.replace_file(
                old_file=payment.receipt_url,
                upload_file=file,
                folder=folder,
                filename=payment.payment_id,
            )
        else:
            receipt_url, _, _ = FileStorage.save_file(
                upload_file=file,
                folder=folder,
                filename=payment.payment_id,
            )

        updated = self.payment_repo.update_receipt(payment, receipt_url)
        self._sync_sheets(updated.prospect_id)
        return updated

    def delete_payment(self, payment_id: int) -> None:
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise ValueError("Payment not found.")
        prospect_id = payment.prospect_id
        if payment.receipt_url:
            FileStorage.delete_file(payment.receipt_url)
        self.payment_repo.delete(payment)
        self._sync_sheets(prospect_id)
