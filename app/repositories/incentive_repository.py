from sqlalchemy.orm import Session

from app.db.models.incentive_slab import IncentiveSlab


class IncentiveRepository:

    @staticmethod
    def get_all(db: Session, include_inactive: bool = False):
        query = db.query(IncentiveSlab)
        if not include_inactive:
            query = query.filter(IncentiveSlab.is_active.is_(True))
        return query.order_by(IncentiveSlab.min_amount.asc()).all()

    @staticmethod
    def get_by_id(db: Session, slab_id: int) -> IncentiveSlab | None:
        return (
            db.query(IncentiveSlab)
            .filter(IncentiveSlab.id == slab_id)
            .first()
        )

    @staticmethod
    def delete_all(db: Session):
        db.query(IncentiveSlab).delete()
        db.commit()

    @staticmethod
    def create(db: Session, slab: IncentiveSlab) -> IncentiveSlab:
        db.add(slab)
        db.commit()
        db.refresh(slab)
        return slab

    @staticmethod
    def update(db: Session, slab: IncentiveSlab) -> IncentiveSlab:
        db.commit()
        db.refresh(slab)
        return slab

    @staticmethod
    def delete(db: Session, slab: IncentiveSlab) -> None:
        db.delete(slab)
        db.commit()

    @staticmethod
    def soft_delete(db: Session, slab: IncentiveSlab) -> IncentiveSlab:
        slab.is_active = False
        return IncentiveRepository.update(db, slab)
