from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id

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
    def _sync_sheets(db: Session, prospect_id: int) -> None:
        from app.services.google_sheets_service import GoogleSheetsService

        GoogleSheetsService.sync_prospect_by_id(db, prospect_id)

    @staticmethod
    def _next_document_code(db: Session) -> str:
        """Sequential DOC code that is unique in DB (retries on collision)."""
        code = generate_id(db, ProspectDocument, "document_id", "DOC")
        attempts = 0
        while DocumentRepository.get_by_document_id(db, code):
            attempts += 1
            # Skip past collisions (legacy/hex IDs, races)
            match_digits = "".join(ch for ch in code[3:] if ch.isdigit())
            n = int(match_digits or "0") + attempts
            code = f"DOC{n:05d}"
            if attempts > 50:
                from uuid import uuid4

                code = f"DOC{uuid4().hex[:5].upper()}"
                break
        return code

    @staticmethod
    def upload_document(
        db: Session,
        prospect_id: int,
        document_type,
        file: UploadFile,
        remarks: str | None = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        # Always create a new row so multiple files per type are supported
        # (e.g. aadhaar front+back, degree marks+provisional).
        document_code = DocumentService._next_document_code(db)

        file_url, stored_filename, file_size = FileStorage.save_file(
            upload_file=file,
            folder=f"prospects/{prospect.prospect_id}",
            filename=document_code,
        )

        document = ProspectDocument(
            document_id=document_code,
            prospect_id=prospect.id,
            document_type=document_type,
            original_filename=file.filename or "document",
            stored_filename=stored_filename,
            file_url=file_url,
            mime_type=file.content_type,
            file_size=file_size,
            remarks=remarks,
            verified=False,
        )

        created = DocumentRepository.create(db, document)
        DocumentService._sync_sheets(db, prospect_id)
        return created

    @staticmethod
    def get_documents(db: Session, prospect_id: int):
        return DocumentRepository.get_by_prospect(db, prospect_id)

    @staticmethod
    def get_document(db: Session, document_id: int):
        document = DocumentRepository.get_by_id(db, document_id)
        if not document:
            raise ValueError("Document not found.")
        return document

    @staticmethod
    def update_document(
        db: Session,
        document_id: int,
        payload: DocumentUpdate,
    ):
        document = DocumentRepository.get_by_id(db, document_id)
        if not document:
            raise ValueError("Document not found.")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(document, key, value)

        updated = DocumentRepository.update(db, document)
        DocumentService._sync_sheets(db, document.prospect_id)
        return updated

    @staticmethod
    def delete_document(db: Session, document_id: int):
        document = DocumentRepository.get_by_id(db, document_id)
        if not document:
            raise ValueError("Document not found.")

        prospect_id = document.prospect_id
        FileStorage.delete_file(document.file_url)
        DocumentRepository.delete(db, document)
        DocumentService._sync_sheets(db, prospect_id)
