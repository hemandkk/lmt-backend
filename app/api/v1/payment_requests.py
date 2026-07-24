from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.roles import is_admin
from app.db.models.payment_request import PaymentRequestStatus
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.permissions import (
    require_payment_request_fulfiller,
    require_payment_request_manager,
)
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestFulfill,
    PaymentRequestListResponse,
    PaymentRequestResponse,
    PaymentRequestUpdate,
)
from app.services.payment_request_service import PaymentRequestService

router = APIRouter(prefix="/payment-requests", tags=["Payment Requests"])


def _is_upload(value: Any) -> bool:
    return hasattr(value, "filename") and hasattr(value, "file")


def _form_value(form, *keys: str) -> Any:
    for key in keys:
        value = form.get(key)
        if value is not None and value != "":
            return value
    return None


def _pick_upload(form, *keys: str) -> UploadFile | None:
    for key in keys:
        value = form.get(key)
        if _is_upload(value) and getattr(value, "filename", None):
            return value  # type: ignore[return-value]
    return None


def _parse_status(raw: str | None) -> PaymentRequestStatus | None:
    if not raw:
        return None
    value = raw.strip().replace("-", "_").replace(" ", "_").lower()
    aliases = {
        "requested": PaymentRequestStatus.requested,
        "payment_done": PaymentRequestStatus.payment_done,
        "paymentdone": PaymentRequestStatus.payment_done,
        "approved": PaymentRequestStatus.approved,
    }
    compact = value.replace("_", "")
    if value in aliases:
        return aliases[value]
    if compact in aliases:
        return aliases[compact]
    try:
        return PaymentRequestStatus(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Use: requested, payment_done, approved."
            ),
        ) from exc


@router.post(
    "",
    response_model=PaymentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_request(
    payload: PaymentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    return PaymentRequestService(db).create(
        payload, actor_id=current_user.id
    )


@router.get("", response_model=PaymentRequestListResponse)
def list_payment_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=200),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="requested | payment_done | approved",
    ),
    date_from: date | None = Query(None, alias="dateFrom"),
    date_to: date | None = Query(None, alias="dateTo"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    return PaymentRequestService(db).list(
        page=page,
        page_size=page_size,
        status=_parse_status(status_filter),
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


@router.get("/{request_id}", response_model=PaymentRequestResponse)
def get_payment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    try:
        return PaymentRequestService(db).get(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{request_id}", response_model=PaymentRequestResponse)
def update_payment_request(
    request_id: int,
    payload: PaymentRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    try:
        return PaymentRequestService(db).update(request_id, payload)
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc


@router.post(
    "/{request_id}/fulfill",
    response_model=PaymentRequestResponse,
)
async def fulfill_payment_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_fulfiller),
):
    """Admin marks payment done: transactionId, paymentDate, receipt."""
    content_type = (request.headers.get("content-type") or "").lower()
    receipt_file: UploadFile | None = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload = PaymentRequestFulfill.model_validate(
                {
                    "transactionId": _form_value(
                        form, "transactionId", "transaction_id"
                    ),
                    "paymentDate": _form_value(
                        form, "paymentDate", "payment_date", "date"
                    ),
                }
            )
            receipt_file = _pick_upload(
                form, "receipt", "receiptFile", "receipt_file"
            )
        else:
            body = await request.json()
            payload = PaymentRequestFulfill.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    try:
        return PaymentRequestService(db).fulfill(
            request_id,
            payload,
            actor_id=current_user.id,
            receipt_file=receipt_file,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc


@router.post(
    "/{request_id}/verify",
    response_model=PaymentRequestResponse,
)
def verify_payment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    """
    Accountant verifies admin payment against statement.
    On success: status → approved and expense is auto-created.
    """
    try:
        return PaymentRequestService(db).verify(
            request_id, actor_id=current_user.id
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payment_request_manager),
):
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin may delete payment requests.",
        )
    try:
        PaymentRequestService(db).delete(request_id)
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
