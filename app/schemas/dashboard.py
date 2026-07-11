from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class LeadCountSummary(BaseModel):
    model_config = _alias_config()

    total: int = 0
    today: int = 0
    this_week: int = Field(default=0, serialization_alias="thisWeek")
    this_month: int = Field(default=0, serialization_alias="thisMonth")
    custom: Optional[int] = None


class PaymentStatusSummary(BaseModel):
    model_config = _alias_config()

    advanced_paid: int = Field(default=0, serialization_alias="advancedPaid")
    fifty_percent_paid: int = Field(
        default=0, serialization_alias="fiftyPercentPaid"
    )
    hundred_percent_paid: int = Field(
        default=0, serialization_alias="hundredPercentPaid"
    )


class PaymentCollectedSummary(BaseModel):
    model_config = _alias_config()

    today: Decimal = Decimal("0")
    this_week: Decimal = Field(default=Decimal("0"), serialization_alias="thisWeek")
    this_month: Decimal = Field(
        default=Decimal("0"), serialization_alias="thisMonth"
    )
    total: Decimal = Decimal("0")
    custom: Optional[Decimal] = None


class StageCountItem(BaseModel):
    model_config = _alias_config()

    stage: str
    count: int


class ExamStatsSummary(BaseModel):
    model_config = _alias_config()

    attended: int = 0
    certified: int = 0


class IncentiveStatusSummary(BaseModel):
    model_config = _alias_config()

    eligible: bool = False
    amount: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    slab: Optional[str] = None
    collection: Decimal = Decimal("0")
    next_bracket_amount: Optional[Decimal] = Field(
        default=None, serialization_alias="nextBracketAmount"
    )
    next_bracket_rate: Optional[Decimal] = Field(
        default=None, serialization_alias="nextBracketRate"
    )


class DashboardMetricsMixin(BaseModel):
    """Shared widgets used by employee + admin overview cards."""

    model_config = _alias_config()

    lead_counts: LeadCountSummary = Field(
        default_factory=LeadCountSummary, serialization_alias="leadCounts"
    )
    payment_status: PaymentStatusSummary = Field(
        default_factory=PaymentStatusSummary,
        serialization_alias="paymentStatus",
    )
    payment_collected: PaymentCollectedSummary = Field(
        default_factory=PaymentCollectedSummary,
        serialization_alias="paymentCollected",
    )
    leads_by_stage: list[StageCountItem] = Field(
        default_factory=list,
        serialization_alias="leadsByStage",
    )
    target_achieved: Decimal = Field(
        default=Decimal("0"), serialization_alias="targetAchieved"
    )
    monthly_target: Decimal = Field(
        default=Decimal("0"), serialization_alias="monthlyTarget"
    )
    target_status: str = Field(
        default="not_started", serialization_alias="targetStatus"
    )
    incentive: IncentiveStatusSummary = Field(
        default_factory=IncentiveStatusSummary
    )
    exam_stats: ExamStatsSummary = Field(
        default_factory=ExamStatsSummary,
        serialization_alias="examStats",
    )
    total_leads: int = Field(default=0, serialization_alias="totalLeads")


class EmployeeDashboardResponse(DashboardMetricsMixin):
    pass


class EmployeeOverviewItem(DashboardMetricsMixin):
    """Per-employee card for admin overview / reports."""

    employee_id: int = Field(serialization_alias="employeeId")
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeCode"
    )
    employee_name: str = Field(serialization_alias="employeeName")


class EmployeePerformanceItem(BaseModel):
    model_config = _alias_config()

    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeCode"
    )
    employee_name: str = Field(serialization_alias="employeeName")
    leads_assigned: int = Field(default=0, serialization_alias="leadsAssigned")
    leads_converted: int = Field(default=0, serialization_alias="leadsConverted")
    revenue: Decimal = Decimal("0")
    conversion_rate: float = Field(default=0.0, serialization_alias="conversionRate")
    target_achieved: Decimal = Field(
        default=Decimal("0"), serialization_alias="targetAchieved"
    )
    monthly_target: Decimal = Field(
        default=Decimal("0"), serialization_alias="monthlyTarget"
    )
    target_status: str = Field(
        default="not_started", serialization_alias="targetStatus"
    )
    incentive_amount: Decimal = Field(
        default=Decimal("0"), serialization_alias="incentiveAmount"
    )
    incentive_rate: Decimal = Field(
        default=Decimal("0"), serialization_alias="incentiveRate"
    )
    exam_attended: int = Field(default=0, serialization_alias="examAttended")
    exam_certified: int = Field(default=0, serialization_alias="examCertified")


class MonthlySalesItem(BaseModel):
    model_config = _alias_config()

    month: str
    year: int
    revenue: Decimal = Decimal("0")
    leads_won: int = Field(default=0, serialization_alias="leadsWon")


class AdminDashboardResponse(DashboardMetricsMixin):
    model_config = _alias_config()

    total_employees: int = Field(serialization_alias="totalEmployees")
    total_revenue: Decimal = Field(
        default=Decimal("0"), serialization_alias="totalRevenue"
    )
    employee_performance: list[EmployeePerformanceItem] = Field(
        default_factory=list,
        serialization_alias="employeePerformance",
    )
    monthly_sales_trend: list[MonthlySalesItem] = Field(
        default_factory=list,
        serialization_alias="monthlySalesTrend",
    )
    top_performers: list[EmployeePerformanceItem] = Field(
        default_factory=list,
        serialization_alias="topPerformers",
    )
    employees: list[EmployeeOverviewItem] = Field(default_factory=list)


class EmployeeReportResponse(DashboardMetricsMixin):
    model_config = _alias_config()

    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    employee_name: Optional[str] = Field(
        default=None, serialization_alias="employeeName"
    )
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeCode"
    )
    leads_created: int = Field(default=0, serialization_alias="leadsCreated")
    leads_converted: int = Field(default=0, serialization_alias="leadsConverted")
    revenue_generated: Decimal = Field(
        default=Decimal("0"), serialization_alias="revenueGenerated"
    )
    conversion_rate: float = Field(default=0.0, serialization_alias="conversionRate")
    follow_up_activity: int = Field(
        default=0, serialization_alias="followUpActivity"
    )


class SalesByMonthItem(BaseModel):
    model_config = _alias_config()

    month: str
    year: int
    revenue: Decimal = Decimal("0")
    deals: int = 0


class SalesByEmployeeItem(BaseModel):
    model_config = _alias_config()

    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    employee_name: str = Field(serialization_alias="employeeName")
    revenue: Decimal = Decimal("0")
    deals: int = 0
    target_achieved: Decimal = Field(
        default=Decimal("0"), serialization_alias="targetAchieved"
    )
    monthly_target: Decimal = Field(
        default=Decimal("0"), serialization_alias="monthlyTarget"
    )
    target_status: str = Field(
        default="not_started", serialization_alias="targetStatus"
    )
    incentive_amount: Decimal = Field(
        default=Decimal("0"), serialization_alias="incentiveAmount"
    )


class LeadSourceItem(BaseModel):
    model_config = _alias_config()

    source: str
    count: int
    converted: int = 0
    revenue: Decimal = Decimal("0")


class WinLossItem(BaseModel):
    model_config = _alias_config()

    won: int = 0
    lost: int = 0
    win_rate: float = Field(default=0.0, serialization_alias="winRate")


class AdminReportResponse(DashboardMetricsMixin):
    model_config = _alias_config()

    total_employees: int = Field(default=0, serialization_alias="totalEmployees")
    total_revenue: Decimal = Field(
        default=Decimal("0"), serialization_alias="totalRevenue"
    )
    employee_performance: list[EmployeePerformanceItem] = Field(
        default_factory=list,
        serialization_alias="employeePerformance",
    )
    sales_by_month: list[SalesByMonthItem] = Field(
        default_factory=list,
        serialization_alias="salesByMonth",
    )
    sales_by_employee: list[SalesByEmployeeItem] = Field(
        default_factory=list,
        serialization_alias="salesByEmployee",
    )
    lead_source_analysis: list[LeadSourceItem] = Field(
        default_factory=list,
        serialization_alias="leadSourceAnalysis",
    )
    win_loss_analysis: WinLossItem = Field(
        default_factory=WinLossItem,
        serialization_alias="winLossAnalysis",
    )
    employees: list[EmployeeOverviewItem] = Field(default_factory=list)
    employee_reports: list[EmployeeReportResponse] = Field(
        default_factory=list,
        serialization_alias="employeeReports",
    )


class NotificationResponse(BaseModel):
    id: int
    user_id: int = Field(serialization_alias="userId")
    prospect_id: Optional[int] = Field(
        default=None, serialization_alias="prospectId"
    )
    type: str
    title: str
    message: str
    is_read: bool = Field(serialization_alias="isRead")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = _alias_config()


class NotificationListResponse(BaseModel):
    model_config = _alias_config()

    items: list[NotificationResponse]
    total: int
    unread_count: int = Field(serialization_alias="unreadCount")
    page: int
    page_size: int = Field(serialization_alias="pageSize")


class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = Field(default=None, serialization_alias="userId")
    prospect_id: Optional[int] = Field(
        default=None, serialization_alias="prospectId"
    )
    action: str
    entity_type: str = Field(serialization_alias="entityType")
    entity_id: Optional[int] = Field(default=None, serialization_alias="entityId")
    description: str
    meta_data: Optional[str] = Field(default=None, serialization_alias="metaData")
    created_at: datetime = Field(serialization_alias="createdAt")
    user_name: Optional[str] = Field(default=None, serialization_alias="userName")

    model_config = _alias_config()


class ActivityLogListResponse(BaseModel):
    model_config = _alias_config()

    items: list[ActivityLogResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")


class ExportRequest(BaseModel):
    model_config = _alias_config()

    export_type: str = Field(alias="exportType")  # leads | employee_performance | sales | dashboard
    format: str  # xlsx | csv | pdf
    date_from: Optional[date] = Field(default=None, alias="dateFrom")
    date_to: Optional[date] = Field(default=None, alias="dateTo")
    employee_id: Optional[int] = Field(default=None, alias="employeeId")
    stage: Optional[str] = None
    source: Optional[str] = None
