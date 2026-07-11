from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ==========================================================
# COURSE
# ==========================================================

class CourseCreate(BaseModel):
    name: str


class CourseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    name: str

    active: bool

    created_at: datetime

    updated_at: datetime


# ==========================================================
# INCENTIVE SLAB
# ==========================================================

class IncentiveSlabCreate(BaseModel):
    min_amount: Decimal

    max_amount: Decimal | None = None

    rate_percent: Decimal


class IncentiveSlabResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    min_amount: Decimal

    max_amount: Decimal | None

    rate_percent: Decimal

    is_active: bool

    created_at: datetime

    updated_at: datetime


class UpdateIncentiveSlabsRequest(BaseModel):
    slabs: list[IncentiveSlabCreate]