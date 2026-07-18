"""App role helpers and admission-stage authorization rules."""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from app.db.models.prospect import AdmissionStage
from app.db.models.user import User, UserRole

# Stages only admin + processing_team may set
RESTRICTED_ADMISSION_STAGES = frozenset(
    {
        AdmissionStage.waiting_result,
        AdmissionStage.result_announced,
        AdmissionStage.completed,
        AdmissionStage.delivered,
    }
)

ACCOUNTANT_VISIBLE_STAGES = frozenset({AdmissionStage.certificate_waiting})

PROCESSING_VISIBLE_STAGES = frozenset(
    {
        AdmissionStage.waiting_result,
        AdmissionStage.result_announced,
    }
)

# Creatable via POST/PUT /employees (not admin)
ASSIGNABLE_ROLES = frozenset(
    {
        UserRole.employee,
        UserRole.accountant,
        UserRole.processing_team,
    }
)

# Sales performance / targets / dashboard employee lists
SALES_ROLES = frozenset({UserRole.employee})


def normalize_role(value: Any) -> UserRole:
    if isinstance(value, UserRole):
        return value
    if value is None or value == "":
        return UserRole.employee

    raw = str(value).strip()
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw).lower()
    snake = snake.replace("-", "_").replace(" ", "_")
    compact = re.sub(r"[^a-z0-9]", "", snake)

    aliases = {
        "admin": UserRole.admin,
        "employee": UserRole.employee,
        "accountant": UserRole.accountant,
        "processing_team": UserRole.processing_team,
        "processing": UserRole.processing_team,
        "processingteam": UserRole.processing_team,
        "procession_team": UserRole.processing_team,  # common typo
        "processionteam": UserRole.processing_team,
    }
    if snake in aliases:
        return aliases[snake]
    if compact in aliases:
        return aliases[compact]
    raise ValueError(f"Invalid role: {value}")


def role_value(user: User) -> str:
    role = getattr(user, "role", None)
    if hasattr(role, "value"):
        return str(role.value)
    return str(role or "")


def is_admin(user: User) -> bool:
    return user.role == UserRole.admin


def is_employee(user: User) -> bool:
    return user.role == UserRole.employee


def is_accountant(user: User) -> bool:
    return user.role == UserRole.accountant


def is_processing_team(user: User) -> bool:
    return user.role == UserRole.processing_team


def can_mutate_leads(user: User) -> bool:
    """Create/edit leads, CRM stage, exam, docs, add payment."""
    return user.role in (UserRole.admin, UserRole.employee)


def can_change_admission_stage(user: User) -> bool:
    return user.role in (
        UserRole.admin,
        UserRole.employee,
        UserRole.processing_team,
    )


def can_set_restricted_admission_stage(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.processing_team)


def can_verify_payments(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.accountant)


def admission_stage_allowed_for_role(
    user: User, stage: AdmissionStage
) -> bool:
    """Whether caller may SET this admission stage."""
    if not can_change_admission_stage(user):
        return False
    if stage in RESTRICTED_ADMISSION_STAGES:
        return can_set_restricted_admission_stage(user)
    return True


def visible_admission_stages_for_role(
    user: User,
) -> Optional[frozenset[AdmissionStage]]:
    """
    Forced admission-stage visibility for list/get.
    None = no force filter (admin / employee use other scopes).
    """
    if user.role == UserRole.accountant:
        return ACCOUNTANT_VISIBLE_STAGES
    if user.role == UserRole.processing_team:
        return PROCESSING_VISIBLE_STAGES
    return None


def prospect_visible_to_user(prospect, user: User) -> bool:
    if is_admin(user):
        return True
    if is_employee(user):
        return prospect.assigned_to_id == user.id

    stage = getattr(prospect, "admission_stage", None)
    if isinstance(stage, str):
        try:
            stage = AdmissionStage(stage)
        except ValueError:
            return False

    allowed = visible_admission_stages_for_role(user)
    if allowed is None:
        return False
    return stage in allowed


def intersect_admission_filters(
    requested: Optional[Iterable[AdmissionStage]],
    forced: Optional[frozenset[AdmissionStage]],
) -> Optional[list[AdmissionStage]]:
    """
    Combine client admissionStage(s) with role-forced visibility.
    Returns None = no admission filter; list = IN filter.

    For accountant / processing_team, forced stages always apply.
    Client filters may narrow within that set; incompatible filters
    (e.g. accountant + waiting_result) fall back to the full forced set
    so outdated frontend query params still return the correct leads.
    """
    if forced is None and not requested:
        return None
    if forced is None:
        return list(requested or [])
    if not requested:
        return list(forced)
    overlap = [s for s in requested if s in forced]
    if not overlap:
        return list(forced)
    return overlap
