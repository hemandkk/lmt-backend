from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin, resolve_employee_scope
from app.schemas.dashboard import (
    AdminDashboardResponse,
    EmployeeDashboardResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/employee", response_model=EmployeeDashboardResponse)
def employee_dashboard(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(
        None,
        alias="employeeId",
        description="Admin only: view a specific employee's dashboard",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scoped employee dashboard.
    - Employee: always own data
    - Admin: own data by default, or ?employeeId= for another employee
    """
    if current_user.role == UserRole.admin and employee_id is not None:
        scoped_id = employee_id
    else:
        scoped_id = current_user.id

    return DashboardService.employee_dashboard(
        db,
        employee_id=scoped_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/employee/{employee_id}",
    response_model=EmployeeDashboardResponse,
)
def employee_dashboard_by_id(
    employee_id: int,
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin view of a specific employee's dashboard."""
    return DashboardService.employee_dashboard(
        db,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/admin", response_model=AdminDashboardResponse)
def admin_dashboard(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(
        None,
        alias="employeeId",
        description="Optional: filter all KPIs to one employee",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin dashboard. View all, or filter with ?employeeId=.
    """
    return DashboardService.admin_dashboard(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
    )
