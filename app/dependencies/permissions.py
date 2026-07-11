from typing import Optional

from fastapi import Depends, HTTPException, status

from app.db.models.user import User, UserRole
from app.dependencies.auth import get_current_user
from app.repositories.prospect_repository import ProspectRepository
from sqlalchemy.orm import Session


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


def resolve_employee_scope(
    current_user: User,
    requested_employee_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve which employee_id to filter by.

    - Employee: always forced to their own id (cannot view others).
    - Admin: None = all users; or requested_employee_id if provided.
    """
    if current_user.role == UserRole.employee:
        return current_user.id

    return requested_employee_id


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

    if current_user.role == UserRole.admin:
        return prospect

    if prospect.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this prospect.",
        )
    return prospect


def ensure_payment_access(
    db: Session,
    payment,
    current_user: User,
):
    """Ensure payment belongs to a prospect the user can access."""
    if current_user.role == UserRole.admin:
        return payment

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    prospect = ProspectRepository.get_by_id(db, payment.prospect_id)
    if not prospect or prospect.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this payment.",
        )
    return payment
