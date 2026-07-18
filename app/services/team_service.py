"""Team dashboard for managers, sales heads, and admin."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.date_utils import datetime_range_bounds
from app.core.roles import SUPERVISOR_ROLES, is_admin, is_manager, is_sales_head
from app.db.models.prospect import Prospect
from app.db.models.user import User, UserRole
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.user_repository import UserRepository
from app.services.master_service import resolve_employee_monthly_target


class TeamService:

    @staticmethod
    def _as_decimal(value) -> Decimal:
        return Decimal(str(value or 0))

    @staticmethod
    def resolve_team_member_ids(
        db: Session,
        viewer: User,
        *,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> list[int]:
        """
        Resolve which sales employees are in scope for the viewer.
        Only role=employee members (not managers/sales_heads themselves).
        """
        query = db.query(User.id).filter(
            User.role == UserRole.employee,
            User.is_active.is_(True),
        )

        if is_admin(viewer):
            if supervisor_id is not None:
                supervisor = UserRepository.get_by_id(db, supervisor_id)
                if not supervisor or supervisor.role not in SUPERVISOR_ROLES:
                    raise ValueError("supervisorId must be a manager or sales_head.")
                if supervisor.role == UserRole.manager:
                    query = query.filter(
                        User.reports_to_manager_id == supervisor_id
                    )
                else:
                    query = query.filter(
                        User.reports_to_sales_head_id == supervisor_id
                    )
        elif is_manager(viewer):
            query = query.filter(User.reports_to_manager_id == viewer.id)
        elif is_sales_head(viewer):
            query = query.filter(User.reports_to_sales_head_id == viewer.id)
        else:
            raise ValueError("Access denied.")

        ids = [row[0] for row in query.all()]

        if employee_id is None:
            return ids

        if is_admin(viewer) and supervisor_id is None:
            emp = UserRepository.get_by_id(db, employee_id)
            if not emp or emp.role != UserRole.employee or not emp.is_active:
                raise ValueError(
                    "employeeId must be an active sales employee."
                )
            return [employee_id]

        if employee_id not in ids:
            raise ValueError("employeeId is not in your team.")
        return [employee_id]

    @staticmethod
    def list_supervisors(
        db: Session,
        role: Optional[str] = None,
    ) -> dict:
        query = db.query(User).filter(
            User.role.in_(list(SUPERVISOR_ROLES)),
            User.is_active.is_(True),
        )
        if role:
            from app.core.roles import normalize_role

            parsed = normalize_role(role)
            if parsed not in SUPERVISOR_ROLES:
                raise ValueError("role must be manager or sales_head.")
            query = query.filter(User.role == parsed)

        users = query.order_by(User.name.asc()).all()
        items = [
            {
                "id": u.id,
                "employee_id": u.employee_id,
                "name": u.name,
                "email": u.email,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": bool(u.is_active),
            }
            for u in users
        ]
        return {"items": items, "total": len(items)}

    @staticmethod
    def list_members(
        db: Session,
        viewer: User,
        *,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        ids = TeamService.resolve_team_member_ids(
            db, viewer, supervisor_id=supervisor_id
        )
        if not ids:
            return {"items": [], "total": 0}

        users = (
            db.query(User)
            .filter(User.id.in_(ids))
            .order_by(User.name.asc())
            .all()
        )
        items = []
        for u in users:
            effective, _, _ = resolve_employee_monthly_target(db, u)
            items.append(
                {
                    "id": u.id,
                    "employee_id": u.employee_id,
                    "name": u.name,
                    "email": u.email,
                    "is_active": bool(u.is_active),
                    "monthly_target": effective,
                    "reports_to_manager_id": u.reports_to_manager_id,
                    "reports_to_sales_head_id": u.reports_to_sales_head_id,
                }
            )
        return {"items": items, "total": len(items)}

    @staticmethod
    def update_assignment(
        db: Session,
        employee_id: int,
        *,
        reports_to_manager_id: Optional[int] = None,
        reports_to_sales_head_id: Optional[int] = None,
        unset_manager: bool = False,
        unset_sales_head: bool = False,
        manager_provided: bool = False,
        sales_head_provided: bool = False,
    ) -> dict:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role != UserRole.employee:
            raise ValueError("Assignment target must be a sales employee.")

        if manager_provided:
            if unset_manager or reports_to_manager_id is None:
                user.reports_to_manager_id = None
            else:
                mgr = UserRepository.get_by_id(db, reports_to_manager_id)
                if not mgr or mgr.role != UserRole.manager or not mgr.is_active:
                    raise ValueError(
                        "reportsToManagerId must be an active manager."
                    )
                user.reports_to_manager_id = reports_to_manager_id

        if sales_head_provided:
            if unset_sales_head or reports_to_sales_head_id is None:
                user.reports_to_sales_head_id = None
            else:
                sh = UserRepository.get_by_id(db, reports_to_sales_head_id)
                if (
                    not sh
                    or sh.role != UserRole.sales_head
                    or not sh.is_active
                ):
                    raise ValueError(
                        "reportsToSalesHeadId must be an active sales_head."
                    )
                user.reports_to_sales_head_id = reports_to_sales_head_id

        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "email": user.email,
            "is_active": bool(user.is_active),
            "monthly_target": None,
            "reports_to_manager_id": user.reports_to_manager_id,
            "reports_to_sales_head_id": user.reports_to_sales_head_id,
        }

    @staticmethod
    def _sum_collection(
        db: Session,
        employee_ids: list[int],
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> Decimal:
        if not employee_ids:
            return Decimal("0")
        total = Decimal("0")
        for eid in employee_ids:
            total += TeamService._as_decimal(
                AnalyticsRepository.payment_collected(
                    db,
                    employee_id=eid,
                    date_from=date_from,
                    date_to=date_to,
                )
            )
        return total

    @staticmethod
    def _deal_metrics(
        db: Session,
        employee_id: int,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> tuple[Decimal, Decimal]:
        """Returns (target_revenue, converted_deal_value)."""
        start_dt, end_dt = datetime_range_bounds(date_from, date_to)
        q = db.query(Prospect).filter(Prospect.assigned_to_id == employee_id)
        if start_dt:
            q = q.filter(Prospect.created_at >= start_dt)
        if end_dt:
            q = q.filter(Prospect.created_at <= end_dt)
        leads = q.all()

        paid_sq = AnalyticsRepository._paid_amount_subquery(db)
        paid_map = {
            row.prospect_id: TeamService._as_decimal(row.paid_amount)
            for row in db.query(paid_sq).all()
        }

        target_revenue = Decimal("0")
        converted_deal_value = Decimal("0")
        for lead in leads:
            deal = TeamService._as_decimal(lead.estimated_deal_value)
            target_revenue += deal
            if paid_map.get(lead.id, Decimal("0")) > 0:
                converted_deal_value += deal
        return target_revenue, converted_deal_value

    @staticmethod
    def compute_performance_status(
        *,
        admissions: int,
        collection: Decimal,
        monthly_target: Decimal,
        target_revenue: Decimal,
        converted_deal_value: Decimal,
    ) -> str:
        target_leads = float(monthly_target or 0)
        if target_leads <= 0:
            target_leads = 1.0  # avoid div issues; treat as at least 1

        collection_ok_high = True
        if converted_deal_value > 0:
            collection_ok_high = (
                collection / converted_deal_value >= Decimal("0.8")
            )

        is_high = admissions >= target_leads and collection_ok_high

        is_low = admissions < (0.5 * target_leads)
        if target_revenue > 0 and collection < (
            Decimal("0.3") * target_revenue
        ):
            is_low = True

        if is_high and not is_low:
            return "high"
        if is_low:
            return "low"
        return "average"

    @staticmethod
    def performance(
        db: Session,
        viewer: User,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        ids = TeamService.resolve_team_member_ids(
            db,
            viewer,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        items = []
        high = average = low = 0

        for eid in ids:
            user = UserRepository.get_by_id(db, eid)
            if not user:
                continue
            perf_rows = AnalyticsRepository.employee_performance(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=eid,
            )
            row = perf_rows[0] if perf_rows else {
                "leads_assigned": 0,
                "leads_converted": 0,
                "revenue": 0,
                "conversion_rate": 0,
            }
            admissions = int(row.get("leads_assigned") or 0)
            converted = int(row.get("leads_converted") or 0)
            collection = TeamService._as_decimal(row.get("revenue"))
            effective, _, _ = resolve_employee_monthly_target(db, user)
            target_revenue, converted_deal_value = TeamService._deal_metrics(
                db, eid, date_from, date_to
            )
            status = TeamService.compute_performance_status(
                admissions=admissions,
                collection=collection,
                monthly_target=effective,
                target_revenue=target_revenue,
                converted_deal_value=converted_deal_value,
            )
            if status == "high":
                high += 1
            elif status == "low":
                low += 1
            else:
                average += 1

            items.append(
                {
                    "employee_id": eid,
                    "employee_code": user.employee_id,
                    "employee_name": user.name,
                    "admissions": admissions,
                    "leads_converted": converted,
                    "collection": collection,
                    "monthly_target": effective,
                    "target_revenue": target_revenue,
                    "converted_deal_value": converted_deal_value,
                    "conversion_rate": float(row.get("conversion_rate") or 0),
                    "performance_status": status,
                }
            )

        items.sort(key=lambda x: (-x["admissions"], -float(x["collection"])))
        return {
            "items": items,
            "total": len(items),
            "high_count": high,
            "average_count": average,
            "low_count": low,
        }

    @staticmethod
    def sales(
        db: Session,
        viewer: User,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        ids = TeamService.resolve_team_member_ids(
            db,
            viewer,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        total_revenue = Decimal("0")
        total_admissions = 0
        leads_converted = 0
        monthly_map: dict[tuple[int, int], dict] = {}

        for eid in ids:
            rows = AnalyticsRepository.employee_performance(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=eid,
            )
            if rows:
                total_admissions += int(rows[0].get("leads_assigned") or 0)
                leads_converted += int(rows[0].get("leads_converted") or 0)
                total_revenue += TeamService._as_decimal(rows[0].get("revenue"))

            for m in AnalyticsRepository.monthly_sales(
                db,
                employee_id=eid,
                date_from=date_from,
                date_to=date_to,
            ):
                key = (int(m["year"]), str(m["month"]))
                bucket = monthly_map.setdefault(
                    key,
                    {
                        "month": m["month"],
                        "year": int(m["year"]),
                        "revenue": Decimal("0"),
                        "deals": 0,
                    },
                )
                bucket["revenue"] += TeamService._as_decimal(m.get("revenue"))
                bucket["deals"] += int(m.get("deals") or 0)

        rate = (
            round((leads_converted / total_admissions) * 100, 2)
            if total_admissions
            else 0.0
        )
        month_order = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        monthly = sorted(
            [
                {
                    "month": v["month"],
                    "year": v["year"],
                    "revenue": float(v["revenue"]),
                    "deals": v["deals"],
                }
                for v in monthly_map.values()
            ],
            key=lambda x: (
                x["year"],
                month_order.index(x["month"])
                if x["month"] in month_order
                else 0,
            ),
        )
        return {
            "total_revenue": total_revenue,
            "total_admissions": total_admissions,
            "leads_converted": leads_converted,
            "conversion_rate": rate,
            "monthly": monthly,
            "employee_id": employee_id,
        }

    @staticmethod
    def payments(
        db: Session,
        viewer: User,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        ids = TeamService.resolve_team_member_ids(
            db,
            viewer,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        collected = {
            "today": Decimal("0"),
            "thisWeek": Decimal("0"),
            "thisMonth": Decimal("0"),
            "total": Decimal("0"),
            "custom": Decimal("0") if (date_from or date_to) else None,
        }
        lead_status = {
            "advancedPaid": 0,
            "fiftyPercentPaid": 0,
            "hundredPercentPaid": 0,
        }
        total_collected = Decimal("0")

        for eid in ids:
            summary = AnalyticsRepository.payment_collected_summary(
                db,
                employee_id=eid,
                custom_from=date_from,
                custom_to=date_to,
            )
            collected["today"] += TeamService._as_decimal(summary.get("today"))
            collected["thisWeek"] += TeamService._as_decimal(
                summary.get("this_week")
            )
            collected["thisMonth"] += TeamService._as_decimal(
                summary.get("this_month")
            )
            collected["total"] += TeamService._as_decimal(summary.get("total"))
            if collected["custom"] is not None:
                collected["custom"] += TeamService._as_decimal(
                    summary.get("custom")
                )

            total_collected += TeamService._as_decimal(
                AnalyticsRepository.payment_collected(
                    db,
                    employee_id=eid,
                    date_from=date_from,
                    date_to=date_to,
                )
            )
            status = AnalyticsRepository.payment_status_summary(
                db, employee_id=eid
            )
            lead_status["advancedPaid"] += int(
                status.get("advanced_paid") or 0
            )
            lead_status["fiftyPercentPaid"] += int(
                status.get("fifty_percent_paid") or 0
            )
            lead_status["hundredPercentPaid"] += int(
                status.get("hundred_percent_paid") or 0
            )

        return {
            "total_collected": total_collected,
            "collected": {
                "today": float(collected["today"]),
                "thisWeek": float(collected["thisWeek"]),
                "thisMonth": float(collected["thisMonth"]),
                "total": float(collected["total"]),
                "custom": (
                    float(collected["custom"])
                    if collected["custom"] is not None
                    else None
                ),
            },
            "lead_payment_status": lead_status,
            "employee_id": employee_id,
        }

    @staticmethod
    def analytics(
        db: Session,
        viewer: User,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        ids = TeamService.resolve_team_member_ids(
            db,
            viewer,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        stage_map: dict[str, int] = {}
        total_admissions = 0
        total_revenue = Decimal("0")
        converted = 0
        exam = {
            "attended": 0,
            "certified": 0,
            "pending": 0,
        }
        lead_counts = {
            "total": 0,
            "today": 0,
            "thisWeek": 0,
            "thisMonth": 0,
            "custom": 0 if (date_from or date_to) else None,
        }

        for eid in ids:
            for s in AnalyticsRepository.leads_by_stage(
                db,
                employee_id=eid,
                date_from=date_from,
                date_to=date_to,
            ):
                key = s["stage"]
                stage_map[key] = stage_map.get(key, 0) + int(s["count"])

            rows = AnalyticsRepository.employee_performance(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=eid,
            )
            if rows:
                total_admissions += int(rows[0].get("leads_assigned") or 0)
                converted += int(rows[0].get("leads_converted") or 0)
                total_revenue += TeamService._as_decimal(rows[0].get("revenue"))

            counts = AnalyticsRepository.lead_counts_summary(
                db,
                employee_id=eid,
                custom_from=date_from,
                custom_to=date_to,
            )
            lead_counts["total"] += int(counts.get("total") or 0)
            lead_counts["today"] += int(counts.get("today") or 0)
            lead_counts["thisWeek"] += int(counts.get("this_week") or 0)
            lead_counts["thisMonth"] += int(counts.get("this_month") or 0)
            if lead_counts["custom"] is not None:
                lead_counts["custom"] += int(counts.get("custom") or 0)

            estats = AnalyticsRepository.exam_stats(db, employee_id=eid)
            attended = int(estats.get("attended") or 0)
            certified = int(estats.get("certified") or 0)
            exam["attended"] += attended
            exam["certified"] += certified
            total_for_exam = AnalyticsRepository.count_leads(
                db, employee_id=eid
            )
            exam["pending"] += max(0, total_for_exam - attended)

        rate = (
            round((converted / total_admissions) * 100, 2)
            if total_admissions
            else 0.0
        )
        return {
            "total_admissions": total_admissions,
            "total_revenue": total_revenue,
            "conversion_rate": rate,
            "leads_by_stage": [
                {"stage": k, "count": v} for k, v in sorted(stage_map.items())
            ],
            "exam_stats": exam,
            "lead_counts": lead_counts,
            "employee_id": employee_id,
        }

    @staticmethod
    def overview(
        db: Session,
        viewer: User,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        supervisor_id: Optional[int] = None,
    ) -> dict:
        perf = TeamService.performance(
            db,
            viewer,
            date_from=date_from,
            date_to=date_to,
            supervisor_id=supervisor_id,
        )
        sales = TeamService.sales(
            db,
            viewer,
            date_from=date_from,
            date_to=date_to,
            supervisor_id=supervisor_id,
        )
        return {
            "team_size": perf["total"],
            "total_admissions": sales["total_admissions"],
            "total_collection": sales["total_revenue"],
            "high_performers": perf["high_count"],
            "average_performers": perf["average_count"],
            "low_performers": perf["low_count"],
            "conversion_rate": sales["conversion_rate"],
            "date_from": date_from,
            "date_to": date_to,
        }
