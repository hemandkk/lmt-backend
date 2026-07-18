from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import (
    can_mutate_leads,
    can_verify_payments,
    is_admin,
    is_employee,
    prospect_visible_to_user,
)
from app.db.models.user import User, UserRole
from app.dependencies.auth import get_current_user
from app.repositories.prospect_repository import ProspectRepository


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def require_employee(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in (UserRole.admin, UserRole.employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    return current_user


def require_lead_mutator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Admin or sales employee — create/edit leads, CRM stage, exam, payments, docs."""
    if not can_mutate_leads(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify leads.",
        )
    return current_user


def require_payment_verifier(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_verify_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or accountant may verify payments.",
        )
    return current_user


def resolve_employee_scope(
    current_user: User,
    requested_employee_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve which employee_id to filter by.

    - Sales employee: always forced to their own id.
    - Admin: None = all users; or requested_employee_id if provided.
    - Accountant / processing_team: no assignee scope (admission filters apply).
    """
    if is_employee(current_user):
        return current_user.id

    if is_admin(current_user):
        return requested_employee_id

    return None


def ensure_prospect_access(
    db: Session,
    prospect_id: int,
    current_user: User,
):
    """
    Load prospect and ensure the current user may access it.
    Returns the prospect or raises 403/404.
    """
    prospect = ProspectRepository.get_by_id(db, prospect_id)
    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prospect not found.",
        )

    if prospect_visible_to_user(prospect, current_user):
        return prospect

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this prospect.",
    )


def ensure_payment_access(
    db: Session,
    payment,
    current_user: User,
):
    """Ensure payment belongs to a prospect the user can access."""
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    if is_admin(current_user):
        return payment

    # Accountant may access payments on leads they can see (certificate_waiting)
    # via ensure_prospect_access.
    ensure_prospect_access(db, payment.prospect_id, current_user)
    return payment


def deny_if_cannot_mutate_leads(current_user: User) -> None:
    if not can_mutate_leads(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify leads.",
        )
