from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.dashboard import ActivityLogListResponse
from app.services.notification_service import ActivityLogService

router = APIRouter(prefix="/activity-logs", tags=["Activity Logs"])


@router.get("", response_model=ActivityLogListResponse)
def list_activity_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    user_id: Optional[int] = Query(None, alias="userId"),
    prospect_id: Optional[int] = Query(None, alias="prospectId"),
    action: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activity logs for lead assignment, stage changes, updates, etc.
    Admin: full log (optional user filter). Others: own logs only.
    """
    scoped_user_id = user_id
    if current_user.role != UserRole.admin:
        scoped_user_id = current_user.id

    return ActivityLogService.list(
        db,
        page=page,
        page_size=page_size,
        user_id=scoped_user_id,
        prospect_id=prospect_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
