from sqlalchemy.orm import Session

from app.db.models.user import User


class UserRepository:

    @staticmethod
    def get_by_email(
        db: Session,
        email: str
    ):
        return (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

    @staticmethod
    def get_by_employee_id(
        db: Session,
        employee_id: str
    ):
        return (
            db.query(User)
            .filter(
                User.employee_id == employee_id
            )
            .first()
        )

    @staticmethod
    def get_by_id(
        db: Session,
        user_id: int
    ):
        return (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )