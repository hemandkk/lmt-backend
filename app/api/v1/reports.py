from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin, resolve_employee_scope
from app.schemas.dashboard import (
    AdminReportResponse,
    EmployeePerformanceReportResponse,
    EmployeeReportResponse,
    IncentiveReleaseListResponse,
    IncentiveReleaseResponse,
    IncentiveReportResponse,
    LeadsByStageReportResponse,
    LeadsByAdminStageReportResponse,
    RevenueReportResponse,
)
from app.services.dashboard_service import ReportService
from app.services.incentive_release_service import IncentiveReleaseService

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
        raise HTTPException(status_code=404, detail=str(ex)) from ex


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
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.get("/admin", response_model=AdminReportResponse)
def admin_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin reports — all data, or filter by employeeId / stateId / branchId /
    stage / source / dates.
    """
    return ReportService.admin_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        state_id=state_id,
        branch_id=branch_id,
        stage=stage,
        source=source,
    )


@router.get("/revenue", response_model=RevenueReportResponse)
def revenue_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin revenue report: totals, monthly trend, by employee."""
    return ReportService.revenue_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        state_id=state_id,
        branch_id=branch_id,
    )


@router.get(
    "/employee-performance",
    response_model=EmployeePerformanceReportResponse,
)
def employee_performance_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin employee performance comparison."""
    return ReportService.employee_performance_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        state_id=state_id,
        branch_id=branch_id,
        stage=stage,
        source=source,
    )


@router.get(
    "/leads-by-stage",
    response_model=LeadsByStageReportResponse,
)
def leads_by_stage_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin leads grouped by pipeline stage."""
    return ReportService.leads_by_stage_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        state_id=state_id,
        branch_id=branch_id,
        source=source,
    )


@router.get(
    "/leads-by-admission-stage",
    response_model=LeadsByAdminStageReportResponse,
)
def leads_by_admission_stage_report(
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin leads grouped by admission stage."""
    return ReportService.leads_by_admission_stage_report(
        db,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        state_id=state_id,
        branch_id=branch_id,
        source=source,
    )


@router.get("/incentives", response_model=IncentiveReportResponse)
def incentives_report(
    month: Optional[str] = Query(
        None,
        description="Month in YYYY-MM format (e.g. 2026-07). Defaults to current month.",
    ),
    employee_id: Optional[int] = Query(
        None,
        alias="employeeId",
        description="Admin only: filter to one employee",
    ),
    state_id: Optional[int] = Query(None, alias="stateId"),
    branch_id: Optional[int] = Query(None, alias="branchId"),
    branch_ids: Optional[str] = Query(None, alias="branchIds", description="CSV e.g. 1,2,3"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Incentive report for a calendar month.
    - Employee: own incentive only
    - Admin: all employees, or ?employeeId= / stateId / branchId
    """
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)
    from app.core.geo_scope import merge_geo_query_params, parse_branch_ids

    geo = merge_geo_query_params(
        current_user, state_id, branch_id, parse_branch_ids(branch_ids)
    )
    state_id = geo.state_id
    branch_id = geo.branch_id
    branch_ids = geo.normalized_branch_ids()
    try:
        return ReportService.incentive_report(
            db,
            month=month,
            employee_id=scoped_employee_id,
            state_id=state_id,
            branch_id=branch_id,
            branch_ids=branch_ids,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get(
    "/incentive-releases",
    response_model=IncentiveReleaseResponse | IncentiveReleaseListResponse,
)
def incentive_releases_report(
    month: Optional[str] = Query(
        None,
        description="Month in YYYY-MM format (e.g. 2026-07). Defaults to current month.",
    ),
    employee_id: Optional[int] = Query(
        None,
        alias="employeeId",
        description="Admin only: filter to one employee. Omit for all employees.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Incentive release report — monthly breakdown of admissions, booked/receivable incentives.
    - Employee: own incentive releases only
    - Admin with ?employeeId=: single employee view
    - Admin without ?employeeId=: per-employee breakdown for all employees
    """
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)
    from app.core.geo_scope import merge_geo_query_params

    geo = merge_geo_query_params(current_user)
    state_id = geo.state_id
    branch_id = geo.branch_id
    branch_ids = geo.normalized_branch_ids()
    try:
        return IncentiveReleaseService.incentive_release_report(
            db,
            month=month,
            employee_id=scoped_employee_id,
            state_id=state_id,
            branch_id=branch_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
