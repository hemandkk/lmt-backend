from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.schemas.dashboard import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    unread_only: bool = Query(False, alias="unreadOnly"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationService.list_for_user(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return NotificationService.mark_read(
            db, notification_id, current_user.id
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = NotificationService.mark_all_read(db, current_user.id)
    return {"marked_read": count}


@router.post("/follow-up-reminders", status_code=status.HTTP_200_OK)
def trigger_follow_up_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Generate follow-up reminder notifications for leads
    whose follow_up_date is today or overdue.
    Intended to be called by a scheduler/cron.
    """
    created = NotificationService.create_follow_up_reminders(db)
    return {"reminders_created": created}
