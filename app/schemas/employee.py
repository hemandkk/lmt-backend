from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class EmployeeCreate(BaseModel):
    model_config = _alias_config()

    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_code: Optional[str] = Field(default=None, alias="employeeId")
    monthly_target: Optional[Decimal] = Field(
        default=None, gt=0, alias="monthlyTarget"
    )
    is_active: bool = Field(default=True, alias="isActive")
    role: Optional[str] = Field(default="employee")
    reports_to_manager_id: Optional[int] = Field(
        default=None, alias="reportsToManagerId"
    )
    reports_to_sales_head_id: Optional[int] = Field(
        default=None, alias="reportsToSalesHeadId"
    )

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, value: Any) -> Any:
        if value is None or value == "":
            return "employee"
        from app.core.roles import normalize_role

        return normalize_role(value).value

    @field_validator(
        "reports_to_manager_id", "reports_to_sales_head_id", mode="before"
    )
    @classmethod
    def empty_supervisor_to_none(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        return value


class EmployeeUpdate(BaseModel):
    model_config = _alias_config()

    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6)
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_code: Optional[str] = Field(default=None, alias="employeeId")
    monthly_target: Optional[Decimal] = Field(
        default=None, gt=0, alias="monthlyTarget"
    )
    clear_monthly_target: bool = Field(
        default=False,
        alias="clearMonthlyTarget",
        description="If true, clear assigned target (use master default).",
    )
    is_active: Optional[bool] = Field(default=None, alias="isActive")
    role: Optional[str] = None
    reports_to_manager_id: Optional[int] = Field(
        default=None, alias="reportsToManagerId"
    )
    reports_to_sales_head_id: Optional[int] = Field(
        default=None, alias="reportsToSalesHeadId"
    )

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        from app.core.roles import normalize_role

        return normalize_role(value).value

    @field_validator(
        "reports_to_manager_id", "reports_to_sales_head_id", mode="before"
    )
    @classmethod
    def empty_supervisor_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class EmployeeResponse(BaseModel):
    model_config = _alias_config()

    id: int
    name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeId"
    )
    role: str
    status: str = "active"
    is_active: bool = Field(serialization_alias="isActive")
    # Frontend edit form uses monthlyTarget (assigned override; null = master default)
    monthly_target: Optional[Decimal] = Field(
        default=None, serialization_alias="monthlyTarget"
    )
    assigned_target: Optional[Decimal] = Field(
        default=None, serialization_alias="assignedTarget"
    )
    effective_target: Decimal = Field(serialization_alias="effectiveTarget")
    target_assigned: bool = Field(serialization_alias="targetAssigned")
    target_source: str = Field(serialization_alias="targetSource")
    leads_assigned: int = Field(default=0, serialization_alias="leadsAssigned")
    revenue: Decimal = Field(default=Decimal("0"))
    reports_to_manager_id: Optional[int] = Field(
        default=None, serialization_alias="reportsToManagerId"
    )
    reports_to_manager_name: Optional[str] = Field(
        default=None, serialization_alias="reportsToManagerName"
    )
    reports_to_sales_head_id: Optional[int] = Field(
        default=None, serialization_alias="reportsToSalesHeadId"
    )
    reports_to_sales_head_name: Optional[str] = Field(
        default=None, serialization_alias="reportsToSalesHeadName"
    )
    last_login: Optional[datetime] = Field(
        default=None, serialization_alias="lastLogin"
    )
    created_at: Optional[datetime] = Field(
        default=None, serialization_alias="createdAt"
    )
    updated_at: Optional[datetime] = Field(
        default=None, serialization_alias="updatedAt"
    )


class EmployeeListResponse(BaseModel):
    model_config = _alias_config()

    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total_pages: int = Field(serialization_alias="totalPages")

    @staticmethod
    def build(
        items: list[EmployeeResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "EmployeeListResponse":
        return EmployeeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if page_size else 0,
        )
