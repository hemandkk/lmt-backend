from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.db.models.payment import (
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    PaymentVerificationStatus,
)


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


def coerce_payment_type(value: Any) -> Any:
    """Accept legacy / display aliases for PaymentType."""
    if isinstance(value, PaymentType) or not isinstance(value, str):
        return value
    raw = value.strip()
    snake = raw.replace("-", "_").replace(" ", "_").lower()
    aliases = {
        "final": PaymentType.full_payment,
        "full": PaymentType.full_payment,
        "full_payment": PaymentType.full_payment,
        "registration_fee": PaymentType.registration_fee,
        "registrationfee": PaymentType.registration_fee,
        "before_exam_fee": PaymentType.before_exam_fee,
        "beforeexamfee": PaymentType.before_exam_fee,
        "after_result_fee": PaymentType.after_result_fee,
        "afterresultfee": PaymentType.after_result_fee,
    }
    compact = snake.replace("_", "")
    if snake in aliases:
        return aliases[snake]
    if compact in aliases:
        return aliases[compact]
    return value


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
    def map_payment_type_aliases(cls, value):
        return coerce_payment_type(value)


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
    def map_payment_type_aliases(cls, value):
        return coerce_payment_type(value)


# -----------------------------
# Receipt Upload Response
# -----------------------------
class ReceiptUploadResponse(BaseModel):
    model_config = _alias_config()

    receipt_url: str = Field(..., alias="receiptUrl")


class PaymentVerificationUpdate(BaseModel):
    model_config = _alias_config()

    verification_status: PaymentVerificationStatus = Field(
        ...,
        alias="verificationStatus",
    )

    @field_validator("verification_status", mode="before")
    @classmethod
    def coerce_verification_status(cls, value: Any):
        if isinstance(value, PaymentVerificationStatus):
            return value
        if value is None:
            raise ValueError("verificationStatus is required")
        raw = str(value).strip()
        snake = raw.replace("-", "_").replace(" ", "_").lower()
        compact = snake.replace("_", "")
        aliases = {
            "verified": PaymentVerificationStatus.verified,
            "not_verified": PaymentVerificationStatus.not_verified,
            "notverified": PaymentVerificationStatus.not_verified,
            "not_credited": PaymentVerificationStatus.not_credited,
            "notcredited": PaymentVerificationStatus.not_credited,
        }
        if snake in aliases:
            return aliases[snake]
        if compact in aliases:
            return aliases[compact]
        return PaymentVerificationStatus(snake)


# -----------------------------
# Response
# -----------------------------
class PaymentResponse(PaymentBase):
    id: int

    payment_id: str = Field(..., alias="paymentId")

    receipt_url: Optional[str] = Field(default=None, alias="receiptUrl")

    verification_status: PaymentVerificationStatus = Field(
        default=PaymentVerificationStatus.not_verified,
        alias="verificationStatus",
        serialization_alias="verificationStatus",
    )
    verified_at: Optional[datetime] = Field(
        default=None,
        alias="verifiedAt",
        serialization_alias="verifiedAt",
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

    created_by: Optional[int] = Field(default=None, alias="createdBy")

    created_at: datetime = Field(..., alias="createdAt")

    updated_at: datetime = Field(..., alias="updatedAt")

    @model_validator(mode="wrap")
    @classmethod
    def pull_verifier_fields(cls, data: Any, handler):
        verifier_name = None
        if not isinstance(data, dict):
            verifier = getattr(data, "verified_by", None)
            if verifier is not None:
                verifier_name = verifier.name or verifier.email
        else:
            verifier_name = data.get("verified_by_name") or data.get(
                "verifiedByName"
            )

        result = handler(data)
        if verifier_name is not None:
            result.verified_by_name = verifier_name
        if result.verification_status is None:
            result.verification_status = PaymentVerificationStatus.not_verified
        return result

    @field_validator("verification_status", mode="before")
    @classmethod
    def default_verification(cls, value: Any):
        if value is None or value == "":
            return PaymentVerificationStatus.not_verified
        return value


# -----------------------------
# List Response
# -----------------------------
class PaymentListResponse(BaseModel):
    total: int

    items: list[PaymentResponse]


class PaymentTypeBreakdown(BaseModel):
    model_config = _alias_config()

    advance: Decimal = Decimal("0")
    installment: Decimal = Decimal("0")
    full_payment: Decimal = Field(
        default=Decimal("0"), serialization_alias="fullPayment"
    )
    registration_fee: Decimal = Field(
        default=Decimal("0"), serialization_alias="registrationFee"
    )
    before_exam_fee: Decimal = Field(
        default=Decimal("0"), serialization_alias="beforeExamFee"
    )
    after_result_fee: Decimal = Field(
        default=Decimal("0"), serialization_alias="afterResultFee"
    )


class PaymentStatusBreakdown(BaseModel):
    model_config = _alias_config()

    completed: Decimal = Decimal("0")
    pending: Decimal = Decimal("0")
    failed: Decimal = Decimal("0")


class PaymentCollectedBreakdown(BaseModel):
    model_config = _alias_config()

    today: Decimal = Decimal("0")
    this_week: Decimal = Field(default=Decimal("0"), serialization_alias="thisWeek")
    this_month: Decimal = Field(
        default=Decimal("0"), serialization_alias="thisMonth"
    )
    total: Decimal = Decimal("0")
    custom: Optional[Decimal] = None


class PaymentLeadStatusBreakdown(BaseModel):
    model_config = _alias_config()

    advanced_paid: int = Field(default=0, serialization_alias="advancedPaid")
    fifty_percent_paid: int = Field(
        default=0, serialization_alias="fiftyPercentPaid"
    )
    hundred_percent_paid: int = Field(
        default=0, serialization_alias="hundredPercentPaid"
    )


class PaymentSummaryResponse(BaseModel):
    model_config = _alias_config()

    total_collected: Decimal = Field(
        default=Decimal("0"), serialization_alias="totalCollected"
    )
    total_count: int = Field(default=0, serialization_alias="totalCount")
    collected: PaymentCollectedBreakdown
    by_type: PaymentTypeBreakdown = Field(serialization_alias="byType")
    by_status: PaymentStatusBreakdown = Field(serialization_alias="byStatus")
    lead_payment_status: PaymentLeadStatusBreakdown = Field(
        serialization_alias="leadPaymentStatus"
    )
