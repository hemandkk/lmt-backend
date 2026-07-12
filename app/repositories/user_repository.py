from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.user import User


class UserRepository:

    @staticmethod
    def get_by_email(
        db: Session,
        email: str
    ):
        if not email:
            return None
        return (
            db.query(User)
            .filter(func.lower(User.email) == email.strip().lower())
            .first()
        )

    @staticmethod
    def get_by_employee_id(
        db: Session,
        employee_id: str
    ):
        if not employee_id:
            return None
        return (
            db.query(User)
            .filter(
                func.lower(User.employee_id) == employee_id.strip().lower()
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