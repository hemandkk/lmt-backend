from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.activity_log import ActivityLog
from app.db.models.notification import Notification, NotificationType
from app.db.models.prospect import Prospect
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.notification_repository import NotificationRepository


class NotificationService:

    @staticmethod
    def notify_lead_assigned(
        db: Session,
        prospect: Prospect,
        actor_id: Optional[int] = None,
    ) -> Optional[Notification]:
        if not prospect.assigned_to_id:
            return None

        notification = Notification(
            user_id=prospect.assigned_to_id,
            prospect_id=prospect.id,
            type=NotificationType.lead_assigned,
            title="New lead assigned",
            message=(
                f"Lead {prospect.prospect_id} ({prospect.name}) "
                f"has been assigned to you."
            ),
            is_read=False,
        )
        created = NotificationRepository.create(db, notification)

        ActivityLogService.log(
            db,
            action="lead_assigned",
            entity_type="prospect",
            entity_id=prospect.id,
            description=(
                f"Lead {prospect.prospect_id} assigned to user "
                f"{prospect.assigned_to_id}"
            ),
            user_id=actor_id,
            prospect_id=prospect.id,
        )
        return created

    @staticmethod
    def notify_stage_changed(
        db: Session,
        prospect: Prospect,
        old_stage: str,
        new_stage: str,
        actor_id: Optional[int] = None,
    ) -> Optional[Notification]:
        notification = None
        if prospect.assigned_to_id:
            notification = Notification(
                user_id=prospect.assigned_to_id,
                prospect_id=prospect.id,
                type=NotificationType.stage_changed,
                title="Lead stage updated",
                message=(
                    f"Lead {prospect.prospect_id} ({prospect.name}) "
                    f"moved from {old_stage} to {new_stage}."
                ),
                is_read=False,
            )
            NotificationRepository.create(db, notification)

        ActivityLogService.log(
            db,
            action="stage_changed",
            entity_type="prospect",
            entity_id=prospect.id,
            description=(
                f"Lead {prospect.prospect_id} stage changed "
                f"from {old_stage} to {new_stage}"
            ),
            user_id=actor_id,
            prospect_id=prospect.id,
            meta_data=f'{{"old_stage":"{old_stage}","new_stage":"{new_stage}"}}',
        )
        return notification

    @staticmethod
    def create_follow_up_reminders(db: Session) -> int:
        """Create reminders for leads with follow_up_date <= today."""
        from datetime import date

        from app.db.models.prospect import Prospect

        due = (
            db.query(Prospect)
            .filter(
                Prospect.follow_up_date.isnot(None),
                Prospect.follow_up_date <= date.today(),
                Prospect.assigned_to_id.isnot(None),
            )
            .all()
        )

        created = 0
        for prospect in due:
            # Avoid duplicate unread reminders for same prospect today
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == prospect.assigned_to_id,
                    Notification.prospect_id == prospect.id,
                    Notification.type == NotificationType.follow_up_reminder,
                    Notification.is_read.is_(False),
                )
                .first()
            )
            if existing:
                continue

            NotificationRepository.create(
                db,
                Notification(
                    user_id=prospect.assigned_to_id,
                    prospect_id=prospect.id,
                    type=NotificationType.follow_up_reminder,
                    title="Follow-up reminder",
                    message=(
                        f"Follow-up due for lead {prospect.prospect_id} "
                        f"({prospect.name}) on {prospect.follow_up_date}."
                    ),
                    is_read=False,
                ),
            )
            created += 1

        return created

    @staticmethod
    def list_for_user(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> dict:
        items, total = NotificationRepository.list_for_user(
            db, user_id, page, page_size, unread_only
        )
        return {
            "items": items,
            "total": total,
            "unread_count": NotificationRepository.unread_count(db, user_id),
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int) -> Notification:
        notification = NotificationRepository.get_by_id(db, notification_id)
        if not notification or notification.user_id != user_id:
            raise ValueError("Notification not found.")
        return NotificationRepository.mark_read(db, notification)

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        return NotificationRepository.mark_all_read(db, user_id)


class ActivityLogService:

    @staticmethod
    def log(
        db: Session,
        *,
        action: str,
        entity_type: str,
        description: str,
        entity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        prospect_id: Optional[int] = None,
        meta_data: Optional[str] = None,
    ) -> ActivityLog:
        log = ActivityLog(
            user_id=user_id,
            prospect_id=prospect_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            meta_data=meta_data,
        )
        return ActivityLogRepository.create(db, log)

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        prospect_id: Optional[int] = None,
        action: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        items, total = ActivityLogRepository.list(
            db,
            page=page,
            page_size=page_size,
            user_id=user_id,
            prospect_id=prospect_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )

        response_items = []
        for item in items:
            response_items.append(
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "prospect_id": item.prospect_id,
                    "action": item.action,
                    "entity_type": item.entity_type,
                    "entity_id": item.entity_id,
                    "description": item.description,
                    "meta_data": item.meta_data,
                    "created_at": item.created_at,
                    "user_name": item.user.name if item.user else None,
                }
            )

        return {
            "items": response_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
