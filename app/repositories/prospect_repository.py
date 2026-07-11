from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models.prospect import Prospect


class ProspectRepository:

    @staticmethod
    def _with_relations():
        return (
            selectinload(Prospect.payments),
            selectinload(Prospect.documents),
            joinedload(Prospect.assigned_to),
            joinedload(Prospect.course),
        )

    @staticmethod
    def create(db: Session, prospect: Prospect) -> Prospect:
        db.add(prospect)
        db.commit()
        return ProspectRepository.get_by_id(db, prospect.id)

    @staticmethod
    def get_by_id(db: Session, prospect_id: int) -> Optional[Prospect]:
        return (
            db.query(Prospect)
            .options(*ProspectRepository._with_relations())
            .filter(Prospect.id == prospect_id)
            .first()
        )

    @staticmethod
    def get_by_prospect_id(
        db: Session, prospect_code: str
    ) -> Optional[Prospect]:
        return (
            db.query(Prospect)
            .options(*ProspectRepository._with_relations())
            .filter(Prospect.prospect_id == prospect_code)
            .first()
        )

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Prospect]:
        return (
            db.query(Prospect)
            .filter(Prospect.email == email)
            .first()
        )

    @staticmethod
    def list(
        db: Session,
        page: int,
        page_size: int,
        search: str | None = None,
        stage: str | None = None,
    ):
        query = db.query(Prospect).options(
            *ProspectRepository._with_relations()
        )

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (Prospect.name.ilike(pattern))
                | (Prospect.email.ilike(pattern))
                | (Prospect.phone.ilike(pattern))
                | (Prospect.prospect_id.ilike(pattern))
            )

        if stage:
            query = query.filter(Prospect.stage == stage)

        total = query.count()
        items = (
            query.order_by(Prospect.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(db: Session, prospect: Prospect) -> Prospect:
        db.commit()
        return ProspectRepository.get_by_id(db, prospect.id)

    @staticmethod
    def delete(db: Session, prospect: Prospect) -> None:
        db.delete(prospect)
        db.commit()

    @staticmethod
    def total_count(db: Session) -> int:
        return db.query(func.count(Prospect.id)).scalar() or 0
