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
    EmployeeReportResponse,
    ExamStatsSummary,
    IncentiveStatusSummary,
    LeadCountSummary,
    LeadSourceItem,
    MonthlySalesItem,
    PaymentCollectedSummary,
    PaymentStatusSummary,
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
    month_collected = payment_collected["this_month"]
    target = AnalyticsRepository.sales_target_summary(
        db,
        employee_id=employee_id,
        achieved=month_collected,
    )
    incentive = AnalyticsRepository.incentive_status(
        db,
        employee_id=employee_id,
        collection=month_collected,
    )

    return {
        "lead_counts": LeadCountSummary(**lead_counts),
        "payment_status": PaymentStatusSummary(**payment_status),
        "payment_collected": PaymentCollectedSummary(**payment_collected),
        "leads_by_stage": [StageCountItem(**s) for s in stages],
        "target_achieved": target["target_achieved"],
        "monthly_target": target["monthly_target"],
        "target_status": target["target_status"],
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
) -> list[EmployeePerformanceItem]:
    enriched: list[EmployeePerformanceItem] = []
    for row in rows:
        emp_id = row.get("employee_id")
        metrics = (
            _metrics_for_scope(db, employee_id=emp_id)
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
                revenue=row.get("revenue", Decimal("0")),
                conversion_rate=row.get("conversion_rate", 0.0),
                target_achieved=(
                    metrics["target_achieved"] if metrics else Decimal("0")
                ),
                monthly_target=(
                    metrics["monthly_target"] if metrics else Decimal("0")
                ),
                target_status=(
                    metrics["target_status"] if metrics else "not_started"
                ),
                incentive_amount=(
                    metrics["incentive"].amount if metrics else Decimal("0")
                ),
                incentive_rate=(
                    metrics["incentive"].rate if metrics else Decimal("0")
                ),
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
        org_collection = overview["payment_collected"].this_month
        slab_progress = AnalyticsRepository.incentive_status(
            db,
            employee_id=employee_id,
            collection=org_collection,
        )
        total_incentive = sum(
            (e.incentive.amount for e in employees), Decimal("0")
        )
        overview["incentive"] = IncentiveStatusSummary(
            eligible=total_incentive > 0 or bool(slab_progress.get("eligible")),
            amount=total_incentive,
            rate=Decimal(str(slab_progress.get("rate") or 0)),
            slab=slab_progress.get("slab") or "per-employee",
            collection=org_collection,
            next_bracket_amount=slab_progress.get("next_bracket_amount"),
            next_bracket_rate=slab_progress.get("next_bracket_rate"),
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
            employee_performance=_enrich_performance(db, performance),
            monthly_sales_trend=[
                MonthlySalesItem(
                    month=m["month"],
                    year=m["year"],
                    revenue=m["revenue"],
                    leads_won=m.get("leads_won", m.get("deals", 0)),
                )
                for m in monthly
            ],
            top_performers=_enrich_performance(db, top),
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
        org_collection = overview["payment_collected"].this_month
        slab_progress = AnalyticsRepository.incentive_status(
            db,
            employee_id=employee_id,
            collection=org_collection,
        )
        total_incentive = sum(
            (e.incentive.amount for e in employees), Decimal("0")
        )
        overview["incentive"] = IncentiveStatusSummary(
            eligible=total_incentive > 0 or bool(slab_progress.get("eligible")),
            amount=total_incentive,
            rate=Decimal(str(slab_progress.get("rate") or 0)),
            slab=slab_progress.get("slab") or "per-employee",
            collection=org_collection,
            next_bracket_amount=slab_progress.get("next_bracket_amount"),
            next_bracket_rate=slab_progress.get("next_bracket_rate"),
        )

        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            stage=stage,
            source=source,
        )
        enriched = _enrich_performance(db, performance)
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
