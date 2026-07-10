from fastapi import Depends, HTTPException, status

from app.db.models.user import User, UserRole
from app.dependencies.auth import get_current_user


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

    if current_user.role not in (
        UserRole.admin,
        UserRole.employee,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    return current_user