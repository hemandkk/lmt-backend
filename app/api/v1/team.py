from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.permissions import require_admin, require_team_viewer
from app.schemas.team import (
    TeamAnalyticsResponse,
    TeamAssignmentUpdate,
    TeamMemberItem,
    TeamMemberListResponse,
    TeamOverviewResponse,
    TeamPaymentsResponse,
    TeamPerformanceResponse,
    TeamSalesResponse,
    TeamSupervisorListResponse,
)
from app.services.team_export_service import TeamExportService
from app.services.team_service import TeamService

router = APIRouter(prefix="/team", tags=["Team Dashboard"])


@router.get("/supervisors", response_model=TeamSupervisorListResponse)
def list_supervisors(
    role: Optional[str] = Query(
        None, description="manager | sales_head"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: list managers / sales heads for assignment dropdowns."""
    try:
        return TeamService.list_supervisors(db, role=role)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/members", response_model=TeamMemberListResponse)
def list_team_members(
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    """
    Team employee list for filter dropdowns.
    Manager/sales_head: own team. Admin: all or filter by supervisorId.
    """
    try:
        return TeamService.list_members(
            db, current_user, supervisor_id=supervisor_id
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put(
    "/assignments/{employee_id}",
    response_model=TeamMemberItem,
)
def update_team_assignment(
    employee_id: int,
    payload: TeamAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: assign employee to manager and/or sales head."""
    data = payload.model_dump(exclude_unset=True)
    try:
        return TeamService.update_assignment(
            db,
            employee_id,
            reports_to_manager_id=data.get("reports_to_manager_id"),
            reports_to_sales_head_id=data.get("reports_to_sales_head_id"),
            manager_provided="reports_to_manager_id" in data,
            sales_head_provided="reports_to_sales_head_id" in data,
            unset_manager=(
                "reports_to_manager_id" in data
                and data.get("reports_to_manager_id") is None
            ),
            unset_sales_head=(
                "reports_to_sales_head_id" in data
                and data.get("reports_to_sales_head_id") is None
            ),
        )
    except ValueError as ex:
        code = (
            status.HTTP_404_NOT_FOUND
            if "must be a sales employee" in str(ex).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(ex)) from ex


@router.get("/dashboard/overview", response_model=TeamOverviewResponse)
def team_overview(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    """
    Team overview KPIs.
    Admin: all employees, or filter with employeeId and/or supervisorId.
    Manager/sales_head: own team (optionally narrowed with employeeId).
    """
    try:
        return TeamService.overview(
            db,
            current_user,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/dashboard/sales", response_model=TeamSalesResponse)
def team_sales(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    try:
        return TeamService.sales(
            db,
            current_user,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/dashboard/performance", response_model=TeamPerformanceResponse)
def team_performance(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    try:
        return TeamService.performance(
            db,
            current_user,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/dashboard/payments", response_model=TeamPaymentsResponse)
def team_payments(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    try:
        return TeamService.payments(
            db,
            current_user,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/dashboard/analytics", response_model=TeamAnalyticsResponse)
def team_analytics(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    try:
        return TeamService.analytics(
            db,
            current_user,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/exports")
def team_exports(
    export_type: str = Query(..., alias="exportType"),
    fmt: str = Query("xlsx", alias="format"),
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    supervisor_id: Optional[int] = Query(None, alias="supervisorId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_viewer),
):
    """Download team sales / performance / payments / analytics reports."""
    try:
        return TeamExportService.export(
            db,
            current_user,
            export_type=export_type,
            fmt=fmt,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
