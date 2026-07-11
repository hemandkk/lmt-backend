from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.user import UserRole
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AdminReportResponse,
    EmployeeDashboardResponse,
    EmployeePerformanceItem,
    EmployeeReportResponse,
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


class DashboardService:

    @staticmethod
    def employee_dashboard(
        db: Session,
        employee_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> EmployeeDashboardResponse:
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

        return EmployeeDashboardResponse(
            lead_counts=LeadCountSummary(**lead_counts),
            payment_status=PaymentStatusSummary(**payment_status),
            payment_collected=PaymentCollectedSummary(**payment_collected),
        )

    @staticmethod
    def admin_dashboard(
        db: Session,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> AdminDashboardResponse:
        performance = AnalyticsRepository.employee_performance(
            db, date_from=date_from, date_to=date_to
        )
        top = AnalyticsRepository.employee_performance(
            db, date_from=date_from, date_to=date_to, limit=5
        )
        monthly = AnalyticsRepository.monthly_sales(
            db, date_from=date_from, date_to=date_to
        )
        stages = AnalyticsRepository.leads_by_stage(
            db, date_from=date_from, date_to=date_to
        )

        return AdminDashboardResponse(
            total_employees=AnalyticsRepository.count_employees(db),
            total_leads=AnalyticsRepository.count_leads(
                db, date_from=date_from, date_to=date_to
            ),
            total_revenue=AnalyticsRepository.payment_collected(
                db, date_from=date_from, date_to=date_to
            ),
            leads_by_stage=[StageCountItem(**s) for s in stages],
            employee_performance=[EmployeePerformanceItem(**p) for p in performance],
            monthly_sales_trend=[
                MonthlySalesItem(
                    month=m["month"],
                    year=m["year"],
                    revenue=m["revenue"],
                    leads_won=m.get("leads_won", m.get("deals", 0)),
                )
                for m in monthly
            ],
            top_performers=[EmployeePerformanceItem(**p) for p in top],
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
            employee_id=employee_id,
            employee_name=user.name,
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
        performance = AnalyticsRepository.employee_performance(
            db,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            stage=stage,
            source=source,
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

        sales_by_employee = [
            SalesByEmployeeItem(
                employee_id=p["employee_id"],
                employee_name=p["employee_name"],
                revenue=p["revenue"],
                deals=p["leads_converted"],
            )
            for p in performance
        ]

        return AdminReportResponse(
            employee_performance=[EmployeePerformanceItem(**p) for p in performance],
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
        )
