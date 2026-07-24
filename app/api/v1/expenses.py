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

from app.db.models.expense import ExpenseType
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.permissions import (
    require_expense_deleter,
    require_expense_manager,
)
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.services.expense_service import ExpenseService


def _parse_expense_type(raw: str | None) -> ExpenseType | None:
    if not raw:
        return None
    value = raw.strip().lower()
    try:
        return ExpenseType(value)
    except ValueError:
        return None

router = APIRouter(prefix="/expenses", tags=["Expenses"])


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


@router.post(
    "",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_expense_manager),
):
    content_type = (request.headers.get("content-type") or "").lower()
    receipt_file: UploadFile | None = None
    invoice_file: UploadFile | None = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload_data = {
                "expenseDate": _form_value(
                    form, "expenseDate", "expense_date", "date"
                ),
                "description": _form_value(form, "description"),
                "amount": _form_value(form, "amount"),
                "paidTo": _form_value(form, "paidTo", "paid_to"),
                "transactionId": _form_value(
                    form, "transactionId", "transaction_id"
                ),
                "installmentNumber": _form_value(
                    form, "installmentNumber", "installment_number"
                ),
                "expenseType": _form_value(
                    form, "expenseType", "expense_type"
                ),
                "employeeId": _form_value(
                    form, "employeeId", "employee_id"
                ),
            }
            receipt_file = _pick_upload(
                form, "receipt", "receiptFile", "receipt_file"
            )
            invoice_file = _pick_upload(
                form, "invoice", "invoiceFile", "invoice_file"
            )
            payload = ExpenseCreate.model_validate(payload_data)
        else:
            body = await request.json()
            payload = ExpenseCreate.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    if payload.expense_type == ExpenseType.incentive and not payload.employee_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="employeeId is required when expenseType is incentive.",
        )

    return ExpenseService(db).create(
        payload,
        actor_id=current_user.id,
        receipt_file=receipt_file,
        invoice_file=invoice_file,
    )


@router.get("", response_model=ExpenseListResponse)
def list_expenses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=200),
    date_from: date | None = Query(None, alias="dateFrom"),
    date_to: date | None = Query(None, alias="dateTo"),
    search: str | None = Query(None),
    expense_type: str | None = Query(
        None,
        alias="expenseType",
        description="office | incentive",
    ),
    employee_id: int | None = Query(
        None,
        alias="employeeId",
        description="Filter by employee (for incentive expenses)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_expense_manager),
):
    return ExpenseService(db).list(
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        search=search,
        expense_type=_parse_expense_type(expense_type),
        employee_id=employee_id,
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_expense_manager),
):
    try:
        return ExpenseService(db).get(expense_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_expense_manager),
):
    content_type = (request.headers.get("content-type") or "").lower()
    receipt_file: UploadFile | None = None
    invoice_file: UploadFile | None = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload_data = {}
            mapping = {
                "expenseDate": ("expenseDate", "expense_date", "date"),
                "description": ("description",),
                "amount": ("amount",),
                "paidTo": ("paidTo", "paid_to"),
                "transactionId": ("transactionId", "transaction_id"),
                "installmentNumber": (
                    "installmentNumber",
                    "installment_number",
                ),
            }
            for field, keys in mapping.items():
                value = _form_value(form, *keys)
                if value is not None:
                    payload_data[field] = value
            receipt_file = _pick_upload(
                form, "receipt", "receiptFile", "receipt_file"
            )
            invoice_file = _pick_upload(
                form, "invoice", "invoiceFile", "invoice_file"
            )
            payload = ExpenseUpdate.model_validate(payload_data)
        else:
            body = await request.json()
            payload = ExpenseUpdate.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    try:
        return ExpenseService(db).update(
            expense_id,
            payload,
            receipt_file=receipt_file,
            invoice_file=invoice_file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_expense_deleter),
):
    try:
        ExpenseService(db).delete(expense_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
