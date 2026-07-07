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

        user = (
            UserRepository.get_by_email(
                db,
                username,
            )
            or
            UserRepository.get_by_employee_id(
                db,
                username,
            )
        )

        if not user:
            return None

        if not verify_password(
            password,
            user.password_hash,
        ):
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