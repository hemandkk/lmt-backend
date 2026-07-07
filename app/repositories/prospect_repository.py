from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.prospect import Prospect


class ProspectRepository:

    @staticmethod
    def create(
        db: Session,
        prospect: Prospect,
    ) -> Prospect:

        db.add(prospect)
        db.commit()
        db.refresh(prospect)

        return prospect

    @staticmethod
    def get_by_id(
        db: Session,
        prospect_id: int,
    ) -> Optional[Prospect]:

        return (
            db.query(Prospect)
            .filter(Prospect.id == prospect_id)
            .first()
        )

    @staticmethod
    def get_by_prospect_id(
        db: Session,
        prospect_code: str,
    ) -> Optional[Prospect]:

        return (
            db.query(Prospect)
            .filter(
                Prospect.prospect_id == prospect_code
            )
            .first()
        )

    @staticmethod
    def get_by_email(
        db: Session,
        email: str,
    ) -> Optional[Prospect]:

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

        query = db.query(Prospect)

        if search:

            search = f"%{search}%"

            query = query.filter(
                (Prospect.name.ilike(search))
                |
                (Prospect.email.ilike(search))
                |
                (Prospect.phone.ilike(search))
            )

        if stage:
            query = query.filter(
                Prospect.stage == stage
            )

        total = query.count()

        items = (
            query
            .order_by(
                Prospect.created_at.desc()
            )
            .offset(
                (page - 1) * page_size
            )
            .limit(page_size)
            .all()
        )

        return items, total

    @staticmethod
    def update(
        db: Session,
        prospect: Prospect,
    ) -> Prospect:

        db.commit()
        db.refresh(prospect)

        return prospect

    @staticmethod
    def delete(
        db: Session,
        prospect: Prospect,
    ):

        db.delete(prospect)
        db.commit()

    @staticmethod
    def total_count(
        db: Session,
    ) -> int:

        return (
            db.query(
                func.count(Prospect.id)
            )
            .scalar()
        )