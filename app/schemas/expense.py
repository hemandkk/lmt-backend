from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.expense import ExpenseType


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class ExpenseBase(BaseModel):
    model_config = _alias_config()

    expense_date: date = Field(..., alias="expenseDate")
    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    paid_to: str = Field(..., min_length=1, alias="paidTo")
    transaction_id: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="transactionId",
    )
    installment_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="installmentNumber",
    )
    expense_type: ExpenseType = Field(
        default=ExpenseType.office,
        alias="expenseType",
    )
    employee_id: Optional[int] = Field(
        default=None,
        alias="employeeId",
        description="Required when expenseType is incentive",
    )


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    model_config = _alias_config()

    expense_date: Optional[date] = Field(default=None, alias="expenseDate")
    description: Optional[str] = Field(default=None, min_length=1)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    paid_to: Optional[str] = Field(default=None, min_length=1, alias="paidTo")
    transaction_id: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="transactionId",
    )
    installment_number: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="installmentNumber",
    )


class ExpenseResponse(ExpenseBase):
    id: int
    expense_id: str = Field(..., alias="expenseId", serialization_alias="expenseId")
    employee_name: Optional[str] = Field(
        default=None,
        alias="employeeName",
        serialization_alias="employeeName",
    )
    receipt_url: Optional[str] = Field(
        default=None,
        alias="receiptUrl",
        serialization_alias="receiptUrl",
    )
    invoice_url: Optional[str] = Field(
        default=None,
        alias="invoiceUrl",
        serialization_alias="invoiceUrl",
    )
    payment_request_id: Optional[int] = Field(
        default=None,
        alias="paymentRequestId",
        serialization_alias="paymentRequestId",
    )
    created_by_id: Optional[int] = Field(
        default=None,
        alias="createdById",
        serialization_alias="createdById",
    )
    created_by_name: Optional[str] = Field(
        default=None,
        alias="createdByName",
        serialization_alias="createdByName",
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
    created_at: datetime = Field(..., alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt", serialization_alias="updatedAt")


class ExpenseListResponse(BaseModel):
    total: int
    items: list[ExpenseResponse]
