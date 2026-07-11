from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _alias_config() -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


# ==========================================================
# COURSE
# ==========================================================

class CourseCreate(BaseModel):
    model_config = _alias_config()

    name: str
    course_code: Optional[str] = Field(default=None, alias="courseCode")
    specialization: Optional[str] = None
    duration: Optional[str] = None
    fees: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = Field(default=True, alias="active")


class CourseResponse(BaseModel):
    model_config = _alias_config()

    id: int
    course_code: str = Field(serialization_alias="courseCode")
    name: str
    specialization: Optional[str] = None
    duration: Optional[str] = None
    fees: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = Field(serialization_alias="active")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


# ==========================================================
# INCENTIVE SLAB
# ==========================================================

class IncentiveSlabCreate(BaseModel):
    model_config = _alias_config()

    min_amount: Decimal = Field(..., ge=0, alias="minAmount")
    max_amount: Optional[Decimal] = Field(default=None, alias="maxAmount")
    rate_percent: Decimal = Field(..., ge=0, alias="ratePercent")
    is_active: bool = Field(default=True, alias="isActive")

    @field_validator("max_amount")
    @classmethod
    def max_gte_min(cls, value, info):
        min_amount = info.data.get("min_amount")
        if value is not None and min_amount is not None and value < min_amount:
            raise ValueError("maxAmount must be >= minAmount")
        return value


class IncentiveSlabUpdate(BaseModel):
    model_config = _alias_config()

    min_amount: Optional[Decimal] = Field(default=None, ge=0, alias="minAmount")
    max_amount: Optional[Decimal] = Field(default=None, alias="maxAmount")
    rate_percent: Optional[Decimal] = Field(
        default=None, ge=0, alias="ratePercent"
    )
    is_active: Optional[bool] = Field(default=None, alias="isActive")


class IncentiveSlabResponse(BaseModel):
    model_config = _alias_config()

    id: int
    min_amount: Decimal = Field(serialization_alias="minAmount")
    max_amount: Optional[Decimal] = Field(serialization_alias="maxAmount")
    rate_percent: Decimal = Field(serialization_alias="ratePercent")
    is_active: bool = Field(serialization_alias="isActive")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class UpdateIncentiveSlabsRequest(BaseModel):
    model_config = _alias_config()

    slabs: list[IncentiveSlabCreate]


# ==========================================================
# SALES TARGET (monthly)
# ==========================================================

class DefaultSalesTargetUpdate(BaseModel):
    model_config = _alias_config()

    default_monthly_target: Decimal = Field(
        ...,
        gt=0,
        alias="defaultMonthlyTarget",
    )


class DefaultSalesTargetResponse(BaseModel):
    model_config = _alias_config()

    default_monthly_target: Decimal = Field(
        serialization_alias="defaultMonthlyTarget"
    )


class EmployeeSalesTargetAssign(BaseModel):
    model_config = _alias_config()

    monthly_target: Decimal = Field(..., gt=0, alias="monthlyTarget")


class EmployeeSalesTargetItem(BaseModel):
    model_config = _alias_config()

    employee_id: int = Field(serialization_alias="employeeId")
    employee_code: Optional[str] = Field(
        default=None, serialization_alias="employeeCode"
    )
    employee_name: str = Field(serialization_alias="employeeName")
    assigned_target: Optional[Decimal] = Field(
        default=None, serialization_alias="assignedTarget"
    )
    effective_target: Decimal = Field(serialization_alias="effectiveTarget")
    target_assigned: bool = Field(serialization_alias="targetAssigned")
    target_source: str = Field(serialization_alias="targetSource")  # assigned | default


class SalesTargetOverviewResponse(BaseModel):
    model_config = _alias_config()

    default_monthly_target: Decimal = Field(
        serialization_alias="defaultMonthlyTarget"
    )
    employees: list[EmployeeSalesTargetItem]
