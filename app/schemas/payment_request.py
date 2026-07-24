from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.payment_request import PaymentRequestStatus, PaymentRequestType


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class PaymentRequestCreate(BaseModel):
    model_config = _alias_config()

    description: str = Field(..., min_length=1)
    paid_to_details: str = Field(
        ...,
        min_length=1,
        alias="paidToDetails",
        description="Account / UPI details",
    )
    amount: Decimal = Field(..., gt=0)
    installment_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="installmentNumber",
    )
    payment_type: PaymentRequestType = Field(
        default=PaymentRequestType.office,
        alias="paymentType",
    )
    employee_id: Optional[int] = Field(
        default=None,
        alias="employeeId",
        description="Required when paymentType is incentive",
    )


class PaymentRequestUpdate(BaseModel):
    """Accountant may edit while still in requested status."""

    model_config = _alias_config()

    description: Optional[str] = Field(default=None, min_length=1)
    paid_to_details: Optional[str] = Field(
        default=None,
        min_length=1,
        alias="paidToDetails",
    )
    amount: Optional[Decimal] = Field(default=None, gt=0)
    installment_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="installmentNumber",
    )


class PaymentRequestFulfill(BaseModel):
    """Admin marks payment done with transaction details."""

    model_config = _alias_config()

    transaction_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        alias="transactionId",
    )
    payment_date: date = Field(..., alias="paymentDate")


class PaymentRequestResponse(BaseModel):
    model_config = _alias_config()

    id: int
    request_id: str = Field(..., alias="requestId", serialization_alias="requestId")
    description: str
    paid_to_details: str = Field(
        ...,
        alias="paidToDetails",
        serialization_alias="paidToDetails",
    )
    amount: Decimal
    installment_number: Optional[str] = Field(
        default=None,
        alias="installmentNumber",
        serialization_alias="installmentNumber",
    )
    payment_type: PaymentRequestType = Field(
        default=PaymentRequestType.office,
        alias="paymentType",
        serialization_alias="paymentType",
    )
    employee_id: Optional[int] = Field(
        default=None,
        alias="employeeId",
        serialization_alias="employeeId",
    )
    employee_name: Optional[str] = Field(
        default=None,
        alias="employeeName",
        serialization_alias="employeeName",
    )
    status: PaymentRequestStatus
    transaction_id: Optional[str] = Field(
        default=None,
        alias="transactionId",
        serialization_alias="transactionId",
    )
    receipt_url: Optional[str] = Field(
        default=None,
        alias="receiptUrl",
        serialization_alias="receiptUrl",
    )
    payment_date: Optional[date] = Field(
        default=None,
        alias="paymentDate",
        serialization_alias="paymentDate",
    )
    paid_by_id: Optional[int] = Field(
        default=None,
        alias="paidById",
        serialization_alias="paidById",
    )
    paid_by_name: Optional[str] = Field(
        default=None,
        alias="paidByName",
        serialization_alias="paidByName",
    )
    # Alias of admin fulfiller (same as paidBy*) for UI wording
    approved_by_id: Optional[int] = Field(
        default=None,
        alias="approvedById",
        serialization_alias="approvedById",
    )
    approved_by_name: Optional[str] = Field(
        default=None,
        alias="approvedByName",
        serialization_alias="approvedByName",
    )
    paid_at: Optional[datetime] = Field(
        default=None,
        alias="paidAt",
        serialization_alias="paidAt",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        alias="approvedAt",
        serialization_alias="approvedAt",
    )
    verified_by_id: Optional[int] = Field(
        default=None,
        alias="verifiedById",
        serialization_alias="verifiedById",
    )
    verified_by_name: Optional[str] = Field(
        default=None,
        alias="verifiedByName",
        serialization_alias="verifiedByName",
    )
    verified_at: Optional[datetime] = Field(
        default=None,
        alias="verifiedAt",
        serialization_alias="verifiedAt",
    )
    requested_by_id: Optional[int] = Field(
        default=None,
        alias="requestedById",
        serialization_alias="requestedById",
    )
    requested_by_name: Optional[str] = Field(
        default=None,
        alias="requestedByName",
        serialization_alias="requestedByName",
    )
    expense_id: Optional[int] = Field(
        default=None,
        alias="expenseId",
        serialization_alias="expenseId",
    )
    created_at: datetime = Field(..., alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt", serialization_alias="updatedAt")

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, value: Any):
        if isinstance(value, PaymentRequestStatus):
            return value
        if value is None:
            return PaymentRequestStatus.requested
        raw = str(value).strip().replace("-", "_").replace(" ", "_").lower()
        aliases = {
            "requested": PaymentRequestStatus.requested,
            "payment_done": PaymentRequestStatus.payment_done,
            "paymentdone": PaymentRequestStatus.payment_done,
            "approved": PaymentRequestStatus.approved,
        }
        compact = raw.replace("_", "")
        if raw in aliases:
            return aliases[raw]
        if compact in aliases:
            return aliases[compact]
        return PaymentRequestStatus(raw)


class PaymentRequestListResponse(BaseModel):
    total: int
    items: list[PaymentRequestResponse]
