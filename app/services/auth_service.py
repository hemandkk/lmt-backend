from sqlalchemy.orm import Session

from app.core.security import (
    verify_password,
    create_access_token,
    hash_password
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
        """ print("Password from DB:", repr(user.password_hash))
        print("Length:", len(user.password_hash))
        hashed = hash_password("asdf1234")
        print('$$$$$$$$$$')
        print(repr(hashed))
        print(verify_password("asdf1234", hashed)) """

        db_hash = "$2b$12$o0PqavtBPaFe1sXfz8CT0.5kSgquoleHR.k.Zuq.2ojDwBKtguq3."
        print('$$$$$$$$$$')

        print(verify_password("asdf1234", db_hash))
        if not verify_password(
            password,
            user.password_hash,
        ):
            print("HASH failed")
            return None

        if not user.is_active:
            return None

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "role": user.role.value,
            }
        )
        print("USER toke")
        print(access_token)
        return user, access_token