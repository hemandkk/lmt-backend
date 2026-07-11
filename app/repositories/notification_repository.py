from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.notification import Notification


class NotificationRepository:

    @staticmethod
    def create(db: Session, notification: Notification) -> Notification:
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def create_many(db: Session, notifications: list[Notification]) -> list[Notification]:
        db.add_all(notifications)
        db.commit()
        for n in notifications:
            db.refresh(n)
        return notifications

    @staticmethod
    def get_by_id(db: Session, notification_id: int) -> Optional[Notification]:
        return (
            db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

    @staticmethod
    def list_for_user(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        query = db.query(Notification).filter(Notification.user_id == user_id)

        if unread_only:
            query = query.filter(Notification.is_read.is_(False))

        total = query.count()
        items = (
            query.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def unread_count(db: Session, user_id: int) -> int:
        return (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .count()
        )

    @staticmethod
    def mark_read(db: Session, notification: Notification) -> Notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        updated = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .update({"is_read": True}, synchronize_session=False)
        )
        db.commit()
        return updated
