from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Employee dashboard:
    - Lead counts (total, today, this week, this month, custom range)
    - Payment status (advance / 50% / 100% paid)
    - Payment collected (today, week, month, total, custom range)
    """
    employee_id = current_user.id
    if current_user.role == UserRole.admin:
        # Admin can view own empty employee view; use assigned scope of self
        employee_id = current_user.id

    return DashboardService.employee_dashboard(
        db,
        employee_id=employee_id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin dashboard KPIs and chart data:
    Total Employees, Total Leads, Total Revenue,
    Leads by Stage, Employee-wise Performance,
    Monthly Sales Trend, Top Performers.
    """
    return DashboardService.admin_dashboard(
        db,
        date_from=date_from,
        date_to=date_to,
    )
