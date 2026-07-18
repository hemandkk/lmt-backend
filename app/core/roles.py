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
        UserRole.manager,
        UserRole.sales_head,
    }
)

# Roles that own leads / mutate CRM like sales staff
SALES_ROLES = frozenset(
    {
        UserRole.employee,
        UserRole.manager,
        UserRole.sales_head,
    }
)

# Team dashboard viewers (supervisors + admin)
TEAM_VIEWER_ROLES = frozenset(
    {
        UserRole.admin,
        UserRole.manager,
        UserRole.sales_head,
    }
)

SUPERVISOR_ROLES = frozenset(
    {
        UserRole.manager,
        UserRole.sales_head,
    }
)


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
        "procession_team": UserRole.processing_team,
        "processionteam": UserRole.processing_team,
        "manager": UserRole.manager,
        "sales_head": UserRole.sales_head,
        "saleshead": UserRole.sales_head,
        "sales_heads": UserRole.sales_head,
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


def is_manager(user: User) -> bool:
    return user.role == UserRole.manager


def is_sales_head(user: User) -> bool:
    return user.role == UserRole.sales_head


def is_team_supervisor(user: User) -> bool:
    return user.role in SUPERVISOR_ROLES


def is_sales_user(user: User) -> bool:
    """Employee / manager / sales_head — own-lead CRM scope."""
    return user.role in SALES_ROLES


def can_mutate_leads(user: User) -> bool:
    """Create/edit leads, CRM stage, exam, docs, add payment."""
    return user.role in (UserRole.admin, *SALES_ROLES)


def can_change_admission_stage(user: User) -> bool:
    return user.role in (
        UserRole.admin,
        *SALES_ROLES,
        UserRole.processing_team,
    )


def can_set_restricted_admission_stage(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.processing_team)


def can_verify_payments(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.accountant)


def can_view_team_dashboard(user: User) -> bool:
    return user.role in TEAM_VIEWER_ROLES


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
    None = no force filter (admin / sales users use other scopes).
    """
    if user.role == UserRole.accountant:
        return ACCOUNTANT_VISIBLE_STAGES
    if user.role == UserRole.processing_team:
        return PROCESSING_VISIBLE_STAGES
    return None


def prospect_visible_to_user(prospect, user: User) -> bool:
    if is_admin(user):
        return True
    if is_sales_user(user):
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
