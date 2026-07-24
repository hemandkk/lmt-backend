from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import (
    can_delete_expenses,
    can_fulfill_payment_requests,
    can_manage_expenses,
    can_manage_payment_requests,
    can_mutate_leads,
    can_verify_payments,
    can_view_team_dashboard,
    is_admin,
    is_sales_user,
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


def require_admin_or_accountant(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in (UserRole.admin, UserRole.accountant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or accountant access required.",
        )
    return current_user


def require_employee(
    current_user: User = Depends(get_current_user),
) -> User:
    if not (is_admin(current_user) or is_sales_user(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    return current_user


def require_lead_mutator(
    current_user: User = Depends(get_current_user),
) -> User:
    """Admin or sales staff — create/edit leads, CRM stage, exam, payments, docs."""
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


def require_expense_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_manage_expenses(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or accountant may manage expenses.",
        )
    return current_user


def require_expense_deleter(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_delete_expenses(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin may delete expenses.",
        )
    return current_user


def require_payment_request_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_manage_payment_requests(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or accountant may manage payment requests.",
        )
    return current_user


def require_payment_request_fulfiller(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_fulfill_payment_requests(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin may fulfill payment requests.",
        )
    return current_user


def require_team_viewer(
    current_user: User = Depends(get_current_user),
) -> User:
    if not can_view_team_dashboard(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team dashboard access requires admin, manager, or sales_head.",
        )
    return current_user


def resolve_employee_scope(
    current_user: User,
    requested_employee_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve which employee_id to filter by.

    - Sales roles (employee/manager/sales_head): always forced to their own id.
    - Admin: None = all users; or requested_employee_id if provided.
    - Accountant / processing_team: no assignee scope (admission filters apply).
    """
    if is_sales_user(current_user):
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
