from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.prospect_document import ProspectDocument


class DocumentRepository:

    @staticmethod
    def create(
        db: Session,
        document: ProspectDocument,
    ) -> ProspectDocument:

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    @staticmethod
    def get_by_id(
        db: Session,
        document_id: int,
    ) -> Optional[ProspectDocument]:

        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.id == document_id
            )
            .first()
        )

    @staticmethod
    def get_by_document_id(
        db: Session,
        document_code: str,
    ) -> Optional[ProspectDocument]:

        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.document_id == document_code
            )
            .first()
        )

    @staticmethod
    def get_by_prospect(
        db: Session,
        prospect_id: int,
    ) -> list[ProspectDocument]:

        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.prospect_id == prospect_id
            )
            .order_by(
                ProspectDocument.created_at.desc()
            )
            .all()
        )

    @staticmethod
    def get_by_prospect_and_type(
        db: Session,
        prospect_id: int,
        document_type,
    ) -> Optional[ProspectDocument]:
        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.prospect_id == prospect_id,
                ProspectDocument.document_type == document_type,
            )
            .order_by(ProspectDocument.created_at.desc())
            .first()
        )

    @staticmethod
    def update(
        db: Session,
        document: ProspectDocument,
    ) -> ProspectDocument:

        db.commit()
        db.refresh(document)

        return document

    @staticmethod
    def delete(
        db: Session,
        document: ProspectDocument,
    ):

        db.delete(document)
        db.commit()

    @staticmethod
    def exists(
        db: Session,
        prospect_id: int,
        document_type: str,
    ) -> bool:

        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.prospect_id == prospect_id,
                ProspectDocument.document_type == document_type,
            )
            .first()
            is not None
        )

    @staticmethod
    def count_by_prospect(
        db: Session,
        prospect_id: int,
    ) -> int:

        return (
            db.query(ProspectDocument)
            .filter(
                ProspectDocument.prospect_id == prospect_id
            )
            .count()
        )