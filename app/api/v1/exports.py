from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import resolve_employee_scope
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
    Export filtered data.
    - Employee: always scoped to self
    - Admin: all, or filter with employeeId
    """
    is_admin = current_user.role == UserRole.admin
    scoped_employee_id = resolve_employee_scope(current_user, employee_id)

    # Admin "all" exports keep employee_id=None; employees always get self
    export_employee_id = scoped_employee_id
    if is_admin and employee_id is None:
        export_employee_id = None

    try:
        return ExportService.export(
            db,
            export_type=export_type,
            fmt=format,
            date_from=date_from,
            date_to=date_to,
            employee_id=export_employee_id,
            stage=stage,
            source=source,
            current_user_id=current_user.id,
            is_admin=is_admin and employee_id is None,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
