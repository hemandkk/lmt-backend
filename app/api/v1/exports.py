from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("")
def export_data(
    export_type: str = Query(
        ...,
        alias="exportType",
        description="leads | employee_performance | sales | dashboard",
    ),
    format: str = Query(
        ...,
        alias="format",
        description="xlsx | csv | pdf",
    ),
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    employee_id: Optional[int] = Query(None, alias="employeeId"),
    stage: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export filtered data to Excel (.xlsx), CSV, or PDF.
    Options: leads, employee_performance, sales, dashboard.
    """
    is_admin = current_user.role == UserRole.admin
    try:
        return ExportService.export(
            db,
            export_type=export_type,
            fmt=format,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            stage=stage,
            source=source,
            current_user_id=current_user.id,
            is_admin=is_admin,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
