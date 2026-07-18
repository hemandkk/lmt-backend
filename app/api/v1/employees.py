from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.session import get_db
from app.dependencies.permissions import require_admin
from app.db.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
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
        description="Filter by role: employee | accountant | processing_team",
    ),
    sales_only: bool = Query(
        False,
        alias="salesOnly",
        description="If true, only sales employees (excludes accountant/processing).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: paginated staff directory (employee / accountant / processing_team)."""
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

    return EmployeeService.list(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=resolved_active,
        role=role,
        sales_only=sales_only,
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
