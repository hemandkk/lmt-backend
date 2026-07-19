from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


PerformanceStatus = Literal["high", "average", "low"]


class TeamAssignmentUpdate(BaseModel):
    model_config = _alias_config()

    reports_to_manager_id: Optional[int] = Field(
        default=None, alias="reportsToManagerId"
    )
    reports_to_sales_head_id: Optional[int] = Field(
        default=None, alias="reportsToSalesHeadId"
    )


class TeamMemberItem(BaseModel):
    model_config = _alias_config()

    id: int
    employee_id: Optional[str] = Field(
        default=None, serialization_alias="employeeId"
    )
    name: Optional[str] = None
    email: str
    is_active: bool = Field(serialization_alias="isActive")
    monthly_target: Optional[Decimal] = Field(
        default=None, serialization_alias="monthlyTarget"
    )
    reports_to_manager_id: Optional[int] = Field(
        default=None, serialization_alias="reportsToManagerId"
    )
    reports_to_sales_head_id: Optional[int] = Field(
        default=None, serialization_alias="reportsToSalesHeadId"
    )


class TeamMemberListResponse(BaseModel):
    model_config = _alias_config()

    items: list[TeamMemberItem]
    total: int


class TeamSupervisorItem(BaseModel):
    model_config = _alias_config()

    id: int
    employee_id: Optional[str] = Field(
        default=None, serialization_alias="employeeId"
    )
    name: Optional[str] = None
    email: str
    role: str
    is_active: bool = Field(serialization_alias="isActive")


class TeamSupervisorListResponse(BaseModel):
    model_config = _alias_config()

    items: list[TeamSupervisorItem]
    total: int


class TeamSalesResponse(BaseModel):
    model_config = _alias_config()

    total_revenue: Decimal = Field(serialization_alias="totalRevenue")
    total_admissions: int = Field(serialization_alias="totalAdmissions")
    leads_converted: int = Field(serialization_alias="leadsConverted")
    conversion_rate: float = Field(serialization_alias="conversionRate")
    monthly: list[dict[str, Any]] = []
    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    supervisor_id: Optional[int] = Field(
        default=None, serialization_alias="supervisorId"
    )


class TeamPerformanceItem(BaseModel):
    model_config = _alias_config()

    employee_id: int = Field(serialization_alias="employeeId")
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeCode"
    )
    employee_name: Optional[str] = Field(
        default=None, serialization_alias="employeeName"
    )
    admissions: int
    leads_converted: int = Field(serialization_alias="leadsConverted")
    collection: Decimal
    monthly_target: Decimal = Field(serialization_alias="monthlyTarget")
    target_revenue: Decimal = Field(serialization_alias="targetRevenue")
    converted_deal_value: Decimal = Field(
        serialization_alias="convertedDealValue"
    )
    conversion_rate: float = Field(serialization_alias="conversionRate")
    performance_status: PerformanceStatus = Field(
        serialization_alias="performanceStatus"
    )


class TeamPerformanceResponse(BaseModel):
    model_config = _alias_config()

    items: list[TeamPerformanceItem]
    total: int
    high_count: int = Field(serialization_alias="highCount")
    average_count: int = Field(serialization_alias="averageCount")
    low_count: int = Field(serialization_alias="lowCount")
    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    supervisor_id: Optional[int] = Field(
        default=None, serialization_alias="supervisorId"
    )


class TeamPaymentsResponse(BaseModel):
    model_config = _alias_config()

    total_collected: Decimal = Field(serialization_alias="totalCollected")
    collected: dict[str, Any]
    lead_payment_status: dict[str, Any] = Field(
        serialization_alias="leadPaymentStatus"
    )
    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    supervisor_id: Optional[int] = Field(
        default=None, serialization_alias="supervisorId"
    )


class TeamAnalyticsResponse(BaseModel):
    model_config = _alias_config()

    total_admissions: int = Field(serialization_alias="totalAdmissions")
    total_revenue: Decimal = Field(serialization_alias="totalRevenue")
    conversion_rate: float = Field(serialization_alias="conversionRate")
    leads_by_stage: list[dict[str, Any]] = Field(
        default_factory=list, serialization_alias="leadsByStage"
    )
    exam_stats: dict[str, Any] = Field(
        default_factory=dict, serialization_alias="examStats"
    )
    lead_counts: dict[str, Any] = Field(
        default_factory=dict, serialization_alias="leadCounts"
    )
    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    supervisor_id: Optional[int] = Field(
        default=None, serialization_alias="supervisorId"
    )


class TeamOverviewResponse(BaseModel):
    model_config = _alias_config()

    team_size: int = Field(serialization_alias="teamSize")
    total_admissions: int = Field(serialization_alias="totalAdmissions")
    total_collection: Decimal = Field(serialization_alias="totalCollection")
    high_performers: int = Field(serialization_alias="highPerformers")
    average_performers: int = Field(serialization_alias="averagePerformers")
    low_performers: int = Field(serialization_alias="lowPerformers")
    conversion_rate: float = Field(serialization_alias="conversionRate")
    date_from: Optional[date] = Field(
        default=None, serialization_alias="dateFrom"
    )
    date_to: Optional[date] = Field(default=None, serialization_alias="dateTo")
    employee_id: Optional[int] = Field(
        default=None, serialization_alias="employeeId"
    )
    supervisor_id: Optional[int] = Field(
        default=None, serialization_alias="supervisorId"
    )
