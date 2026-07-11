from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin, resolve_employee_scope
from app.schemas.dashboard import AdminReportResponse, EmployeeReportResponse
from app.services.dashboard_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/employee", response_model=EmployeeReportResponse)
def employee_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    employee_id: Optional[int] = Query(
        None,
        alias="employeeId",
        description="Admin only: report for another employee",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Employee report (scoped).
    - Employee: always own report
    - Admin: own by default, or ?employeeId=
    """
    if current_user.role == UserRole.admin and employee_id is not None:
        scoped_id = employee_id
    else:
        scoped_id = current_user.id

    try:
        return ReportService.employee_report(
            db,
            employee_id=scoped_id,
            date_from=date_from,
            date_to=date_to,
            stage=stage,
            source=source,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get(
    "/employee/{employee_id}",
    response_model=EmployeeReportResponse,
)
def employee_report_by_id(
    employee_id: int,
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return ReportService.employee_report(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            stage=stage,
            source=source,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get("/admin", response_model=AdminReportResponse)
def admin_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin reports — all data, or filter by employeeId / stage / source / dates.
    """
    return ReportService.admin_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        stage=stage,
        source=source,
    )
