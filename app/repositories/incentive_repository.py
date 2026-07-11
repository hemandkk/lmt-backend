from sqlalchemy.orm import Session

from app.db.models.incentive_slab import (
    IncentiveSlab,
)


class IncentiveRepository:

    @staticmethod
    def get_all(
        db: Session,
    ):

        return (
            db.query(IncentiveSlab)
            .filter(
                IncentiveSlab.is_active == True
            )
            .order_by(
                IncentiveSlab.min_amount
            )
            .all()
        )

    @staticmethod
    def delete_all(
        db: Session,
    ):

        db.query(
            IncentiveSlab
        ).delete()

        db.commit()

    @staticmethod
    def create(
        db: Session,
        slab: IncentiveSlab,
    ):

        db.add(slab)

        db.commit()

        db.refresh(slab)

        return slab