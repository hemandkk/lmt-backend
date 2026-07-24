from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.db.models.payment_request import PaymentRequest, PaymentRequestStatus


class PaymentRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, request: PaymentRequest) -> PaymentRequest:
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def get_by_id(self, request_pk: int) -> PaymentRequest | None:
        return (
            self.db.query(PaymentRequest)
            .options(
                joinedload(PaymentRequest.requested_by),
                joinedload(PaymentRequest.paid_by),
                joinedload(PaymentRequest.verified_by),
                joinedload(PaymentRequest.expense),
            )
            .filter(PaymentRequest.id == request_pk)
            .first()
        )

    def get_by_request_id(self, request_code: str) -> PaymentRequest | None:
        return (
            self.db.query(PaymentRequest)
            .filter(PaymentRequest.request_id == request_code)
            .first()
        )

    def list(
        self,
        skip: int = 0,
        limit: int = 20,
        status: PaymentRequestStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
    ) -> tuple[int, list[PaymentRequest]]:
        query = self.db.query(PaymentRequest).options(
            joinedload(PaymentRequest.requested_by),
            joinedload(PaymentRequest.paid_by),
            joinedload(PaymentRequest.verified_by),
            joinedload(PaymentRequest.expense),
        )

        if status is not None:
            query = query.filter(PaymentRequest.status == status)

        if date_from is not None:
            start = datetime.combine(
                date_from, time.min, tzinfo=timezone.utc
            )
            query = query.filter(PaymentRequest.created_at >= start)

        if date_to is not None:
            end = datetime.combine(
                date_to + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
            query = query.filter(PaymentRequest.created_at < end)

        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                (PaymentRequest.description.ilike(like))
                | (PaymentRequest.paid_to_details.ilike(like))
                | (PaymentRequest.request_id.ilike(like))
                | (PaymentRequest.transaction_id.ilike(like))
            )

        total = query.count()
        items = (
            query.order_by(PaymentRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return total, items

    def update(self, request: PaymentRequest) -> PaymentRequest:
        self.db.commit()
        self.db.refresh(request)
        return request

    def delete(self, request: PaymentRequest) -> None:
        self.db.delete(request)
        self.db.commit()
