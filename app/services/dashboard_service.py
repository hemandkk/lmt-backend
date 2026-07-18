from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AdminReportResponse,
    EmployeeDashboardResponse,
    EmployeeOverviewItem,
    EmployeePerformanceItem,
    EmployeePerformanceReportResponse,
    EmployeeReportResponse,
    ExamStatsSummary,
    IncentiveReportItem,
    IncentiveReportResponse,
    IncentiveReportTotals,
    IncentiveStatusSummary,
    LeadCountSummary,
    LeadSourceItem,
    LeadsByStageReportResponse,
    MonthlySalesItem,
    PaymentCollectedSummary,
    PaymentStatusSummary,
    RevenueByMonthItem,
    RevenueReportResponse,
    SalesByEmployeeItem,
    SalesByMonthItem,
    StageCountItem,
    WinLossItem,
)


def _metrics_for_scope(
    db: Session,
    employee_id: Optional[int],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Shared KPI payload for employee / org / filtered scope."""
    lead_counts = AnalyticsRepository.lead_counts_summary(
        db,
        employee_id=employee_id,
        custom_from=date_from,
        custom_to=date_to,
    )
    payment_status = AnalyticsRepository.payment_status_summary(
        db, employee_id=employee_id
    )
    payment_collected = AnalyticsRepository.payment_collected_summary(
        db,
        employee_id=employee_id,
        custom_from=date_from,
        custom_to=date_to,
    )
    stages = AnalyticsRepository.leads_by_stage(
        db,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
    )
    exam = AnalyticsRepository.exam_stats(db, employee_id=employee_id)
    # Targets / incentives are lead-count based (leads = sales)
    month_leads = lead_counts["this_month"]
    target = AnalyticsRepository.sales_target_summary(
        db,
        employee_id=employee_id,
        achieved=Decimal(str(month_leads)),
    )
    incentive = AnalyticsRepository.incentive_status(
        db,
        employee_id=employee_id,
        lead_count=month_leads,
    )

    return {
        "lead_counts": LeadCountSummary(**lead_counts),
        "payment_status": PaymentStatusSummary(**payment_status),
        "payment_collected": PaymentCollectedSummary(**payment_collected),
        "leads_by_stage": [StageCountItem(**s) for s in stages],
        "target_achieved": target["target_achieved"],
        "monthly_target": target["monthly_target"],
        "target_status": target["target_status"],
        "target_assigned": target.get("target_assigned", False),
        "target_source": target.get("target_source", "default"),
        "incentive": IncentiveStatusSummary(**incentive),
        "exam_stats": ExamStatsSummary(**exam),
        "total_leads": lead_counts["total"],
    }


def _employee_overviews(
    db: Session,
    employee_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[EmployeeOverviewItem]:
    items: list[EmployeeOverviewItem] = []
    for user in AnalyticsRepository.list_active_employees(db, employee_id):
        metrics = _metrics_for_scope(
            db,
            employee_id=user.id,
            date_from=date_from,
            date_to=date_to,
        )
        items.append(
            EmployeeOverviewItem(
                employee_id=user.id,
                employee_code=user.employee_id,
                employee_name=user.name or "Unknown",
                **metrics,
            )
        )
    return items


def _enrich_performance(
    db: Session,
    rows: list[dict],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[EmployeePerformanceItem]:
    enriched: list[EmployeePerformanceItem] = []
    for row in rows:
        emp_id = row.get("employee_id")
        metrics = (
            _metrics_for_scope(
                db,
                employee_id=emp_id,
                date_from=date_from,
                date_to=date_to,
            )
            if emp_id is not None
            else None
        )
        # Monthly target progress always uses this-month lead count
        month_leads = (
            metrics["lead_counts"].this_month if metrics else 0
        )
        target = (
            AnalyticsRepository.sales_target_summary(
                db,
                employee_id=emp_id,
                achieved=Decimal(str(month_leads)),
            )
            if emp_id is not None
            else None
        )
        incentive = (
            AnalyticsRepository.incentive_status(
                db,
                employee_id=emp_id,
                lead_count=month_leads,
            )
            if emp_id is not None
            else None
        )
        enriched.append(
            EmployeePerformanceItem(
                employee_id=emp_id,
                employee_code=row.get("employee_code"),
                employee_name=row.get("employee_name") or "Unknown",
                leads_assigned=row.get("leads_assigned", 0),
                leads_converted=row.get("leads_converted", 0),
                total_leads=row.get("total_leads", 0),
                revenue=row.get("revenue", Decimal("0")),
                conversion_rate=row.get("conversion_rate", 0.0),
                target_achieved=(
                    Decimal(str(target["target_achieved"]))
                    if target
                    else Decimal("0")
                ),
                monthly_target=(
                    Decimal(str(target["monthly_target"]))
                    if target
                    else Decimal("0")
                ),
                target_status=(
                    target["target_status"] if target else "not_started"
                ),
                target_assigned=(
                    target.get("target_assigned", False) if target else False
                ),
                target_source=(
                    target.get("target_source", "default") if target else "default"
                ),
                incentive_amount=(
                    Decimal(str(incentive.get("amount") or 0))
                    if incentive
                    else Decimal("0")
                ),
                incentive_rate=Decimal("0"),
                exam_attended=(
                    metrics["exam_stats"].attended if metrics else 0
                ),
                exam_certified=(
                    metrics["exam_stats"].certified if metrics else 0
                ),
            )
        )
    return enriched


class DashboardService:

    @staticmethod
    def employee_dashboard(
        db: Session,
        employee_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> EmployeeDashboardResponse:
        metrics = _metrics_for_scope(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        return EmployeeDashboardResponse(**metrics)

    @staticmethod
    def admin_dashboard(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
    ) -> AdminDashboardResponse:
        overview = _metrics_for_scope(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        employees = _employee_overviews(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Prefer summed per-employee incentive amounts for admin overview
        slab_progress = AnalyticsRepository.incentive_status(
            db,
            employee_id=employee_id,
        )
        total_incentive = sum(
            (e.incentive.amount for e in employees), Decimal("0")
        )
        total_leads = sum((e.incentive.lead_count for e in employees), 0)
        overview["incentive"] = IncentiveStatusSummary(
            eligible=total_incentive > 0 or bool(slab_progress.get("eligible")),
            amount=total_incentive,
            slab="per-employee",
            lead_count=total_leads,
            next_bracket_leads=None,
            next_bracket_incentive=None,
        )

        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
        )
        top = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            limit=5,
        )
        monthly = AnalyticsRepository.monthly_sales(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            months=6,
        )
        monthly_items = [
            MonthlySalesItem(
                month=m["month"],
                year=m["year"],
                revenue=m["revenue"],
                leads_won=m.get("leads_won", m.get("deals", 0)),
            )
            for m in monthly
        ]
        revenue_by_month = [
            RevenueByMonthItem(
                month=m["month"],
                year=m["year"],
                revenue=m["revenue"],
                label=f"{m['month']} {m['year']}",
            )
            for m in monthly
        ]

        lead_counts = overview["lead_counts"]
        exam = overview["exam_stats"]
        conversion_rate = AnalyticsRepository.conversion_rate(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )

        return AdminDashboardResponse(
            **overview,
            total_employees=(
                1
                if employee_id is not None
                else AnalyticsRepository.count_employees(db)
            ),
            total_revenue=AnalyticsRepository.payment_collected(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
            ),
            leads_this_week=lead_counts.this_week,
            conversion_rate=conversion_rate,
            certificates_issued=exam.certified,
            revenue_by_month=revenue_by_month,
            employee_performance=_enrich_performance(
                db, performance, date_from=date_from, date_to=date_to
            ),
            monthly_sales_trend=monthly_items,
            top_performers=_enrich_performance(
                db, top, date_from=date_from, date_to=date_to
            ),
            employees=employees,
        )


class ReportService:

    @staticmethod
    def employee_report(
        db: Session,
        employee_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> EmployeeReportResponse:
        from app.repositories.user_repository import UserRepository

        user = UserRepository.get_by_id(db, employee_id)
        if not user:
            raise ValueError("Employee not found.")

        metrics = _metrics_for_scope(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        leads_created = AnalyticsRepository.count_leads(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            stage=stage,
            source=source,
        )
        leads_converted = AnalyticsRepository.count_leads(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            stage="won",
            source=source,
        )
        revenue = AnalyticsRepository.payment_collected(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        conversion_rate = (
            (leads_converted / leads_created * 100) if leads_created else 0.0
        )
        follow_ups = AnalyticsRepository.follow_up_activity_count(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )

        return EmployeeReportResponse(
            **metrics,
            employee_id=employee_id,
            employee_name=user.name,
            employee_code=user.employee_id,
            leads_created=leads_created,
            leads_converted=leads_converted,
            revenue_generated=revenue,
            conversion_rate=round(conversion_rate, 2),
            follow_up_activity=follow_ups,
        )

    @staticmethod
    def admin_report(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AdminReportResponse:
        overview = _metrics_for_scope(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        employees = _employee_overviews(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        slab_progress = AnalyticsRepository.incentive_status(
            db,
            employee_id=employee_id,
        )
        total_incentive = sum(
            (e.incentive.amount for e in employees), Decimal("0")
        )
        total_leads = sum((e.incentive.lead_count for e in employees), 0)
        overview["incentive"] = IncentiveStatusSummary(
            eligible=total_incentive > 0 or bool(slab_progress.get("eligible")),
            amount=total_incentive,
            slab="per-employee",
            lead_count=total_leads,
            next_bracket_leads=None,
            next_bracket_incentive=None,
        )

        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            stage=stage,
            source=source,
        )
        enriched = _enrich_performance(
            db, performance, date_from=date_from, date_to=date_to
        )
        monthly = AnalyticsRepository.monthly_sales(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        sources = AnalyticsRepository.lead_source_analysis(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            stage=stage,
        )
        win_loss = AnalyticsRepository.win_loss_analysis(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            source=source,
        )

        employee_reports = [
            ReportService.employee_report(
                db,
                employee_id=item.employee_id,
                date_from=date_from,
                date_to=date_to,
                stage=stage,
                source=source,
            )
            for item in employees
        ]

        sales_by_employee = [
            SalesByEmployeeItem(
                employee_id=p.employee_id,
                employee_name=p.employee_name,
                revenue=p.revenue,
                deals=p.leads_converted,
                target_achieved=p.target_achieved,
                monthly_target=p.monthly_target,
                target_status=p.target_status,
                target_assigned=p.target_assigned,
                target_source=p.target_source,
                incentive_amount=p.incentive_amount,
            )
            for p in enriched
        ]

        return AdminReportResponse(
            **overview,
            total_employees=(
                1
                if employee_id is not None
                else AnalyticsRepository.count_employees(db)
            ),
            total_revenue=AnalyticsRepository.payment_collected(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
            ),
            employee_performance=enriched,
            sales_by_month=[
                SalesByMonthItem(
                    month=m["month"],
                    year=m["year"],
                    revenue=m["revenue"],
                    deals=m.get("deals", 0),
                )
                for m in monthly
            ],
            sales_by_employee=sales_by_employee,
            lead_source_analysis=[LeadSourceItem(**s) for s in sources],
            win_loss_analysis=WinLossItem(**win_loss),
            employees=employees,
            employee_reports=employee_reports,
        )

    @staticmethod
    def revenue_report(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
    ) -> RevenueReportResponse:
        collected = AnalyticsRepository.payment_collected_summary(
            db,
            employee_id=employee_id,
            custom_from=date_from,
            custom_to=date_to,
        )
        monthly = AnalyticsRepository.monthly_sales(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
        )
        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
        )
        enriched = _enrich_performance(
            db, performance, date_from=date_from, date_to=date_to
        )
        return RevenueReportResponse(
            total_revenue=AnalyticsRepository.payment_collected(
                db,
                employee_id=employee_id,
                date_from=date_from,
                date_to=date_to,
            ),
            payment_collected=PaymentCollectedSummary(**collected),
            sales_by_month=[
                SalesByMonthItem(
                    month=m["month"],
                    year=m["year"],
                    revenue=m["revenue"],
                    deals=m.get("deals", 0),
                )
                for m in monthly
            ],
            sales_by_employee=[
                SalesByEmployeeItem(
                    employee_id=p.employee_id,
                    employee_name=p.employee_name,
                    revenue=p.revenue,
                    deals=p.leads_converted,
                    target_achieved=p.target_achieved,
                    monthly_target=p.monthly_target,
                    target_status=p.target_status,
                    target_assigned=p.target_assigned,
                    target_source=p.target_source,
                    incentive_amount=p.incentive_amount,
                )
                for p in enriched
            ],
        )

    @staticmethod
    def employee_performance_report(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> EmployeePerformanceReportResponse:
        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            stage=stage,
            source=source,
        )
        items = _enrich_performance(
            db, performance, date_from=date_from, date_to=date_to
        )
        return EmployeePerformanceReportResponse(
            items=items,
            total=len(items),
        )

    @staticmethod
    def leads_by_stage_report(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        source: Optional[str] = None,
    ) -> LeadsByStageReportResponse:
        stages = AnalyticsRepository.leads_by_stage(
            db,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            source=source,
        )
        items = [StageCountItem(**s) for s in stages]
        return LeadsByStageReportResponse(
            items=items,
            total=sum(i.count for i in items),
        )

    @staticmethod
    def _parse_month(month: Optional[str]) -> tuple[date, date, str]:
        """
        Parse YYYY-MM into inclusive month bounds.
        Defaults to the current calendar month.
        """
        from calendar import monthrange

        from app.core.date_utils import today

        current = today()
        if month:
            try:
                year_str, month_str = month.strip().split("-", 1)
                year = int(year_str)
                month_num = int(month_str)
                if month_num < 1 or month_num > 12:
                    raise ValueError
            except ValueError as ex:
                raise ValueError(
                    "Invalid month. Use format YYYY-MM (e.g. 2026-07)."
                ) from ex
        else:
            year = current.year
            month_num = current.month

        start = date(year, month_num, 1)
        end = date(year, month_num, monthrange(year, month_num)[1])
        label = f"{year:04d}-{month_num:02d}"
        return start, end, label

    @staticmethod
    def incentive_report(
        db: Session,
        month: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> IncentiveReportResponse:
        date_from, date_to, month_label = ReportService._parse_month(month)

        employees = AnalyticsRepository.list_active_employees(
            db, employee_id=employee_id
        )
        # If filtering a specific id that is inactive/missing, still try that user
        if employee_id is not None and not employees:
            from app.repositories.user_repository import UserRepository
            from app.db.models.user import UserRole

            user = UserRepository.get_by_id(db, employee_id)
            if not user or user.role != UserRole.employee:
                raise ValueError("Employee not found.")
            employees = [user]

        items: list[IncentiveReportItem] = []
        total_leads = 0
        total_incentive = Decimal("0")
        eligible_count = 0

        for user in employees:
            status = AnalyticsRepository.incentive_status(
                db,
                employee_id=user.id,
                date_from=date_from,
                date_to=date_to,
            )
            item = IncentiveReportItem(
                employee_id=user.id,
                employee_code=user.employee_id,
                employee_name=user.name or "Unknown",
                eligible=bool(status.get("eligible")),
                amount=Decimal(str(status.get("amount") or 0)),
                slab=status.get("slab"),
                lead_count=int(status.get("lead_count") or 0),
                next_bracket_leads=status.get("next_bracket_leads"),
                next_bracket_incentive=status.get("next_bracket_incentive"),
            )
            items.append(item)
            total_leads += item.lead_count
            total_incentive += item.amount
            if item.eligible:
                eligible_count += 1

        items.sort(key=lambda x: x.amount, reverse=True)

        return IncentiveReportResponse(
            month=month_label,
            date_from=date_from,
            date_to=date_to,
            items=items,
            totals=IncentiveReportTotals(
                lead_count=total_leads,
                incentive_amount=total_incentive,
                eligible_count=eligible_count,
                employee_count=len(items),
            ),
        )
