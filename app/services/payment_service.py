from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment
from app.repositories.payment_repository import PaymentRepository
from app.repositories.prospect_repository import ProspectRepository
from app.schemas.payment import (
    PaymentCreate,
    PaymentUpdate,
)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.prospect_repo = ProspectRepository(db)

    async def _generate_payment_id(self) -> str:
        """
        Generates IDs like:
        PAY000001
        PAY000002
        """

        total, _ = await self.payment_repo.list(
            skip=0,
            limit=1,
        )

        return f"PAY{total + 1:06d}"

    async def create_payment(
        self,
        payment_in: PaymentCreate,
        current_user_id: int,
    ) -> Payment:

        prospect = await self.prospect_repo.get_by_id(
            payment_in.prospect_id
        )

        if not prospect:
            raise ValueError("Prospect not found.")

        if payment_in.transaction_number:

            existing = await self.payment_repo.get_by_transaction_number(
                payment_in.transaction_number
            )

            if existing:
                raise ValueError(
                    "Transaction number already exists."
                )

        payment = Payment(
            payment_id=await self._generate_payment_id(),
            prospect_id=payment_in.prospect_id,
            amount=payment_in.amount,
            payment_type=payment_in.payment_type,
            payment_method=payment_in.payment_method,
            payment_status=payment_in.payment_status,
            payment_date=payment_in.payment_date,
            transaction_number=payment_in.transaction_number,
            reference_number=payment_in.reference_number,
            notes=payment_in.notes,
            created_by=current_user_id,
        )

        return await self.payment_repo.create(
            payment=payment
        )

    async def get_payment(
        self,
        payment_id: int,
    ) -> Payment | None:

        return await self.payment_repo.get_by_id(
            payment_id
        )

    async def get_payment_by_code(
        self,
        payment_code: str,
    ) -> Payment | None:

        return await self.payment_repo.get_by_payment_id(
            payment_code
        )

    async def list_payments(
        self,
        skip: int = 0,
        limit: int = 20,
    ):

        return await self.payment_repo.list(
            skip=skip,
            limit=limit,
        )

    async def get_payments_by_prospect(
        self,
        prospect_id: int,
    ):

        return await self.payment_repo.get_by_prospect(
            prospect_id
        )

    async def update_payment(
        self,
        payment_id: int,
        payment_in: PaymentUpdate,
    ) -> Payment:

        payment = await self.payment_repo.get_by_id(
            payment_id
        )

        if not payment:
            raise ValueError("Payment not found.")

        if payment_in.transaction_number:

            existing = await self.payment_repo.get_by_transaction_number(
                payment_in.transaction_number
            )

            if (
                existing
                and existing.id != payment.id
            ):
                raise ValueError(
                    "Transaction number already exists."
                )

        return await self.payment_repo.update(
            payment,
            payment_in,
        )

    async def upload_receipt(
        self,
        payment_id: int,
        receipt_url: str,
    ) -> Payment:

        payment = await self.payment_repo.get_by_id(
            payment_id
        )

        if not payment:
            raise ValueError("Payment not found.")

        return await self.payment_repo.update_receipt(
            payment,
            receipt_url,
        )

    async def delete_payment(
        self,
        payment_id: int,
    ) -> None:

        payment = await self.payment_repo.get_by_id(
            payment_id
        )

        if not payment:
            raise ValueError("Payment not found.")

        await self.payment_repo.delete(
            payment
        )