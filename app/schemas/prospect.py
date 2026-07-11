from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.db.models.payment import PaymentMethod, PaymentStatus, PaymentType
from app.db.models.prospect import ProspectStage
from app.db.models.prospect_document import DocumentType


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


# --------------------------------------------------
# Payment (inline on lead form)
# --------------------------------------------------

class LeadPaymentInput(BaseModel):
    """Matches frontend payments[] on create/edit."""

    model_config = _alias_config()

    id: Optional[int] = None
    payment_code: Optional[str] = Field(default=None, alias="paymentId")
    amount: Decimal
    payment_date: date = Field(alias="paymentDate")
    payment_type: PaymentType = Field(alias="paymentType")
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.cash,
        alias="paymentMethod",
    )
    payment_status: PaymentStatus = Field(
        default=PaymentStatus.completed,
        alias="paymentStatus",
    )
    receipt_url: Optional[str] = Field(default=None, alias="receiptUrl")
    notes: Optional[str] = None
    transaction_number: Optional[str] = Field(
        default=None, alias="transactionNumber"
    )
    reference_number: Optional[str] = Field(
        default=None, alias="referenceNumber"
    )

    @field_validator("payment_type", mode="before")
    @classmethod
    def map_final_to_full(cls, value: Any) -> Any:
        # Frontend uses "final"; DB enum uses "full"
        if isinstance(value, str) and value.lower() == "final":
            return PaymentType.full
        return value


class PaymentResponse(BaseModel):
    model_config = _alias_config()

    id: int
    payment_id: str = Field(serialization_alias="paymentId")
    amount: Decimal
    payment_type: PaymentType = Field(serialization_alias="paymentType")
    payment_method: Optional[PaymentMethod] = Field(
        default=None, serialization_alias="paymentMethod"
    )
    payment_status: Optional[PaymentStatus] = Field(
        default=None, serialization_alias="paymentStatus"
    )
    payment_date: date = Field(serialization_alias="paymentDate")
    receipt_url: Optional[str] = Field(
        default=None, serialization_alias="receiptUrl"
    )
    notes: Optional[str] = None
    transaction_number: Optional[str] = Field(
        default=None, serialization_alias="transactionNumber"
    )
    reference_number: Optional[str] = Field(
        default=None, serialization_alias="referenceNumber"
    )


# --------------------------------------------------
# Document (inline metadata; files via multipart)
# --------------------------------------------------

class LeadDocumentInput(BaseModel):
    """Matches frontend documents[] metadata."""

    model_config = _alias_config()

    doc_type: DocumentType = Field(alias="docType")
    existing_url: Optional[str] = Field(default=None, alias="existingUrl")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    id: Optional[int] = None


class DocumentResponse(BaseModel):
    model_config = _alias_config()

    id: int
    document_id: str = Field(serialization_alias="documentId")
    document_type: DocumentType = Field(serialization_alias="docType")
    file_name: str = Field(serialization_alias="fileName")
    file_url: str = Field(serialization_alias="fileUrl")
    verified: bool = False
    existing_url: Optional[str] = Field(
        default=None, serialization_alias="existingUrl"
    )

    @model_validator(mode="before")
    @classmethod
    def from_orm_document(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        # SQLAlchemy ProspectDocument
        return {
            "id": data.id,
            "document_id": data.document_id,
            "document_type": data.document_type,
            "file_name": getattr(
                data, "original_filename", None
            )
            or getattr(data, "file_name", ""),
            "file_url": data.file_url,
            "verified": bool(getattr(data, "verified", False)),
            "existing_url": data.file_url,
        }


# --------------------------------------------------
# Create Prospect
# --------------------------------------------------

class ProspectCreate(BaseModel):
    """Lead add form — accepts snake_case or camelCase."""

    model_config = _alias_config()

    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    prospect_id: Optional[str] = Field(default=None, alias="prospectId")

    father_name: Optional[str] = Field(default=None, alias="fatherName")
    mother_name: Optional[str] = Field(default=None, alias="motherName")
    dob: Optional[date] = None

    course_id: Optional[int] = Field(default=None, alias="courseId")
    specialization: Optional[str] = None

    address: Optional[str] = None
    delivery_address: Optional[str] = Field(
        default=None, alias="deliveryAddress"
    )
    delivery_date: Optional[date] = Field(default=None, alias="deliveryDate")

    estimated_deal_value: Decimal = Field(
        default=Decimal("0"),
        alias="estimatedValue",
    )

    notes: Optional[str] = None
    assigned_to_id: Optional[int] = Field(
        default=None, alias="assignedToId"
    )
    source: Optional[str] = None
    follow_up_date: Optional[date] = Field(
        default=None, alias="followUpDate"
    )
    stage: Optional[ProspectStage] = None

    payments: list[LeadPaymentInput] = []
    documents: list[LeadDocumentInput] = []

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    @field_validator("course_id", mode="before")
    @classmethod
    def course_id_from_string(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value


# --------------------------------------------------
# Update Prospect
# --------------------------------------------------

class ProspectUpdate(BaseModel):
    model_config = _alias_config()

    name: Optional[str] = None
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    father_name: Optional[str] = Field(default=None, alias="fatherName")
    mother_name: Optional[str] = Field(default=None, alias="motherName")
    dob: Optional[date] = None

    course_id: Optional[int] = Field(default=None, alias="courseId")
    specialization: Optional[str] = None

    address: Optional[str] = None
    delivery_address: Optional[str] = Field(
        default=None, alias="deliveryAddress"
    )
    delivery_date: Optional[date] = Field(default=None, alias="deliveryDate")

    estimated_deal_value: Optional[Decimal] = Field(
        default=None, alias="estimatedValue"
    )

    notes: Optional[str] = None
    stage: Optional[ProspectStage] = None
    assigned_to_id: Optional[int] = Field(
        default=None, alias="assignedToId"
    )
    exam_attended: Optional[bool] = Field(
        default=None, alias="examAttended"
    )
    exam_certified: Optional[bool] = Field(
        default=None, alias="examCertified"
    )
    source: Optional[str] = None
    follow_up_date: Optional[date] = Field(
        default=None, alias="followUpDate"
    )

    payments: Optional[list[LeadPaymentInput]] = None
    documents: Optional[list[LeadDocumentInput]] = None
    # When true, payments not present in payload are deleted
    replace_payments: bool = Field(default=True, alias="replacePayments")

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    @field_validator("course_id", mode="before")
    @classmethod
    def course_id_from_string(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value


# --------------------------------------------------
# Response
# --------------------------------------------------

class ProspectResponse(BaseModel):
    model_config = _alias_config()

    id: int
    prospect_id: str = Field(serialization_alias="prospectId")
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None

    father_name: Optional[str] = Field(
        default=None, serialization_alias="fatherName"
    )
    mother_name: Optional[str] = Field(
        default=None, serialization_alias="motherName"
    )
    dob: Optional[date] = None
    stage: ProspectStage

    estimated_deal_value: Decimal = Field(
        serialization_alias="estimatedValue"
    )

    address: Optional[str] = None
    delivery_address: Optional[str] = Field(
        default=None, serialization_alias="deliveryAddress"
    )
    delivery_date: Optional[date] = Field(
        default=None, serialization_alias="deliveryDate"
    )
    notes: Optional[str] = None

    exam_attended: bool = Field(
        default=False, serialization_alias="examAttended"
    )
    exam_certified: bool = Field(
        default=False, serialization_alias="examCertified"
    )

    assigned_to_id: Optional[int] = Field(
        default=None, serialization_alias="assignedToId"
    )
    course_id: Optional[int] = Field(
        default=None, serialization_alias="courseId"
    )
    specialization: Optional[str] = None
    source: Optional[str] = None
    follow_up_date: Optional[date] = Field(
        default=None, serialization_alias="followUpDate"
    )

    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    payments: list[PaymentResponse] = []
    documents: list[DocumentResponse] = []

    @field_validator("exam_attended", "exam_certified", mode="before")
    @classmethod
    def coerce_bool(cls, value: Any) -> bool:
        return bool(value)


class ProspectListResponse(BaseModel):
    model_config = _alias_config()

    items: list[ProspectResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total_pages: int = Field(serialization_alias="totalPages")


# Backwards-compatible alias used by older payment inline create
PaymentCreate = LeadPaymentInput
