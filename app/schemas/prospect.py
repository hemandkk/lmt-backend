from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from app.db.models.prospect import ProspectStage
from app.db.models.payment import PaymentType


# --------------------------------------------------
# Payment
# --------------------------------------------------

class PaymentCreate(BaseModel):
    amount: Decimal
    payment_type: PaymentType
    payment_date: date
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class PaymentResponse(PaymentCreate):
    id: int
    payment_id: str

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------
# Document
# --------------------------------------------------

class DocumentResponse(BaseModel):
    id: int
    document_id: str
    document_type: str
    file_name: str
    file_url: str
    verified: bool

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------
# Create Prospect
# --------------------------------------------------

class ProspectCreate(BaseModel):

    name: str

    password: Optional[str] = None

    email: Optional[EmailStr] = None

    phone: Optional[str] = None

    father_name: Optional[str] = None

    mother_name: Optional[str] = None

    dob: Optional[date] = None

    course_id: Optional[int] = None

    specialization: Optional[str] = None

    address: Optional[str] = None

    delivery_address: Optional[str] = None

    delivery_date: Optional[date] = None

    estimated_deal_value: Decimal = Decimal("0")

    notes: Optional[str] = None

    assigned_to_id: Optional[int] = None

    payments: list[PaymentCreate] = []


# --------------------------------------------------
# Update Prospect
# --------------------------------------------------

class ProspectUpdate(BaseModel):

    name: Optional[str] = None

    password: Optional[str] = None

    email: Optional[EmailStr] = None

    phone: Optional[str] = None

    father_name: Optional[str] = None

    mother_name: Optional[str] = None

    dob: Optional[date] = None

    course_id: Optional[int] = None

    specialization: Optional[str] = None

    address: Optional[str] = None

    delivery_address: Optional[str] = None

    delivery_date: Optional[date] = None

    estimated_deal_value: Optional[Decimal] = None

    notes: Optional[str] = None

    stage: Optional[ProspectStage] = None

    assigned_to_id: Optional[int] = None

    exam_attended: Optional[bool] = None

    exam_certified: Optional[bool] = None


# --------------------------------------------------
# Response
# --------------------------------------------------

class ProspectResponse(BaseModel):

    id: int

    prospect_id: str

    name: str

    email: Optional[str]

    phone: Optional[str]

    father_name: Optional[str]

    mother_name: Optional[str]

    dob: Optional[date]

    stage: ProspectStage

    estimated_deal_value: Decimal

    address: Optional[str]

    delivery_address: Optional[str]

    delivery_date: Optional[date]

    notes: Optional[str]

    exam_attended: bool

    exam_certified: bool

    assigned_to_id: Optional[int]

    course_id: Optional[int]

    specialization: Optional[str]

    created_at: datetime

    updated_at: datetime

    payments: list[PaymentResponse] = []

    documents: list[DocumentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------
# Pagination
# --------------------------------------------------

class ProspectListResponse(BaseModel):

    items: list[ProspectResponse]

    total: int

    page: int

    page_size: int

    total_pages: int