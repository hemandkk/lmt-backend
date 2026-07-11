from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.payment import (
    PaymentMethod,
    PaymentStatus,
    PaymentType,
)


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


# -----------------------------
# Base Schema
# -----------------------------
class PaymentBase(BaseModel):
    model_config = _alias_config()

    prospect_id: int = Field(..., alias="prospectId")

    amount: Decimal = Field(..., gt=0)

    payment_type: PaymentType = Field(..., alias="paymentType")

    payment_method: PaymentMethod = Field(
        default=PaymentMethod.cash,
        alias="paymentMethod",
    )

    payment_status: PaymentStatus = Field(
        default=PaymentStatus.completed,
        alias="paymentStatus",
    )

    payment_date: date = Field(..., alias="paymentDate")

    transaction_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="transactionNumber",
    )

    reference_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="referenceNumber",
    )

    notes: Optional[str] = None

    @field_validator("payment_type", mode="before")
    @classmethod
    def map_final_to_full(cls, value):
        if isinstance(value, str) and value.lower() == "final":
            return PaymentType.full
        return value


# -----------------------------
# Create
# -----------------------------
class PaymentCreate(PaymentBase):
    pass


# -----------------------------
# Update
# -----------------------------
class PaymentUpdate(BaseModel):
    model_config = _alias_config()

    amount: Optional[Decimal] = Field(default=None, gt=0)

    payment_type: Optional[PaymentType] = Field(
        default=None,
        alias="paymentType",
    )

    payment_method: Optional[PaymentMethod] = Field(
        default=None,
        alias="paymentMethod",
    )

    payment_status: Optional[PaymentStatus] = Field(
        default=None,
        alias="paymentStatus",
    )

    payment_date: Optional[date] = Field(
        default=None,
        alias="paymentDate",
    )

    transaction_number: Optional[str] = Field(
        default=None,
        alias="transactionNumber",
    )

    reference_number: Optional[str] = Field(
        default=None,
        alias="referenceNumber",
    )

    notes: Optional[str] = None

    @field_validator("payment_type", mode="before")
    @classmethod
    def map_final_to_full(cls, value):
        if isinstance(value, str) and value.lower() == "final":
            return PaymentType.full
        return value


# -----------------------------
# Receipt Upload Response
# -----------------------------
class ReceiptUploadResponse(BaseModel):
    model_config = _alias_config()

    receipt_url: str = Field(..., alias="receiptUrl")


# -----------------------------
# Response
# -----------------------------
class PaymentResponse(PaymentBase):
    id: int

    payment_id: str = Field(..., alias="paymentId")

    receipt_url: Optional[str] = Field(default=None, alias="receiptUrl")

    created_by: Optional[int] = Field(default=None, alias="createdBy")

    created_at: datetime = Field(..., alias="createdAt")

    updated_at: datetime = Field(..., alias="updatedAt")


# -----------------------------
# List Response
# -----------------------------
class PaymentListResponse(BaseModel):
    total: int

    items: list[PaymentResponse]
