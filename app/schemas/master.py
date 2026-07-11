from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ==========================================================
# COURSE
# ==========================================================

class CourseCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    course_code: Optional[str] = Field(default=None, alias="courseCode")
    specialization: Optional[str] = None
    duration: Optional[str] = None
    fees: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = Field(default=True, alias="active")


class CourseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

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
    min_amount: Decimal
    max_amount: Decimal | None = None
    rate_percent: Decimal


class IncentiveSlabResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    min_amount: Decimal
    max_amount: Decimal | None
    rate_percent: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateIncentiveSlabsRequest(BaseModel):
    slabs: list[IncentiveSlabCreate]
