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
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin

from app.db.models.user import User
from app.db.session import get_db
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
async def create_payment(
    payment: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    try:
        return await service.create_payment(
            payment,
            current_user.id,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )


@router.get(
    "",
    response_model=PaymentListResponse,
)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    total, items = await service.list_payments(
        skip,
        limit,
    )

    return {
        "total": total,
        "items": items,
    }


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    payment = await service.get_payment(
        payment_id,
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    return payment


@router.get(
    "/prospect/{prospect_id}",
    response_model=list[PaymentResponse],
)
async def get_prospect_payments(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    return await service.get_payments_by_prospect(
        prospect_id,
    )


@router.put(
    "/{payment_id}",
    response_model=PaymentResponse,
)
async def update_payment(
    payment_id: int,
    payment: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    try:
        return await service.update_payment(
            payment_id,
            payment,
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )


@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)

    try:
        await service.delete_payment(payment_id)
    except ValueError as ex:
        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


@router.post(
    "/{payment_id}/receipt",
    response_model=ReceiptUploadResponse,
)
async def upload_receipt(
    payment_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Temporary implementation.

    When S3/MinIO/local storage service is implemented,
    replace this section with the FileService.
    """

    filename = file.filename or "receipt"

    receipt_url = f"/uploads/payments/{filename}"

    service = PaymentService(db)

    try:
        payment = await service.upload_receipt(
            payment_id,
            receipt_url,
        )

        return ReceiptUploadResponse(
            receipt_url=payment.receipt_url,
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )