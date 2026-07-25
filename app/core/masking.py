"""Prospect data masking for completed admission stage."""

from __future__ import annotations

from decimal import Decimal

from app.db.models.prospect import AdmissionStage, Prospect
from app.db.models.user import User, UserRole


MASKED_VALUE = "**********"

# Fields to mask when admission_stage is "completed" and user is not admin
# Each entry: (field_name, replacement_value)
# String fields get MASKED_VALUE, numeric fields get 0, date/None fields get None
MASKED_FIELDS = (
    "name",
    "email",
    "phone",
    "father_name",
    "mother_name",
    "specialization",
    "university",
    "address",
    "delivery_address",
    "assigned_to_name",
    "assigned_to_code",
)

# Fields that need type-specific masking
MASKED_DECIMAL_FIELDS = ("estimated_deal_value",)
MASKED_DATE_FIELDS = ("delivery_date",)


def _should_mask(user: User, prospect) -> bool:
    """Check if masking should be applied."""
    if user.role == UserRole.admin:
        return False
    stage = getattr(prospect, "admission_stage", None)
    if hasattr(stage, "value"):
        stage = stage.value
    return stage == AdmissionStage.completed.value


def mask_prospect(prospect, user: User) -> None:
    """
    Mask sensitive fields on a prospect object in-place if:
    - prospect.admission_stage == completed
    - user is not admin
    """
    if not _should_mask(user, prospect):
        return

    for field in MASKED_FIELDS:
        if hasattr(prospect, field):
            setattr(prospect, field, MASKED_VALUE)

    for field in MASKED_DECIMAL_FIELDS:
        if hasattr(prospect, field):
            setattr(prospect, field, Decimal("0"))

    for field in MASKED_DATE_FIELDS:
        if hasattr(prospect, field):
            setattr(prospect, field, None)


def mask_prospect_dict(data: dict, user: User, admission_stage=None) -> dict:
    """
    Mask sensitive fields on a prospect dict if:
    - admission_stage == completed
    - user is not admin
    """
    if user.role == UserRole.admin:
        return data

    stage = admission_stage or data.get("admissionStage") or data.get("admission_stage")
    if hasattr(stage, "value"):
        stage = stage.value

    if stage != AdmissionStage.completed.value:
        return data

    alias_map = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "father_name": "fatherName",
        "mother_name": "motherName",
        "specialization": "specialization",
        "university": "university",
        "address": "address",
        "delivery_address": "deliveryAddress",
        "assigned_to_name": "assignedToName",
        "assigned_to_code": "assignedToCode",
    }

    for field, alias in alias_map.items():
        if alias in data:
            data[alias] = MASKED_VALUE

    # Numeric fields
    if "estimatedValue" in data:
        data["estimatedValue"] = 0

    # Date fields
    if "deliveryDate" in data:
        data["deliveryDate"] = None

    return data
