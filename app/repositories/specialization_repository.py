from sqlalchemy.orm import Session

from app.db.models.specialization import Specialization


class SpecializationRepository:

    @staticmethod
    def get_all(db: Session, *, active_only: bool = False):
        query = db.query(Specialization)
        if active_only:
            query = query.filter(Specialization.is_active.is_(True))
        return query.order_by(Specialization.name).all()

    @staticmethod
    def get_by_id(db: Session, specialization_id: int):
        return (
            db.query(Specialization)
            .filter(Specialization.id == specialization_id)
            .first()
        )

    @staticmethod
    def get_by_name(db: Session, name: str):
        return (
            db.query(Specialization)
            .filter(Specialization.name == name)
            .first()
        )

    @staticmethod
    def get_by_code(db: Session, code: str):
        return (
            db.query(Specialization)
            .filter(Specialization.specialization_code == code)
            .first()
        )

    @staticmethod
    def create(db: Session, specialization: Specialization):
        db.add(specialization)
        db.commit()
        db.refresh(specialization)
        return specialization

    @staticmethod
    def update(db: Session, specialization: Specialization):
        db.add(specialization)
        db.commit()
        db.refresh(specialization)
        return specialization

    @staticmethod
    def delete(db: Session, specialization: Specialization):
        db.delete(specialization)
        db.commit()
