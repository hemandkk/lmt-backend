from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, extract, func, or_
from sqlalchemy.orm import Session

from app.core.date_utils import (
    datetime_range_bounds,
    end_of_month,
    end_of_week,
    start_of_month,
    start_of_week,
    today,
)
from app.db.models.payment import Payment, PaymentStatus, PaymentType
from app.db.models.prospect import Prospect, ProspectStage
from app.db.models.user import User, UserRole


class AnalyticsRepository:
    """Shared aggregation queries for dashboards and reports."""

    @staticmethod
    def _prospect_base_query(
        db: Session,
        employee_id: Optional[int] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ):
        query = db.query(Prospect)

        if employee_id is not None:
            query = query.filter(Prospect.assigned_to_id == employee_id)

        if stage:
            query = query.filter(Prospect.stage == stage)

        if source:
            query = query.filter(Prospect.source == source)

        start_dt, end_dt = datetime_range_bounds(date_from, date_to)
        if start_dt:
            query = query.filter(Prospect.created_at >= start_dt)
        if end_dt:
            query = query.filter(Prospect.created_at <= end_dt)

        return query

    @staticmethod
    def count_leads(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        return AnalyticsRepository._prospect_base_query(
            db,
            employee_id=employee_id,
            stage=stage,
            source=source,
            date_from=date_from,
            date_to=date_to,
        ).count()

    @staticmethod
    def lead_counts_summary(
        db: Session,
        employee_id: Optional[int] = None,
        custom_from: Optional[date] = None,
        custom_to: Optional[date] = None,
    ) -> dict:
        current = today()
        week_start = start_of_week(current)
        week_end = end_of_week(current)
        month_start = start_of_month(current)
        month_end = end_of_month(current)

        result = {
            "total": AnalyticsRepository.count_leads(db, employee_id=employee_id),
            "today": AnalyticsRepository.count_leads(
                db,
                employee_id=employee_id,
                date_from=current,
                date_to=current,
            ),
            "this_week": AnalyticsRepository.count_leads(
                db,
                employee_id=employee_id,
                date_from=week_start,
                date_to=week_end,
            ),
            "this_month": AnalyticsRepository.count_leads(
                db,
                employee_id=employee_id,
                date_from=month_start,
                date_to=month_end,
            ),
            "custom": None,
        }

        if custom_from or custom_to:
            result["custom"] = AnalyticsRepository.count_leads(
                db,
                employee_id=employee_id,
                date_from=custom_from,
                date_to=custom_to,
            )

        return result

    @staticmethod
    def _paid_amount_subquery(db: Session):
        return (
            db.query(
                Payment.prospect_id.label("prospect_id"),
                func.coalesce(func.sum(Payment.amount), 0).label("paid_amount"),
            )
            .filter(Payment.payment_status == PaymentStatus.completed)
            .group_by(Payment.prospect_id)
            .subquery()
        )

    @staticmethod
    def payment_status_summary(
        db: Session,
        employee_id: Optional[int] = None,
    ) -> dict:
        paid_sq = AnalyticsRepository._paid_amount_subquery(db)

        base = (
            db.query(
                Prospect.id,
                Prospect.estimated_deal_value,
                func.coalesce(paid_sq.c.paid_amount, 0).label("paid_amount"),
            )
            .outerjoin(paid_sq, paid_sq.c.prospect_id == Prospect.id)
        )

        if employee_id is not None:
            base = base.filter(Prospect.assigned_to_id == employee_id)

        rows = base.all()

        advanced_paid = 0
        fifty_percent = 0
        hundred_percent = 0

        # Advance-type completed payments count as "advanced paid" leads
        advance_q = (
            db.query(func.count(func.distinct(Payment.prospect_id)))
            .join(Prospect, Prospect.id == Payment.prospect_id)
            .filter(
                Payment.payment_status == PaymentStatus.completed,
                Payment.payment_type == PaymentType.advance,
            )
        )
        if employee_id is not None:
            advance_q = advance_q.filter(Prospect.assigned_to_id == employee_id)
        advanced_paid = advance_q.scalar() or 0

        for row in rows:
            deal = Decimal(row.estimated_deal_value or 0)
            paid = Decimal(row.paid_amount or 0)

            if deal <= 0:
                if paid > 0:
                    hundred_percent += 1
                continue

            ratio = paid / deal
            if ratio >= Decimal("1"):
                hundred_percent += 1
            elif ratio >= Decimal("0.5"):
                fifty_percent += 1

        return {
            "advanced_paid": int(advanced_paid),
            "fifty_percent_paid": fifty_percent,
            "hundred_percent_paid": hundred_percent,
        }

    @staticmethod
    def payment_collected(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Decimal:
        query = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Prospect, Prospect.id == Payment.prospect_id)
            .filter(Payment.payment_status == PaymentStatus.completed)
        )

        if employee_id is not None:
            query = query.filter(Prospect.assigned_to_id == employee_id)

        if date_from:
            query = query.filter(Payment.payment_date >= date_from)
        if date_to:
            query = query.filter(Payment.payment_date <= date_to)

        return Decimal(query.scalar() or 0)

    @staticmethod
    def payment_collected_summary(
        db: Session,
        employee_id: Optional[int] = None,
        custom_from: Optional[date] = None,
        custom_to: Optional[date] = None,
    ) -> dict:
        current = today()
        result = {
            "today": AnalyticsRepository.payment_collected(
                db, employee_id=employee_id, date_from=current, date_to=current
            ),
            "this_week": AnalyticsRepository.payment_collected(
                db,
                employee_id=employee_id,
                date_from=start_of_week(current),
                date_to=end_of_week(current),
            ),
            "this_month": AnalyticsRepository.payment_collected(
                db,
                employee_id=employee_id,
                date_from=start_of_month(current),
                date_to=end_of_month(current),
            ),
            "total": AnalyticsRepository.payment_collected(db, employee_id=employee_id),
            "custom": None,
        }

        if custom_from or custom_to:
            result["custom"] = AnalyticsRepository.payment_collected(
                db,
                employee_id=employee_id,
                date_from=custom_from,
                date_to=custom_to,
            )

        return result

    @staticmethod
    def count_employees(db: Session) -> int:
        return (
            db.query(func.count(User.id))
            .filter(User.role == UserRole.employee, User.is_active.is_(True))
            .scalar()
            or 0
        )

    @staticmethod
    def leads_by_stage(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        source: Optional[str] = None,
    ) -> list[dict]:
        query = db.query(Prospect.stage, func.count(Prospect.id))

        if employee_id is not None:
            query = query.filter(Prospect.assigned_to_id == employee_id)
        if source:
            query = query.filter(Prospect.source == source)

        start_dt, end_dt = datetime_range_bounds(date_from, date_to)
        if start_dt:
            query = query.filter(Prospect.created_at >= start_dt)
        if end_dt:
            query = query.filter(Prospect.created_at <= end_dt)

        rows = query.group_by(Prospect.stage).all()
        return [{"stage": (r[0].value if hasattr(r[0], "value") else str(r[0])), "count": r[1]} for r in rows]

    @staticmethod
    def employee_performance(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        paid_sq = AnalyticsRepository._paid_amount_subquery(db)
        start_dt, end_dt = datetime_range_bounds(date_from, date_to)

        has_filters = any([stage, source, start_dt, end_dt])

        assigned = func.count(Prospect.id)
        converted = func.sum(
            case((Prospect.stage == ProspectStage.won, 1), else_=0)
        )
        revenue = func.coalesce(func.sum(paid_sq.c.paid_amount), 0)

        if has_filters:
            query = (
                db.query(
                    User.id.label("employee_id"),
                    User.employee_id.label("employee_code"),
                    User.name.label("employee_name"),
                    assigned.label("leads_assigned"),
                    converted.label("leads_converted"),
                    revenue.label("revenue"),
                )
                .join(Prospect, Prospect.assigned_to_id == User.id)
                .outerjoin(paid_sq, paid_sq.c.prospect_id == Prospect.id)
                .filter(User.role == UserRole.employee)
            )
            if stage:
                query = query.filter(Prospect.stage == stage)
            if source:
                query = query.filter(Prospect.source == source)
            if start_dt:
                query = query.filter(Prospect.created_at >= start_dt)
            if end_dt:
                query = query.filter(Prospect.created_at <= end_dt)
        else:
            query = (
                db.query(
                    User.id.label("employee_id"),
                    User.employee_id.label("employee_code"),
                    User.name.label("employee_name"),
                    assigned.label("leads_assigned"),
                    converted.label("leads_converted"),
                    revenue.label("revenue"),
                )
                .outerjoin(Prospect, Prospect.assigned_to_id == User.id)
                .outerjoin(paid_sq, paid_sq.c.prospect_id == Prospect.id)
                .filter(User.role == UserRole.employee)
            )

        if employee_id is not None:
            query = query.filter(User.id == employee_id)

        query = query.group_by(User.id, User.employee_id, User.name).order_by(
            revenue.desc()
        )

        if limit:
            query = query.limit(limit)

        results = []
        for row in query.all():
            assigned_count = int(row.leads_assigned or 0)
            converted_count = int(row.leads_converted or 0)
            rate = (converted_count / assigned_count * 100) if assigned_count else 0.0
            results.append(
                {
                    "employee_id": row.employee_id,
                    "employee_code": row.employee_code,
                    "employee_name": row.employee_name or "Unknown",
                    "leads_assigned": assigned_count,
                    "leads_converted": converted_count,
                    "revenue": Decimal(row.revenue or 0),
                    "conversion_rate": round(rate, 2),
                }
            )
        return results

    @staticmethod
    def monthly_sales(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        months: int = 12,
    ) -> list[dict]:
        year_col = extract("year", Payment.payment_date)
        month_col = extract("month", Payment.payment_date)

        query = (
            db.query(
                year_col.label("year"),
                month_col.label("month"),
                func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
                func.count(func.distinct(Payment.prospect_id)).label("deals"),
            )
            .join(Prospect, Prospect.id == Payment.prospect_id)
            .filter(Payment.payment_status == PaymentStatus.completed)
        )

        if employee_id is not None:
            query = query.filter(Prospect.assigned_to_id == employee_id)
        if date_from:
            query = query.filter(Payment.payment_date >= date_from)
        if date_to:
            query = query.filter(Payment.payment_date <= date_to)

        rows = (
            query.group_by(year_col, month_col)
            .order_by(year_col.desc(), month_col.desc())
            .limit(months)
            .all()
        )

        month_names = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

        items = []
        for row in reversed(rows):
            m = int(row.month)
            items.append(
                {
                    "month": month_names[m],
                    "year": int(row.year),
                    "revenue": Decimal(row.revenue or 0),
                    "leads_won": int(row.deals or 0),
                    "deals": int(row.deals or 0),
                }
            )
        return items

    @staticmethod
    def lead_source_analysis(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        stage: Optional[str] = None,
    ) -> list[dict]:
        paid_sq = AnalyticsRepository._paid_amount_subquery(db)
        start_dt, end_dt = datetime_range_bounds(date_from, date_to)

        source_col = func.coalesce(Prospect.source, "Unknown")

        query = (
            db.query(
                source_col.label("source"),
                func.count(Prospect.id).label("count"),
                func.sum(
                    case((Prospect.stage == ProspectStage.won, 1), else_=0)
                ).label("converted"),
                func.coalesce(func.sum(paid_sq.c.paid_amount), 0).label("revenue"),
            )
            .outerjoin(paid_sq, paid_sq.c.prospect_id == Prospect.id)
        )

        if employee_id is not None:
            query = query.filter(Prospect.assigned_to_id == employee_id)
        if stage:
            query = query.filter(Prospect.stage == stage)
        if start_dt:
            query = query.filter(Prospect.created_at >= start_dt)
        if end_dt:
            query = query.filter(Prospect.created_at <= end_dt)

        rows = query.group_by(source_col).order_by(func.count(Prospect.id).desc()).all()

        return [
            {
                "source": row.source,
                "count": int(row.count or 0),
                "converted": int(row.converted or 0),
                "revenue": Decimal(row.revenue or 0),
            }
            for row in rows
        ]

    @staticmethod
    def win_loss_analysis(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        source: Optional[str] = None,
    ) -> dict:
        query = AnalyticsRepository._prospect_base_query(
            db,
            employee_id=employee_id,
            source=source,
            date_from=date_from,
            date_to=date_to,
        )

        won = query.filter(Prospect.stage == ProspectStage.won).count()
        lost = query.filter(Prospect.stage == ProspectStage.lost).count()
        closed = won + lost
        win_rate = (won / closed * 100) if closed else 0.0

        return {
            "won": won,
            "lost": lost,
            "win_rate": round(win_rate, 2),
        }

    @staticmethod
    def follow_up_activity_count(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> int:
        from app.db.models.activity_log import ActivityLog

        query = db.query(func.count(ActivityLog.id)).filter(
            ActivityLog.action.in_(
                ["follow_up", "stage_changed", "lead_updated"]
            ),
            or_(
                ActivityLog.description.ilike("%follow%"),
                ActivityLog.action == "follow_up",
            ),
        )

        # Also count prospects currently in follow_up stage created/updated in range
        prospect_q = db.query(func.count(Prospect.id)).filter(
            Prospect.stage == ProspectStage.follow_up
        )
        if employee_id is not None:
            prospect_q = prospect_q.filter(Prospect.assigned_to_id == employee_id)
            query = query.filter(ActivityLog.user_id == employee_id)

        start_dt, end_dt = datetime_range_bounds(date_from, date_to)
        if start_dt:
            prospect_q = prospect_q.filter(Prospect.updated_at >= start_dt)
            query = query.filter(ActivityLog.created_at >= start_dt)
        if end_dt:
            prospect_q = prospect_q.filter(Prospect.updated_at <= end_dt)
            query = query.filter(ActivityLog.created_at <= end_dt)

        activity_count = query.scalar() or 0
        stage_count = prospect_q.scalar() or 0
        return int(activity_count) + int(stage_count)

    @staticmethod
    def list_leads_for_export(
        db: Session,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[Prospect]:
        return (
            AnalyticsRepository._prospect_base_query(
                db,
                employee_id=employee_id,
                stage=stage,
                source=source,
                date_from=date_from,
                date_to=date_to,
            )
            .order_by(Prospect.created_at.desc())
            .all()
        )
