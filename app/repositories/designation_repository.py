from sqlalchemy.orm import Session

from app.db.models.designation import Designation


class DesignationRepository:

    @staticmethod
    def get_all(db: Session, *, active_only: bool = False):
        query = db.query(Designation)
        if active_only:
            query = query.filter(Designation.is_active.is_(True))
        return query.order_by(Designation.name).all()

    @staticmethod
    def get_by_id(db: Session, designation_id: int):
        return (
            db.query(Designation)
            .filter(Designation.id == designation_id)
            .first()
        )

    @staticmethod
    def get_by_name(db: Session, name: str):
        return (
            db.query(Designation)
            .filter(Designation.name == name)
            .first()
        )

    @staticmethod
    def create(db: Session, designation: Designation):
        db.add(designation)
        db.commit()
        db.refresh(designation)
        return designation

    @staticmethod
    def update(db: Session, designation: Designation):
        db.add(designation)
        db.commit()
        db.refresh(designation)
        return designation

    @staticmethod
    def delete(db: Session, designation: Designation):
        db.delete(designation)
        db.commit()
