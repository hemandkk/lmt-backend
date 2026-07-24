from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.date_utils import today
from app.db.models.expense import Expense, ExpenseType
from app.db.models.prospect import AdmissionStage, Prospect
from app.db.models.user import User, UserRole
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.incentive_repository import IncentiveRepository
from app.schemas.dashboard import (
    IncentiveReleaseListResponse,
    IncentiveReleaseMonthItem,
    IncentiveReleaseResponse,
    IncentiveReleaseSummary,
)


def _parse_month(month: Optional[str]) -> tuple[date, date, str]:
    """Parse YYYY-MM into inclusive month bounds. Defaults to current calendar month."""
    current = today()
    if month:
        try:
            year_str, month_str = month.strip().split("-", 1)
            year = int(year_str)
            month_num = int(month_str)
            if month_num < 1 or month_num > 12:
                raise ValueError
        except ValueError as ex:
            raise ValueError("Invalid month. Use format YYYY-MM (e.g. 2026-07).") from ex
    else:
        year = current.year
        month_num = current.month

    start = date(year, month_num, 1)
    end = date(year, month_num, monthrange(year, month_num)[1])
    label = f"{year:04d}-{month_num:02d}"
    return start, end, label


def _resolve_slab_rate(slabs: list, admission_count: int) -> Decimal:
    """Determine the incentive per admission based on the slab brackets."""
    for slab in slabs:
        min_leads = int(slab.min_leads or 0)
        max_leads = int(slab.max_leads) if slab.max_leads is not None else None
        if admission_count >= min_leads and (max_leads is None or admission_count <= max_leads):
            return Decimal(str(slab.incentive_amount or 0)).quantize(Decimal("0.01"))
    return Decimal("0")


def _get_completed_stages() -> list[str]:
    """Admission stages considered as 'completed' for incentive purposes."""
    return [AdmissionStage.completed.value, AdmissionStage.delivered.value]


def _compute_employee_monthly(
    db: Session,
    employee_id: int,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    report_date_to: date,
    slabs: list,
) -> IncentiveReleaseResponse:
    """Compute monthly incentive release data for a single employee."""
    completed_stages = _get_completed_stages()
    report_label = f"{report_date_to.year:04d}-{report_date_to.month:02d}"

    # Report cutoff: end of report month in UTC
    report_cutoff = datetime.combine(
        report_date_to, datetime.max.time()
    ).replace(tzinfo=timezone.utc)

    # Get total paid incentive amount for this employee
    total_paid = Decimal(
        str(
            db.query(func.coalesce(func.sum(Expense.amount), 0))
            .filter(
                Expense.employee_id == employee_id,
                Expense.expense_type == ExpenseType.incentive,
            )
            .scalar() or 0
        )
    )

    monthly_items: list[IncentiveReleaseMonthItem] = []
    total_admissions = 0
    total_booked = Decimal("0")
    total_completed = 0
    total_receivable = Decimal("0")

    year, m = start_year, start_month
    while (year, m) <= (end_year, end_month):
        month_label = f"{year:04d}-{m:02d}"

        # Count admissions created in this month
        admissions_count = int(
            db.query(func.count(Prospect.id)).filter(
                extract("year", Prospect.created_at) == year,
                extract("month", Prospect.created_at) == m,
                Prospect.assigned_to_id == employee_id,
            ).scalar() or 0
        )

        # Determine slab rate
        slab_rate = _resolve_slab_rate(slabs, admissions_count)
        booked_incentive = Decimal(str(admissions_count)) * slab_rate

        # Count completed admissions (created in this month, currently completed, updated_at <= report cutoff)
        completed_count = int(
            db.query(func.count(Prospect.id)).filter(
                extract("year", Prospect.created_at) == year,
                extract("month", Prospect.created_at) == m,
                Prospect.assigned_to_id == employee_id,
                Prospect.admission_stage.in_(completed_stages),
                Prospect.updated_at <= report_cutoff,
            ).scalar() or 0
        )

        receivable_incentive = Decimal(str(completed_count)) * slab_rate

        monthly_items.append(IncentiveReleaseMonthItem(
            month=month_label,
            admissions=admissions_count,
            slab_rate=slab_rate,
            booked_incentive=booked_incentive,
            completed_admissions=completed_count,
            receivable_incentive=receivable_incentive,
        ))

        total_admissions += admissions_count
        total_booked += booked_incentive
        total_completed += completed_count
        total_receivable += receivable_incentive

        # Advance to next month
        if m == 12:
            m = 1
            year += 1
        else:
            m += 1

    balance_to_pay = total_receivable - total_paid

    return IncentiveReleaseResponse(
        month=report_label,
        date_from=date(start_year, start_month, 1),
        date_to=report_date_to,
        employee_id=employee_id,
        months=monthly_items,
        summary=IncentiveReleaseSummary(
            total_admissions=total_admissions,
            total_booked_incentive=total_booked,
            total_completed_admissions=total_completed,
            total_receivable_incentive=total_receivable,
            total_paid=total_paid,
            balance_to_pay=balance_to_pay,
        ),
    )


class IncentiveReleaseService:

    @staticmethod
    def incentive_release_report(
        db: Session,
        month: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> IncentiveReleaseResponse | IncentiveReleaseListResponse:
        """
        Monthly incentive release summary.

        When employee_id is provided: returns data for that single employee.
        When employee_id is None (admin): returns per-employee breakdown.
        """
        report_date_from, report_date_to, report_label = _parse_month(month)
        slabs = IncentiveRepository.get_all(db)

        # Single employee view
        if employee_id is not None:
            user = db.query(User).filter(User.id == employee_id).first()
            earliest = db.query(func.min(Prospect.created_at)).filter(
                Prospect.assigned_to_id == employee_id
            ).scalar()

            if earliest is None:
                return IncentiveReleaseResponse(
                    month=report_label,
                    date_from=report_date_from,
                    date_to=report_date_to,
                    employee_id=employee_id,
                    employee_code=user.employee_id if user else None,
                    employee_name=user.name if user else None,
                    months=[],
                    summary=IncentiveReleaseSummary(),
                )

            earliest_date = earliest.date() if hasattr(earliest, 'date') else earliest
            result = _compute_employee_monthly(
                db, employee_id,
                earliest_date.year, earliest_date.month,
                report_date_to.year, report_date_to.month,
                report_date_to, slabs,
            )
            result.employee_code = user.employee_id if user else None
            result.employee_name = user.name if user else None
            return result

        # Admin: all employees view
        employees = AnalyticsRepository.list_active_employees(db)
        if not employees:
            return IncentiveReleaseListResponse(
                month=report_label,
                date_from=report_date_from,
                date_to=report_date_to,
                items=[],
            )

        items: list[IncentiveReleaseResponse] = []
        for emp in employees:
            earliest = db.query(func.min(Prospect.created_at)).filter(
                Prospect.assigned_to_id == emp.id
            ).scalar()

            if earliest is None:
                items.append(IncentiveReleaseResponse(
                    month=report_label,
                    date_from=report_date_from,
                    date_to=report_date_to,
                    employee_id=emp.id,
                    employee_code=emp.employee_id,
                    employee_name=emp.name or "Unknown",
                    months=[],
                    summary=IncentiveReleaseSummary(),
                ))
                continue

            earliest_date = earliest.date() if hasattr(earliest, 'date') else earliest
            result = _compute_employee_monthly(
                db, emp.id,
                earliest_date.year, earliest_date.month,
                report_date_to.year, report_date_to.month,
                report_date_to, slabs,
            )
            result.employee_code = emp.employee_id
            result.employee_name = emp.name or "Unknown"
            items.append(result)

        return IncentiveReleaseListResponse(
            month=report_label,
            date_from=report_date_from,
            date_to=report_date_to,
            items=items,
        )
