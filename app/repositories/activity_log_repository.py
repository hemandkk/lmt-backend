from datetime import date
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.date_utils import datetime_range_bounds
from app.db.models.activity_log import ActivityLog


class ActivityLogRepository:

    @staticmethod
    def create(db: Session, log: ActivityLog) -> ActivityLog:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        prospect_id: Optional[int] = None,
        action: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> tuple[list[ActivityLog], int]:
        query = db.query(ActivityLog).options(joinedload(ActivityLog.user))

        if user_id is not None:
            query = query.filter(ActivityLog.user_id == user_id)
        if prospect_id is not None:
            query = query.filter(ActivityLog.prospect_id == prospect_id)
        if action:
            query = query.filter(ActivityLog.action == action)

        start_dt, end_dt = datetime_range_bounds(date_from, date_to)
        if start_dt:
            query = query.filter(ActivityLog.created_at >= start_dt)
        if end_dt:
            query = query.filter(ActivityLog.created_at <= end_dt)

        total = query.count()
        items = (
            query.order_by(ActivityLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
