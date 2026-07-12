from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

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


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None, alias="isActive"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: paginated employee directory."""
    return EmployeeService.list(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
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
        return EmployeeService.create(db, payload)
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
