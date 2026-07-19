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


class CourseUpdate(BaseModel):
    model_config = _alias_config()

    name: Optional[str] = None
    course_code: Optional[str] = Field(default=None, alias="courseCode")
    specialization: Optional[str] = None
    duration: Optional[str] = None
    fees: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = Field(default=None, alias="active")


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
# SPECIALIZATION (lead dropdown master — not FK-linked)
# ==========================================================

class SpecializationCreate(BaseModel):
    model_config = _alias_config()

    name: str
    specialization_code: Optional[str] = Field(
        default=None, alias="specializationCode"
    )
    description: Optional[str] = None
    is_active: bool = Field(default=True, alias="active")


class SpecializationUpdate(BaseModel):
    model_config = _alias_config()

    name: Optional[str] = None
    specialization_code: Optional[str] = Field(
        default=None, alias="specializationCode"
    )
    description: Optional[str] = None
    is_active: Optional[bool] = Field(default=None, alias="active")


class SpecializationResponse(BaseModel):
    model_config = _alias_config()

    id: int
    specialization_code: str = Field(serialization_alias="specializationCode")
    name: str
    description: Optional[str] = None
    is_active: bool = Field(serialization_alias="active")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class MasterImportResponse(BaseModel):
    model_config = _alias_config()

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


# ==========================================================
# INCENTIVE SLAB (lead-count based)
# ==========================================================

class IncentiveSlabCreate(BaseModel):
    model_config = _alias_config()

    min_leads: int = Field(..., ge=0, alias="minLeads")
    max_leads: Optional[int] = Field(default=None, alias="maxLeads")
    incentive_amount: Decimal = Field(..., ge=0, alias="incentiveAmount")
    is_active: bool = Field(default=True, alias="isActive")

    @field_validator("max_leads")
    @classmethod
    def max_gte_min(cls, value, info):
        min_leads = info.data.get("min_leads")
        if value is not None and min_leads is not None and value < min_leads:
            raise ValueError("maxLeads must be >= minLeads")
        return value


class IncentiveSlabUpdate(BaseModel):
    model_config = _alias_config()

    min_leads: Optional[int] = Field(default=None, ge=0, alias="minLeads")
    max_leads: Optional[int] = Field(default=None, alias="maxLeads")
    incentive_amount: Optional[Decimal] = Field(
        default=None, ge=0, alias="incentiveAmount"
    )
    is_active: Optional[bool] = Field(default=None, alias="isActive")


class IncentiveSlabResponse(BaseModel):
    model_config = _alias_config()

    id: int
    min_leads: int = Field(serialization_alias="minLeads")
    max_leads: Optional[int] = Field(serialization_alias="maxLeads")
    incentive_amount: Decimal = Field(serialization_alias="incentiveAmount")
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


class BulkEmployeeMonthlyTargetItem(BaseModel):
    model_config = _alias_config()

    employee_id: int = Field(alias="employeeId")
    monthly_target: Optional[Decimal] = Field(
        default=None, ge=0, alias="monthlyTarget"
    )


class BulkEmployeeMonthlyTargetRequest(BaseModel):
    """
    Assign/clear targets for many employees.
    monthlyTarget=null clears assignment (master default applies).
    """

    model_config = _alias_config()

    items: list[BulkEmployeeMonthlyTargetItem]


class BulkEmployeeMonthlyTargetResponse(BaseModel):
    model_config = _alias_config()

    default_monthly_target: Decimal = Field(
        serialization_alias="defaultMonthlyTarget"
    )
    employees: list[EmployeeSalesTargetItem]
