from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
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
    PaymentUpdate,
    ReceiptUploadResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_prospect_access(db, payment.prospect_id, current_user)
    service = PaymentService(db)
    try:
        return service.create_payment(payment, current_user.id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


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
    """
    - Employee: only payments on their assigned prospects
    - Admin: all, or filter with employeeId / prospectId
    """
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)
    service = PaymentService(db)
    total, items = service.list_payments(
        skip=skip,
        limit=limit,
        assigned_to_id=scoped_employee_id,
        prospect_id=prospect_id,
    )
    return {"total": total, "items": items}


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
        raise HTTPException(status_code=400, detail=str(ex))


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
        raise HTTPException(status_code=404, detail=str(ex))


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
        raise HTTPException(status_code=400, detail=str(ex))
