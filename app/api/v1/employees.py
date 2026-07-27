import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.session import get_db
from app.dependencies.permissions import require_admin, require_admin_or_accountant
from app.db.models.user import User
from app.schemas.auth import ResetPasswordRequest
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeStatusUpdate,
    EmployeeUpdate,
)
from app.services.employee_service import EmployeeService

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
)


@router.get("/utility/next-employee-id")
def get_next_prospect_id(db: Session = Depends(get_db)):
    try:
        employee_id = generate_next_code(
            db=db,
            model=User,
            field="employee_id",
            prefix="EMP",
            digits=4,
        )
        return {"next_id": employee_id, "employeeId": employee_id}
    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate employee id: {ex}",
        ) from ex


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500, alias="pageSize"),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None, alias="isActive"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="active | inactive | all (frontend alias for isActive)",
    ),
    role: Optional[str] = Query(
        None,
        description=(
            "Filter by role: employee | accountant | processing_team | "
            "manager | sales_head"
        ),
    ),
    sales_only: bool = Query(
        False,
        alias="salesOnly",
        description=(
            "If true, only role=employee (for lead-assign / performance "
            "dropdowns; excludes managers, sales_head, accountant, processing)."
        ),
    ),
    all_records: bool = Query(False, alias="all"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_accountant),
):
    """Admin/Accountant: paginated staff directory (all assignable roles)."""
    resolved_active = is_active
    if status_filter is not None:
        key = status_filter.strip().lower()
        if key in ("active", "true", "1"):
            resolved_active = True
        elif key in ("inactive", "false", "0"):
            resolved_active = False
        elif key in ("all", ""):
            resolved_active = None
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="status must be active, inactive, or all.",
            )

    from app.core.geo_scope import merge_geo_query_params

    state_id, branch_id = merge_geo_query_params(
        current_user, state_id, branch_id
    )

    return EmployeeService.list(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=resolved_active,
        role=role,
        sales_only=sales_only,
        all_records=all_records,
        state_id=state_id,
        branch_id=branch_id,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return EmployeeService.get(db, employee_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return EmployeeService.create(
            db, payload, actor_id=current_user.id
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return EmployeeService.update(db, employee_id, payload)
    except ValueError as ex:
        code = 404 if "not found" in str(ex).lower() else 400
        raise HTTPException(status_code=code, detail=str(ex)) from ex


@router.post("/{employee_id}/reset-password")
def reset_employee_password(
    employee_id: int,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        EmployeeService.reset_password(db, employee_id, payload.newPassword)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    return {"message": "Password reset successfully."}


@router.patch("/{employee_id}/status", response_model=EmployeeResponse)
def update_employee_status(
    employee_id: int,
    payload: EmployeeStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate/deactivate employee. Deactivation requires all leads to be
    transferred first (or provide transferToId to auto-transfer)."""
    try:
        return EmployeeService.update_status(
            db,
            employee_id,
            new_status=payload.status,
            transfer_to_id=payload.transfer_to_id,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        detail = str(ex)
        match = re.search(r"has (\d+) lead", detail)
        if match:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": detail,
                    "leadCount": int(match.group(1)),
                },
            )
        raise HTTPException(status_code=404, detail=detail) from ex


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Soft-deactivate employee (isActive=false)."""
    try:
        EmployeeService.deactivate(db, employee_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
