from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id

from app.db.models.prospect import Prospect
from app.db.models.prospect_document import (
    ProspectDocument,
)

from app.repositories.document_repository import (
    DocumentRepository,
)

from app.repositories.prospect_repository import (
    ProspectRepository,
)

from app.schemas.document import (
    DocumentUpdate,
)


class DocumentService:

    @staticmethod
    def upload_document(
        db: Session,
        prospect_id: int,
        document_type,
        file: UploadFile,
        remarks: str | None = None,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        document_code = generate_id(
            db,
            ProspectDocument,
            "document_id",
            "DOC",
        )

        (
            file_url,
            stored_filename,
            file_size,
        ) = FileStorage.save_file(
            upload_file=file,
            folder=f"prospects/{prospect.prospect_id}",
            filename=document_code,
        )

        document = ProspectDocument(

            document_id=document_code,

            prospect_id=prospect.id,

            document_type=document_type,

            original_filename=file.filename,

            stored_filename=stored_filename,

            file_url=file_url,

            mime_type=file.content_type,

            file_size=file_size,

            remarks=remarks,

            verified=False,
        )

        return DocumentRepository.create(
            db,
            document,
        )

    @staticmethod
    def get_documents(
        db: Session,
        prospect_id: int,
    ):

        return DocumentRepository.get_by_prospect(
            db,
            prospect_id,
        )

    @staticmethod
    def get_document(
        db: Session,
        document_id: int,
    ):

        document = DocumentRepository.get_by_id(
            db,
            document_id,
        )

        if not document:
            raise ValueError(
                "Document not found."
            )

        return document

    @staticmethod
    def update_document(
        db: Session,
        document_id: int,
        payload: DocumentUpdate,
    ):

        document = DocumentRepository.get_by_id(
            db,
            document_id,
        )

        if not document:
            raise ValueError(
                "Document not found."
            )

        data = payload.model_dump(
            exclude_unset=True,
        )

        for key, value in data.items():

            setattr(
                document,
                key,
                value,
            )

        return DocumentRepository.update(
            db,
            document,
        )

    @staticmethod
    def delete_document(
        db: Session,
        document_id: int,
    ):

        document = DocumentRepository.get_by_id(
            db,
            document_id,
        )

        if not document:
            raise ValueError(
                "Document not found."
            )

        FileStorage.delete_file(
            document.file_url,
        )

        DocumentRepository.delete(
            db,
            document,
        )