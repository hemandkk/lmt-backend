from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        payment: Payment,
    ) -> Payment:
        self.db.add(payment)
        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    async def get_by_id(
        self,
        payment_id: int,
    ) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_payment_id(
        self,
        payment_id: str,
    ) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_prospect(
        self,
        prospect_id: int,
    ) -> list[Payment]:
        result = await self.db.execute(
            select(Payment)
            .where(Payment.prospect_id == prospect_id)
            .order_by(Payment.payment_date.desc())
        )
        return list(result.scalars().all())

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[Payment]]:
        total = await self.db.scalar(
            select(func.count()).select_from(Payment)
        )

        result = await self.db.execute(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return total or 0, list(result.scalars().all())

    async def update(
        self,
        payment: Payment,
        data: PaymentUpdate,
    ) -> Payment:
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(payment, field, value)

        await self.db.flush()
        await self.db.refresh(payment)

        return payment

    async def update_receipt(
        self,
        payment: Payment,
        receipt_url: str,
    ) -> Payment:
        payment.receipt_url = receipt_url

        await self.db.flush()
        await self.db.refresh(payment)

        return payment

    async def get_by_transaction_number(
        self,
        transaction_number: str,
    ) -> Payment | None:

        result = await self.db.execute(
            select(Payment).where(
                Payment.transaction_number == transaction_number
            )
        )

        return result.scalar_one_or_none()


    async def delete(
        self,
        payment: Payment,
    ) -> None:
        await self.db.delete(payment)
        await self.db.flush()

    async def exists(
        self,
        payment_id: str,
    ) -> bool:
        result = await self.db.scalar(
            select(func.count())
            .select_from(Payment)
            .where(Payment.payment_id == payment_id)
        )

        return (result or 0) > 0