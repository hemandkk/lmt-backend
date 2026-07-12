from sqlalchemy.orm import Session

from app.core.security import (
    verify_password,
    create_access_token,
)

from app.repositories.user_repository import (
    UserRepository,
)


class AuthService:

    @staticmethod
    def login(
        db: Session,
        username: str,
        password: str,
    ):
        username = (username or "").strip()
        password = password or ""

        user = (
            UserRepository.get_by_email(db, username)
            or UserRepository.get_by_employee_id(db, username)
        )

        if not user:
            return None

        stored_hash = (user.password_hash or "").strip()
        if not stored_hash or not verify_password(password, stored_hash):
            return None

        if not user.is_active:
            return None

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "role": user.role.value,
            }
        )
        return user, access_token
