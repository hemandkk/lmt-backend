from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeadCountSummary(BaseModel):
    total: int = 0
    today: int = 0
    this_week: int = 0
    this_month: int = 0
    custom: Optional[int] = None


class PaymentStatusSummary(BaseModel):
    advanced_paid: int = 0
    fifty_percent_paid: int = 0
    hundred_percent_paid: int = 0


class PaymentCollectedSummary(BaseModel):
    today: Decimal = Decimal("0")
    this_week: Decimal = Decimal("0")
    this_month: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    custom: Optional[Decimal] = None


class EmployeeDashboardResponse(BaseModel):
    lead_counts: LeadCountSummary
    payment_status: PaymentStatusSummary
    payment_collected: PaymentCollectedSummary


class StageCountItem(BaseModel):
    stage: str
    count: int


class EmployeePerformanceItem(BaseModel):
    employee_id: Optional[int] = None
    employee_code: Optional[str] = None
    employee_name: str
    leads_assigned: int = 0
    leads_converted: int = 0
    revenue: Decimal = Decimal("0")
    conversion_rate: float = 0.0


class MonthlySalesItem(BaseModel):
    month: str
    year: int
    revenue: Decimal = Decimal("0")
    leads_won: int = 0


class AdminDashboardResponse(BaseModel):
    total_employees: int
    total_leads: int
    total_revenue: Decimal
    leads_by_stage: list[StageCountItem]
    employee_performance: list[EmployeePerformanceItem]
    monthly_sales_trend: list[MonthlySalesItem]
    top_performers: list[EmployeePerformanceItem]


class EmployeeReportResponse(BaseModel):
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    leads_created: int = 0
    leads_converted: int = 0
    revenue_generated: Decimal = Decimal("0")
    conversion_rate: float = 0.0
    follow_up_activity: int = 0


class SalesByMonthItem(BaseModel):
    month: str
    year: int
    revenue: Decimal = Decimal("0")
    deals: int = 0


class SalesByEmployeeItem(BaseModel):
    employee_id: Optional[int] = None
    employee_name: str
    revenue: Decimal = Decimal("0")
    deals: int = 0


class LeadSourceItem(BaseModel):
    source: str
    count: int
    converted: int = 0
    revenue: Decimal = Decimal("0")


class WinLossItem(BaseModel):
    won: int = 0
    lost: int = 0
    win_rate: float = 0.0


class AdminReportResponse(BaseModel):
    employee_performance: list[EmployeePerformanceItem]
    sales_by_month: list[SalesByMonthItem]
    sales_by_employee: list[SalesByEmployeeItem]
    lead_source_analysis: list[LeadSourceItem]
    win_loss_analysis: WinLossItem


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    prospect_id: Optional[int] = None
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    prospect_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    description: str
    meta_data: Optional[str] = None
    created_at: datetime
    user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    page_size: int


class ExportRequest(BaseModel):
    export_type: str  # leads | employee_performance | sales | dashboard
    format: str  # xlsx | csv | pdf
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    employee_id: Optional[int] = None
    stage: Optional[str] = None
    source: Optional[str] = None
