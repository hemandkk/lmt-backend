from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import (
    ensure_payment_access,
    ensure_prospect_access,
    resolve_employee_scope,
)
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    PaymentUpdate,
    ReceiptUploadResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


def _is_upload(value: Any) -> bool:
    return hasattr(value, "filename") and hasattr(value, "file")


def _form_value(form, *keys: str) -> Any:
    for key in keys:
        value = form.get(key)
        if value is not None and value != "":
            return value
    return None


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content_type = (request.headers.get("content-type") or "").lower()
    receipt_file: UploadFile | None = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload = {
                "prospectId": _form_value(form, "prospectId", "prospect_id"),
                "amount": _form_value(form, "amount"),
                "paymentType": _form_value(
                    form, "paymentType", "payment_type"
                ),
                "paymentMethod": _form_value(
                    form, "paymentMethod", "payment_method"
                ),
                "paymentStatus": _form_value(
                    form, "paymentStatus", "payment_status"
                ),
                "paymentDate": _form_value(
                    form, "paymentDate", "payment_date"
                ),
                "transactionNumber": _form_value(
                    form, "transactionNumber", "transaction_number"
                ),
                "referenceNumber": _form_value(
                    form, "referenceNumber", "reference_number"
                ),
                "notes": _form_value(form, "notes"),
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            for name, value in form.multi_items():
                if not _is_upload(value) or not value.filename:
                    continue
                if name in ("receipt", "file", "receiptFile") or name.startswith(
                    "receipt"
                ):
                    receipt_file = value
                    break

            payment = PaymentCreate.model_validate(payload)
        else:
            payment = PaymentCreate.model_validate(await request.json())
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors()) from ex

    ensure_prospect_access(db, payment.prospect_id, current_user)
    service = PaymentService(db)
    try:
        return service.create_payment(
            payment,
            current_user.id,
            receipt_file=receipt_file,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("", response_model=PaymentListResponse)
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    employee_id: int | None = Query(
        None,
        alias="employeeId",
        description="Admin only: filter payments by assignee",
    ),
    prospect_id: int | None = Query(None, alias="prospectId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)
    service = PaymentService(db)
    total, items = service.list_payments(
        skip=skip,
        limit=limit,
        assigned_to_id=scoped_employee_id,
        prospect_id=prospect_id,
    )
    return {"total": total, "items": items}


@router.get("/summary", response_model=PaymentSummaryResponse)
def payments_summary(
    date_from: date | None = Query(None, alias="dateFrom"),
    date_to: date | None = Query(None, alias="dateTo"),
    employee_id: int | None = Query(None, alias="employeeId"),
    prospect_id: int | None = Query(None, alias="prospectId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Payment KPIs. Declared before /{payment_id} so 'summary' is not treated as an id.
    """
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)
    if prospect_id is not None:
        ensure_prospect_access(db, prospect_id, current_user)

    return PaymentService(db).get_summary(
        assigned_to_id=scoped_employee_id,
        prospect_id=prospect_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/prospect/{prospect_id}", response_model=list[PaymentResponse])
def get_prospect_payments(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_prospect_access(db, prospect_id, current_user)
    return PaymentService(db).get_payments_by_prospect(prospect_id)


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = PaymentService(db).get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")
    ensure_payment_access(db, payment, current_user)
    return payment


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(
    payment_id: int,
    payment: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = PaymentService(db).get_payment(payment_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found.")
    ensure_payment_access(db, existing, current_user)
    try:
        return PaymentService(db).update_payment(payment_id, payment)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = PaymentService(db).get_payment(payment_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found.")
    ensure_payment_access(db, existing, current_user)
    try:
        PaymentService(db).delete_payment(payment_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.post(
    "/{payment_id}/receipt",
    response_model=ReceiptUploadResponse,
)
def upload_receipt(
    payment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = PaymentService(db).get_payment(payment_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found.")
    ensure_payment_access(db, existing, current_user)
    try:
        payment = PaymentService(db).upload_receipt(payment_id, file)
        return ReceiptUploadResponse(receipt_url=payment.receipt_url)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
