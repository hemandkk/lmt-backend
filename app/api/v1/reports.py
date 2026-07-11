from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.schemas.dashboard import AdminReportResponse, EmployeeReportResponse
from app.services.dashboard_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/employee", response_model=EmployeeReportResponse)
def employee_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Employee report:
    Leads Created, Leads Converted, Revenue Generated,
    Conversion Rate, Follow-up Activity.
    """
    try:
        return ReportService.employee_report(
            db,
            employee_id=current_user.id,
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
    Admin reports:
    Employee Performance Comparison, Sales by Month,
    Sales by Employee, Lead Source Analysis, Win/Loss Analysis.
    Filters: date range, employee, lead stage, lead source.
    """
    return ReportService.admin_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        stage=stage,
        source=source,
    )
