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


# -----------------------------
# Base Schema
# -----------------------------
class PaymentBase(BaseModel):
    prospect_id: int

    amount: Decimal = Field(..., gt=0)

    payment_type: PaymentType

    payment_method: PaymentMethod = PaymentMethod.cash

    payment_status: PaymentStatus = PaymentStatus.completed

    payment_date: date

    transaction_number: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    reference_number: Optional[str] = Field(
        default=None,
        max_length=100,
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
    amount: Optional[Decimal] = Field(default=None, gt=0)

    payment_type: Optional[PaymentType] = None

    payment_method: Optional[PaymentMethod] = None

    payment_status: Optional[PaymentStatus] = None

    payment_date: Optional[date] = None

    transaction_number: Optional[str] = None

    reference_number: Optional[str] = None

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
    receipt_url: str


# -----------------------------
# Response
# -----------------------------
class PaymentResponse(PaymentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

    payment_id: str

    receipt_url: Optional[str] = None

    created_by: Optional[int] = None

    created_at: datetime

    updated_at: datetime


# -----------------------------
# List Response
# -----------------------------
class PaymentListResponse(BaseModel):
    total: int

    items: list[PaymentResponse]