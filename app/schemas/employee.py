from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
